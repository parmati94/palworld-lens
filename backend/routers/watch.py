"""Watch/reload endpoints for file watching and SSE streaming"""
import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from sse_starlette.sse import EventSourceResponse

from backend.common.logging_config import get_logger
from backend.common.auth import require_auth
from backend.common.config import config
from backend.parser import parser
from backend import startup

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["watch"])


@router.get("/watch", dependencies=[Depends(require_auth)])
async def watch_save_changes(request: Request):
    """Server-Sent Events endpoint for real-time save updates"""
    # Return error if auto-watch is not currently active
    if not startup.watch_active:
        raise HTTPException(
            status_code=503,
            detail="Auto-watch is not currently active. Enable it from the frontend toggle."
        )
    
    client_queue = asyncio.Queue(maxsize=10)
    startup.sse_clients.append(client_queue)
    
    async def event_generator():
        try:
            # Send initial data
            try:
                players = parser.get_players()
                pals = parser.get_pals()
                guilds = parser.get_guilds()
                containers_by_base = parser.get_base_containers()
                save_info = parser.get_save_info()
                
                initial_data = {
                    "info": save_info.model_dump() if hasattr(save_info, 'model_dump') else save_info,
                    "players": [p.model_dump() if hasattr(p, 'model_dump') else p for p in players],
                    "pals": [p.model_dump() if hasattr(p, 'model_dump') else p for p in pals],
                    "guilds": [g.model_dump() if hasattr(g, 'model_dump') else g for g in guilds],
                    "base_containers": {
                        "containers": {
                            base_id: [c.model_dump() if hasattr(c, 'model_dump') else c for c in containers]
                            for base_id, containers in containers_by_base.items()
                        },
                        "count": len(containers_by_base)
                    },
                }
                yield {
                    "event": "init",
                    "data": json.dumps(initial_data, default=str)
                }
            except Exception as e:
                logger.error(f"Error sending initial data: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
                return
            
            # Listen for updates
            while True:
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected")
                    break
                
                try:
                    # Wait for update notification (with timeout to check disconnect)
                    update = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    
                    # Send updated data
                    players = parser.get_players()
                    pals = parser.get_pals()
                    guilds = parser.get_guilds()
                    containers_by_base = parser.get_base_containers()
                    save_info = parser.get_save_info()
                    
                    updated_data = {
                        "info": save_info.model_dump() if hasattr(save_info, 'model_dump') else save_info,
                        "players": [p.model_dump() if hasattr(p, 'model_dump') else p for p in players],
                        "pals": [p.model_dump() if hasattr(p, 'model_dump') else p for p in pals],
                        "guilds": [g.model_dump() if hasattr(g, 'model_dump') else g for g in guilds],
                        "base_containers": {
                            "containers": {
                                base_id: [c.model_dump() if hasattr(c, 'model_dump') else c for c in containers]
                                for base_id, containers in containers_by_base.items()
                            },
                            "count": len(containers_by_base)
                        },
                    }
                    yield {
                        "event": "update",
                        "data": json.dumps(updated_data, default=str)
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "ping",
                        "data": ""
                    }
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    break
        finally:
            # Remove client queue when disconnected
            if client_queue in startup.sse_clients:
                startup.sse_clients.remove(client_queue)
            logger.debug(f"SSE client removed. Active clients: {len(startup.sse_clients)}")
    
    return EventSourceResponse(event_generator())


@router.post("/reload", dependencies=[Depends(require_auth)])
@router.get("/reload", dependencies=[Depends(require_auth)])
async def reload_save():
    """Reload the save file"""
    try:
        # If in remote mode, trigger a manual poll
        if startup.remote_mode and startup.remote_poller:
            logger.info("🔄 Manual reload requested (remote mode)")
            if await startup.remote_poller.poll_now():
                return {
                    "success": True,
                    "message": "Remote save downloaded and reloaded successfully",
                    "info": parser.get_save_info(),
                    "remote": True
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to download remote save")
        
        # Local mode - just reload from disk
        if parser.reload():
            return {
                "success": True,
                "message": "Save reloaded successfully",
                "info": parser.get_save_info(),
                "remote": False
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reload save")
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watch/status", dependencies=[Depends(require_auth)])
async def get_watch_status():
    """Get the current auto-watch/polling status"""
    # Determine if toggle is allowed based on mode
    if startup.remote_mode:
        allowed = config.REMOTE_POLL_INTERVAL > 0
        message = "Remote polling is disabled (REMOTE_POLL_INTERVAL=0). Set interval > 0 to enable." if not allowed else None
    else:
        allowed = config.ENABLE_AUTO_WATCH
        message = "Auto-watch is controlled by ENABLE_AUTO_WATCH environment variable" if not allowed else None
    
    response = {
        "active": startup.watch_active,
        "allowed": allowed,
        "remote_mode": startup.remote_mode,
        "message": message
    }
    
    if startup.remote_mode:
        response["remote_config"] = {
            "protocol": config.get_remote_protocol(),
            "host": config.REMOTE_HOST,
            "port": config.REMOTE_PORT,
            "user": config.REMOTE_USER,
            "path": config.REMOTE_PATH,
            "poll_interval": config.REMOTE_POLL_INTERVAL
        }
    
    return response


@router.post("/watch/start", dependencies=[Depends(require_auth)])
async def start_watch():
    """Start the file watcher or remote poller"""
    
    # Handle remote mode
    if startup.remote_mode:
        if config.REMOTE_POLL_INTERVAL <= 0:
            raise HTTPException(
                status_code=403,
                detail="Remote polling is disabled. Set REMOTE_POLL_INTERVAL > 0 to enable."
            )
        
        # Check if already polling
        if startup.watch_active and startup.remote_poller:
            logger.info("⚠️  Remote polling already active, skipping duplicate start")
            return {
                "success": True,
                "message": "Remote polling is already active",
                "active": True
            }
        
        # Start remote poller
        if startup.remote_poller and startup.remote_poller.start():
            startup.watch_active = True
            logger.info("🌐 Remote polling started via API")
            return {
                "success": True,
                "message": "Remote polling started successfully",
                "active": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start remote poller")
    
    # Local mode - check if auto-watch is allowed by env var
    if not config.ENABLE_AUTO_WATCH:
        raise HTTPException(
            status_code=403,
            detail="Auto-watch is disabled by ENABLE_AUTO_WATCH environment variable. Set it to 'true' to enable this feature."
        )
    
    # Check if already watching
    if startup.watch_active and startup.watcher:
        logger.info("⚠️  Auto-watch already active, skipping duplicate start")
        return {
            "success": True,
            "message": "Auto-watch is already active",
            "active": True
        }
    
    # Stop existing watcher if it exists (cleanup)
    if startup.watcher:
        logger.debug("Cleaning up existing watcher before starting new one")
        startup.watcher.stop()
        startup.watcher = None
    
    # Create and start watcher
    try:
        from backend.utils.watcher import SaveWatcher
        
        async def on_save_change():
            """Callback when save file changes"""
            await startup.reload_and_notify(skip_if_no_clients=False)
        
        loop = asyncio.get_event_loop()
        startup.watcher = SaveWatcher(config.get_save_path(), on_save_change, loop)
        
        if startup.watcher.start():
            startup.watch_active = True
            logger.info("👀 Auto-watch started via API")
            return {
                "success": True,
                "message": "Auto-watch started successfully",
                "active": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start file watcher")
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watch/stop", dependencies=[Depends(require_auth)])
async def stop_watch():
    """Stop the file watcher or remote poller"""
    
    # Handle remote mode
    if startup.remote_mode:
        if not startup.watch_active or not startup.remote_poller:
            return {
                "success": True,
                "message": "Remote polling is already stopped",
                "active": False
            }
        
        try:
            await startup.remote_poller.stop()
            startup.watch_active = False
            logger.info("🛑 Remote polling stopped via API")
            return {
                "success": True,
                "message": "Remote polling stopped successfully",
                "active": False
            }
        except Exception as e:
            logger.error(f"Failed to stop remote poller: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Local mode
    if not startup.watch_active or not startup.watcher:
        return {
            "success": True,
            "message": "Auto-watch is already stopped",
            "active": False
        }
    
    try:
        startup.watcher.stop()
        startup.watcher = None
        startup.watch_active = False
        logger.info("🛑 Auto-watch stopped via API")
        return {
            "success": True,
            "message": "Auto-watch stopped successfully",
            "active": False
        }
    except Exception as e:
        logger.error(f"Failed to stop watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))
