"""FastAPI backend for Palworld Lens"""
import asyncio
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from backend.common.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from backend.common.config import config
from backend.common.auth import (
    require_auth, 
    verify_credentials, 
    create_session_token, 
    get_session_from_request,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE
)
from backend.parser import parser
from backend.utils.watcher import SaveWatcher

# Global watcher instance and SSE clients
watcher: Optional[SaveWatcher] = None
sse_clients: list[asyncio.Queue] = []
watch_active: bool = False  # Track if watching is currently active

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    global watcher, watch_active
    
    logger.info("🚀 Starting Palworld Lens")
    logger.info(f"📂 Save mount path: {config.SAVE_MOUNT_PATH}")
    
    # Try to load save on startup
    if config.get_level_sav_path():
        logger.info("🔍 Found save files, attempting auto-load...")
        if parser.load():
            logger.info("✅ Save loaded successfully on startup")
        else:
            logger.warning("⚠️  Failed to auto-load save")
    else:
        logger.warning("⚠️  No save files found in mounted directory")
    
    # Start file watcher if enabled
    if config.ENABLE_AUTO_WATCH:
        async def on_save_change():
            """Callback when save file changes"""
            logger.info("🔄 Save file changed, reloading...")
            if parser.reload():
                logger.info("✅ Save reloaded successfully")
                # Notify all SSE clients
                for client_queue in sse_clients:
                    try:
                        client_queue.put_nowait({"event": "reload"})
                    except asyncio.QueueFull:
                        pass  # Skip if queue is full
            else:
                logger.error("❌ Failed to reload save")
        
        # Get the current event loop to pass to watcher
        loop = asyncio.get_event_loop()
        watcher = SaveWatcher(config.get_save_path(), on_save_change, loop)
        if watcher.start():
            watch_active = True
    else:
        logger.info("⏸️  Auto-watch disabled by default (ENABLE_AUTO_WATCH=false)")
    
    yield
    
    # Stop watcher
    if watcher:
        watcher.stop()
    
    logger.info("👋 Shutting down Palworld Lens")

app = FastAPI(
    title="Palworld Lens",
    description="Read-only viewer for Palworld save files",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Palworld Lens API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "save_loaded": parser.loaded,
        "last_updated": parser.last_load_time.isoformat() if parser.last_load_time else None
    }

# Pydantic models for auth
class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if authentication is enabled and if user is logged in"""
    if not config.ENABLE_LOGIN:
        return {"enabled": False, "authenticated": True}
    
    username = get_session_from_request(request)
    return {
        "enabled": True,
        "authenticated": username is not None,
        "username": username if username else None
    }

@app.post("/api/auth/login")
async def login(login_data: LoginRequest, response: Response):
    """Login endpoint"""
    if not config.ENABLE_LOGIN:
        raise HTTPException(status_code=400, detail="Authentication is not enabled")
    
    if not verify_credentials(login_data.username, login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session token
    token = create_session_token(login_data.username)
    
    # Set cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False  # Set to True if using HTTPS
    )
    
    logger.info(f"User '{login_data.username}' logged in successfully")
    
    return {"success": True, "username": login_data.username}

@app.post("/api/auth/logout")
async def logout(response: Response):
    """Logout endpoint"""
    response.delete_cookie(SESSION_COOKIE_NAME)
    logger.info("User logged out")
    return {"success": True}

@app.get("/api/info", dependencies=[Depends(require_auth)])
async def get_save_info():
    """Get basic save file information"""
    return parser.get_save_info()

@app.get("/api/watch", dependencies=[Depends(require_auth)])
async def watch_save_changes(request: Request):
    """Server-Sent Events endpoint for real-time save updates"""
    # Return error if auto-watch is not currently active
    if not watch_active:
        raise HTTPException(
            status_code=503,
            detail="Auto-watch is not currently active. Enable it from the frontend toggle."
        )
    
    client_queue = asyncio.Queue(maxsize=10)
    sse_clients.append(client_queue)
    
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
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)
            logger.debug(f"SSE client removed. Active clients: {len(sse_clients)}")
    
    return EventSourceResponse(event_generator())

@app.post("/api/reload", dependencies=[Depends(require_auth)])
@app.get("/api/reload", dependencies=[Depends(require_auth)])
async def reload_save():
    """Reload the save file"""
    try:
        if parser.reload():
            return {
                "success": True,
                "message": "Save reloaded successfully",
                "info": parser.get_save_info()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reload save")
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watch/status", dependencies=[Depends(require_auth)])
async def get_watch_status():
    """Get the current auto-watch status"""
    return {
        "active": watch_active,
        "allowed": config.ENABLE_AUTO_WATCH,
        "message": "Auto-watch is controlled by ENABLE_AUTO_WATCH environment variable" if not config.ENABLE_AUTO_WATCH else None
    }

@app.post("/api/watch/start", dependencies=[Depends(require_auth)])
async def start_watch():
    """Start the file watcher"""
    global watcher, watch_active
    
    # Check if auto-watch is allowed by env var
    if not config.ENABLE_AUTO_WATCH:
        raise HTTPException(
            status_code=403,
            detail="Auto-watch is disabled by ENABLE_AUTO_WATCH environment variable. Set it to 'true' to enable this feature."
        )
    
    # Check if already watching
    if watch_active and watcher:
        logger.info("⚠️  Auto-watch already active, skipping duplicate start")
        return {
            "success": True,
            "message": "Auto-watch is already active",
            "active": True
        }
    
    # Stop existing watcher if it exists (cleanup)
    if watcher:
        logger.debug("Cleaning up existing watcher before starting new one")
        watcher.stop()
        watcher = None
    
    # Create and start watcher
    try:
        async def on_save_change():
            """Callback when save file changes"""
            logger.info("🔄 Save file changed, reloading...")
            if parser.reload():
                logger.info("✅ Save reloaded successfully")
                # Notify all SSE clients
                for client_queue in sse_clients:
                    try:
                        client_queue.put_nowait({"event": "reload"})
                    except asyncio.QueueFull:
                        pass  # Skip if queue is full
            else:
                logger.error("❌ Failed to reload save")
        
        loop = asyncio.get_event_loop()
        watcher = SaveWatcher(config.get_save_path(), on_save_change, loop)
        
        if watcher.start():
            watch_active = True
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

@app.post("/api/watch/stop", dependencies=[Depends(require_auth)])
async def stop_watch():
    """Stop the file watcher"""
    global watcher, watch_active
    
    if not watch_active or not watcher:
        return {
            "success": True,
            "message": "Auto-watch is already stopped",
            "active": False
        }
    
    try:
        watcher.stop()
        watcher = None
        watch_active = False
        logger.info("🛑 Auto-watch stopped via API")
        return {
            "success": True,
            "message": "Auto-watch stopped successfully",
            "active": False
        }
    except Exception as e:
        logger.error(f"Failed to stop watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/world-keys")
async def get_world_keys():
    """Debug endpoint to see what keys are available in world data"""
    if not parser.world_data:
        return {"error": "No world data loaded"}
    
    return {
        "keys": sorted(parser.world_data.keys()),
        "base_camp_exists": "BaseCampSaveData" in parser.world_data
    }

@app.get("/api/debug/base-camps")
async def get_base_camp_info():
    """Debug endpoint to examine base camp structure"""
    if not parser.world_data or "BaseCampSaveData" not in parser.world_data:
        return {"error": "No base camp data"}
    
    base_camp_data = parser.world_data["BaseCampSaveData"]
    result = {
        "type": str(type(base_camp_data)),
        "is_dict": isinstance(base_camp_data, dict),
    }
    
    if isinstance(base_camp_data, dict):
        result["keys"] = list(base_camp_data.keys())
        if "value" in base_camp_data:
            value = base_camp_data["value"]
            result["value_type"] = str(type(value))
            result["value_is_list"] = isinstance(value, list)
            if isinstance(value, list):
                result["base_count"] = len(value)
                if value:
                    first_base = value[0]
                    result["first_base_keys"] = list(first_base.keys()) if isinstance(first_base, dict) else None
                    if isinstance(first_base, dict) and "value" in first_base:
                        base_value = first_base["value"]
                        if isinstance(base_value, dict) and "RawData" in base_value:
                            raw = base_value["RawData"]
                            if isinstance(raw, dict) and "value" in raw:
                                raw_val = raw["value"]
                                result["first_base_raw_keys"] = list(raw_val.keys())[:20]
                                # Check container_ids structure
                                if "container_ids" in raw_val:
                                    cont_ids = raw_val["container_ids"]
                                    result["container_ids_type"] = str(type(cont_ids))
                                    result["container_ids_value"] = str(cont_ids)[:200]
    
    return result

@app.get("/api/debug/char-containers")
async def get_char_container_info():
    """Debug endpoint to examine character container structure"""
    if not parser.world_data or "CharacterContainerSaveData" not in parser.world_data:
        return {"error": "No character container data"}
    
    char_container_data = parser.world_data["CharacterContainerSaveData"]
    containers = char_container_data.get("value", [])
    
    result = {
        "total_containers": len(containers),
        "containers": []
    }
    
    # Check first few containers
    for i, container in enumerate(containers[:3]):
        cont_info = {"index": i}
        if isinstance(container, dict):
            cont_info["keys"] = list(container.keys())
            
            # Get container key/ID
            key = container.get("key")
            if isinstance(key, dict):
                key = key.get("value") or key.get("id")
            cont_info["container_id"] = str(key)[:50]
            
            # Get value
            value = container.get("value", {})
            if isinstance(value, dict) and "RawData" in value:
                raw = value["RawData"]
                if isinstance(raw, dict) and "value" in raw:
                    raw_val = raw["value"]
                    cont_info["raw_keys"] = list(raw_val.keys())
                    
                    # Check the values array
                    if "values" in raw_val:
                        values = raw_val["values"]
                        cont_info["values_type"] = str(type(values))
                        if isinstance(values, (list, tuple)):
                            cont_info["values_count"] = len(values)
                            if values:
                                first_val = values[0]
                                cont_info["first_value_type"] = str(type(first_val))
                                if isinstance(first_val, dict):
                                    cont_info["first_value_keys"] = list(first_val.keys())
                                    # Check if there's SlotIndex and instance_id
                                    if "SlotIndex" in first_val:
                                        cont_info["has_slot_index"] = True
                                        cont_info["first_slot_index"] = str(first_val.get("SlotIndex"))[:100]
                                    if "RawData" in first_val:
                                        raw_data = first_val["RawData"]
                                        if isinstance(raw_data, dict) and "value" in raw_data:
                                            rd_val = raw_data["value"]
                                            if isinstance(rd_val, dict):
                                                cont_info["first_raw_data_keys"] = list(rd_val.keys())
                    
                    # Check slots
                    if "Slots" in raw_val:
                        slots = raw_val["Slots"]
                        cont_info["slots_type"] = str(type(slots))
                        if isinstance(slots, dict):
                            cont_info["slots_keys"] = list(slots.keys())
                            if "values" in slots:
                                values = slots["values"]
                                cont_info["slot_count"] = len(values) if isinstance(values, list) else 0
        
        result["containers"].append(cont_info)
    
    return result

@app.get("/api/debug/work-data")
async def get_work_data_info():
    """Debug endpoint to examine work save data"""
    if not parser.world_data or "WorkSaveData" not in parser.world_data:
        return {"error": "No work save data"}
    
    work_data = parser.world_data["WorkSaveData"]
    result = {
        "type": str(type(work_data)),
        "is_dict": isinstance(work_data, dict)
    }
    
    if isinstance(work_data, dict):
        result["keys"] = list(work_data.keys())
        if "value" in work_data:
            value = work_data["value"]
            result["value_type"] = str(type(value))
            if isinstance(value, dict):
                result["value_keys"] = list(value.keys())
                
                # Check values array
                if "values" in value:
                    values = value["values"]
                    result["values_type"] = str(type(values))
                    if isinstance(values, (list, tuple)):
                        result["values_count"] = len(values)
                        if values:
                            first = values[0]
                            result["first_value_type"] = str(type(first))
                            if isinstance(first, dict):
                                result["first_value_keys"] = list(first.keys())
                                # Check for base camp ID or pal assignments
                                if "RawData" in first:
                                    raw = first["RawData"]
                                    if isinstance(raw, dict) and "value" in raw:
                                        raw_val = raw["value"]
                                        if isinstance(raw_val, dict):
                                            result["first_raw_keys"] = list(raw_val.keys())[:20]
                                            
                                # Check WorkAssignMap
                                if "WorkAssignMap" in first:
                                    wam = first["WorkAssignMap"]
                                    result["work_assign_map_type"] = str(type(wam))
                                    if isinstance(wam, dict):
                                        result["work_assign_map_keys"] = list(wam.keys())
                                        if "value" in wam:
                                            wam_val = wam["value"]
                                            result["work_assign_map_value_type"] = str(type(wam_val))
                                            if isinstance(wam_val, (list, tuple)):
                                                result["work_assign_count"] = len(wam_val)
                                                if wam_val:
                                                    result["first_assign"] = str(wam_val[0])[:200]
                        
                        # Find a work item with assignments
                        for work_item in values[:20]:
                            if isinstance(work_item, dict) and "WorkAssignMap" in work_item:
                                wam = work_item["WorkAssignMap"]
                                if isinstance(wam, dict) and "value" in wam:
                                    wam_val = wam["value"]
                                    if isinstance(wam_val, (list, tuple)) and len(wam_val) > 0:
                                        result["found_assigned_work"] = True
                                        result["assigned_count"] = len(wam_val)
                                        if wam_val:
                                            result["first_assigned_pal"] = str(wam_val[0])[:300]
                                        break
                
                # Check work_assign_map or similar
                for key in value.keys():
                    if "assign" in key.lower() or "worker" in key.lower():
                        assign_data = value[key]
                        result[f"{key}_type"] = str(type(assign_data))
                        if isinstance(assign_data, dict):
                            result[f"{key}_keys"] = list(assign_data.keys())
                            if "value" in assign_data:
                                result[f"{key}_value_type"] = str(type(assign_data["value"]))
                                if isinstance(assign_data["value"], list):
                                    result[f"{key}_count"] = len(assign_data["value"])
    
    return result

@app.get("/api/debug/base-assignments")
async def get_base_assignment_info():
    """Debug endpoint to see work assignments per base"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    work_data = parser.world_data.get("WorkSaveData", {})
    work_values = work_data.get("value", {}).get("values", [])
    
    base_assignments = {}
    
    for work_item in work_values:
        if not isinstance(work_item, dict):
            continue
        
        raw_data = work_item.get("RawData", {})
        if isinstance(raw_data, dict) and "value" in raw_data:
            raw_val = raw_data["value"]
            if isinstance(raw_val, dict):
                base_id = raw_val.get("base_camp_id_belong_to")
                if base_id:
                    if isinstance(base_id, dict):
                        base_id = base_id.get("value") or base_id.get("id")
                    base_id = str(base_id)
                    
                    work_assign_map = work_item.get("WorkAssignMap", {})
                    if isinstance(work_assign_map, dict):
                        assignments = work_assign_map.get("value", [])
                        if isinstance(assignments, (list, tuple)):
                            for assignment in assignments:
                                if isinstance(assignment, dict):
                                    assign_raw = assignment.get("value", {}).get("RawData", {})
                                    if isinstance(assign_raw, dict) and "value" in assign_raw:
                                        assign_val = assign_raw["value"]
                                        if isinstance(assign_val, dict):
                                            ind_id = assign_val.get("assigned_individual_id")
                                            if ind_id and isinstance(ind_id, dict):
                                                instance_id = ind_id.get("instance_id")
                                                if instance_id:
                                                    if isinstance(instance_id, dict):
                                                        instance_id = instance_id.get("value") or instance_id.get("id")
                                                    instance_id = str(instance_id)
                                                    
                                                    if base_id not in base_assignments:
                                                        base_assignments[base_id] = set()
                                                    base_assignments[base_id].add(instance_id)
    
    # Get base info
    bases = parser._get_base_data()
    base_info = {}
    for base_id, base_data in bases.items():
        guild_id = base_data.get("group_id_belong_to")
        if guild_id and isinstance(guild_id, dict):
            guild_id = guild_id.get("value") or guild_id.get("id")
        base_info[str(base_id)] = {
            "name": base_data.get("name", f"Base {str(base_id)[:8]}"),
            "guild_id": str(guild_id)[:8] if guild_id else None,
            "assigned_pals": len(base_assignments.get(str(base_id), set()))
        }
    
    return {
        "total_bases": len(bases),
        "bases_with_assignments": len([b for b in base_info.values() if b["assigned_pals"] > 0]),
        "base_details": base_info
    }

@app.get("/api/debug/world-data-keys")
async def get_world_data_keys():
    """Get all available keys in world data"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    keys_info = {}
    for key in parser.world_data.keys():
        val = parser.world_data[key]
        keys_info[key] = {
            "type": str(type(val)),
        }
        if isinstance(val, dict):
            keys_info[key]["keys"] = list(val.keys())
            if "value" in val:
                keys_info[key]["value_type"] = str(type(val["value"]))
                if isinstance(val["value"], (list, tuple)):
                    keys_info[key]["value_count"] = len(val["value"])
    
    return keys_info

@app.get("/api/debug/worker-director")
async def get_worker_director_info():
    """Debug endpoint to check WorkerDirector data in bases"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    base_camps = parser.world_data.get("BaseCampSaveData", {})
    bases_array = base_camps.get("value", [])
    
    result = {"bases": []}
    
    for base_entry in bases_array:
        if isinstance(base_entry, dict):
            # Get base ID from key
            key_data = base_entry.get("key")
            if isinstance(key_data, dict):
                base_id = key_data.get("value")
            else:
                base_id = str(key_data) if key_data else None
            
            base_info = {
                "id": str(base_id)[:16] if base_id else None,
            }
            
            # Get value data
            value_data = base_entry.get("value", {})
            if isinstance(value_data, dict):
                # Get name from RawData
                raw_data = value_data.get("RawData", {})
                if isinstance(raw_data, dict) and "value" in raw_data:
                    raw_val = raw_data["value"]
                    if isinstance(raw_val, dict):
                        name = raw_val.get("name")
                        if isinstance(name, dict):
                            name = name.get("value")
                        base_info["name"] = str(name) if name else None
                
                # Look for WorkerDirector
                worker_director = value_data.get("WorkerDirector", {})
                if isinstance(worker_director, dict) and "value" in worker_director:
                    wd_value = worker_director["value"]
                    if isinstance(wd_value, dict) and "RawData" in wd_value:
                        wd_raw = wd_value["RawData"]
                        if isinstance(wd_raw, dict) and "value" in wd_raw:
                            wd_raw_val = wd_raw["value"]
                            if isinstance(wd_raw_val, dict):
                                container_id = wd_raw_val.get("container_id")
                                if isinstance(container_id, dict):
                                    container_id = container_id.get("value") or container_id.get("id")
                                base_info["worker_container_id"] = str(container_id) if container_id else None
            
            result["bases"].append(base_info)
    
    return result

@app.get("/api/debug/guild-fields")
async def get_guild_fields():
    """Debug endpoint to see what fields guilds have for names"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    guild_save_param = parser.world_data.get("GroupSaveDataMap", {})
    guild_data = guild_save_param.get("value", [])
    
    result = {"guilds": []}
    for entry in guild_data[:3]:  # Look at first 3 guilds
        if isinstance(entry, dict):
            value_data = entry.get("value", {})
            if isinstance(value_data, dict):
                raw_data = value_data.get("RawData", {}).get("value", {})
                if isinstance(raw_data, dict):
                    group_type = raw_data.get("group_type")
                    if isinstance(group_type, dict):
                        group_type = group_type.get("value")
                    
                    # Only look at player guilds
                    if group_type == "EPalGroupType::Guild":
                        guild_info = {
                            "guild_id": str(entry.get("key"))[:16],
                            "all_fields": list(raw_data.keys())
                        }
                        
                        # Check different name field possibilities
                        for field in ["group_name", "guild_name", "name", "display_name"]:
                            if field in raw_data:
                                val = raw_data[field]
                                guild_info[f"{field}_type"] = str(type(val))
                                if isinstance(val, dict):
                                    guild_info[f"{field}_keys"] = list(val.keys())
                                    if "value" in val:
                                        guild_info[f"{field}_value"] = str(val["value"])[:100]
                                else:
                                    guild_info[f"{field}_direct"] = str(val)[:100]
                        
                        result["guilds"].append(guild_info)
    
    return result

@app.get("/api/debug/pal-container-fields")
async def get_pal_container_fields():
    """Debug endpoint to see what container fields pals have"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    char_save_param = parser.world_data.get("CharacterSaveParameterMap", {})
    char_data = char_save_param.get("value", [])
    
    # Look at first few non-player characters
    pals_checked = 0
    result = {"pals": []}
    
    for entry in char_data:
        if pals_checked >= 3:
            break
            
        if isinstance(entry, dict):
            value_data = entry.get("value", {})
            if isinstance(value_data, dict):
                raw_data = value_data.get("RawData", {}).get("value", {})
                if isinstance(raw_data, dict):
                    save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
                    if isinstance(save_param, dict):
                        # Skip players
                        is_player = save_param.get("IsPlayer", {})
                        if isinstance(is_player, dict):
                            is_player = is_player.get("value", False)
                        if is_player:
                            continue
                        
                        pals_checked += 1
                        
                        pal_info = {
                            "character_id": str(save_param.get("CharacterID", {}).get("value", "Unknown")),
                            "fields_with_container": []
                        }
                        
                        # Look for any field with "container" or "slot" in name
                        for key in save_param.keys():
                            if "container" in key.lower() or "slot" in key.lower():
                                val = save_param[key]
                                field_info = {
                                    "field": key,
                                    "type": str(type(val))
                                }
                                if isinstance(val, dict):
                                    if "value" in val:
                                        field_info["value"] = str(val["value"])[:50]
                                    else:
                                        field_info["keys"] = list(val.keys())
                                else:
                                    field_info["value"] = str(val)[:50]
                                pal_info["fields_with_container"].append(field_info)
                        
                        result["pals"].append(pal_info)
    
    return result

@app.get("/api/debug/pal-slot-structure")
async def get_pal_slot_structure():
    """Debug endpoint to see full SlotId structure"""
    if not parser.world_data:
        return {"error": "No world data"}
    
    char_save_param = parser.world_data.get("CharacterSaveParameterMap", {})
    char_data = char_save_param.get("value", [])
    
    # Look at one non-player character
    for entry in char_data:
        if isinstance(entry, dict):
            value_data = entry.get("value", {})
            if isinstance(value_data, dict):
                raw_data = value_data.get("RawData", {}).get("value", {})
                if isinstance(raw_data, dict):
                    save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
                    if isinstance(save_param, dict):
                        # Skip players
                        is_player = save_param.get("IsPlayer", {})
                        if isinstance(is_player, dict):
                            is_player = is_player.get("value", False)
                        if is_player:
                            continue
                        
                        # Get SlotId structure
                        slot_id = save_param.get("SlotId", {})
                        result = {
                            "character_id": str(save_param.get("CharacterID", {}).get("value", "Unknown")),
                            "slot_id_type": str(type(slot_id)),
                        }
                        
                        if isinstance(slot_id, dict):
                            result["slot_id_keys"] = list(slot_id.keys())
                            # Check the value field
                            slot_id_value = slot_id.get("value")
                            if slot_id_value:
                                result["slot_id_value_type"] = str(type(slot_id_value))
                                if isinstance(slot_id_value, dict):
                                    result["slot_id_value_keys"] = list(slot_id_value.keys())
                                    container_id = slot_id_value.get("ContainerId")
                                    if container_id:
                                        result["container_id_type"] = str(type(container_id))
                                        if isinstance(container_id, dict):
                                            result["container_id_keys"] = list(container_id.keys())
                                            cid_value = container_id.get("value")
                                            if cid_value:
                                                result["container_value_type"] = str(type(cid_value))
                                                if isinstance(cid_value, dict):
                                                    result["container_value_keys"] = list(cid_value.keys())
                                                    # Try ID field
                                                    cid_id = cid_value.get("ID")
                                                    if cid_id:
                                                        result["container_ID_type"] = str(type(cid_id))
                                                        if isinstance(cid_id, dict):
                                                            result["container_ID_keys"] = list(cid_id.keys())
                                                            result["container_ID_value"] = str(cid_id.get("value"))[:80]
                                                        else:
                                                            result["container_ID_value"] = str(cid_id)[:80]
                                                else:
                                                    result["container_value_direct"] = str(cid_value)[:80]
                        
                        return result
    
    return {"error": "No pals found"}

@app.get("/api/players", dependencies=[Depends(require_auth)])
async def get_players():
    """Get list of all players"""
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    
    try:
        players = parser.get_players()
        return {"players": players, "count": len(players)}
    except Exception as e:
        logger.error(f"Error getting players: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/guilds", dependencies=[Depends(require_auth)])
async def get_guilds():
    """Get list of all guilds"""
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    
    try:
        guilds = parser.get_guilds()
        return {"guilds": guilds, "count": len(guilds)}
    except Exception as e:
        logger.error(f"Error getting guilds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/base-containers", dependencies=[Depends(require_auth)])
async def get_base_containers():
    """Get base containers (food bowls, storage, etc.) grouped by base"""
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    
    try:
        containers_by_base = parser.get_base_containers()
        return {"containers": containers_by_base, "count": len(containers_by_base)}
    except Exception as e:
        logger.error(f"Error getting base containers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pals", dependencies=[Depends(require_auth)])
async def get_pals():
    """Get list of all pals"""
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    
    try:
        pals = parser.get_pals()
        return {"pals": pals, "count": len(pals)}
    except Exception as e:
        logger.error(f"Error getting pals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/player-mapping")
async def get_player_mapping():
    """Debug endpoint to show player UID mapping"""
    return {
        "player_uid_to_instance": parser.player_uid_to_instance,
        "player_names": parser.player_names,
        "total_mappings": len(parser.player_uid_to_instance)
    }
@app.get("/api/debug/player-data-structure")
async def get_player_data_structure():
    """Debug endpoint to examine raw player data structure"""
    if not parser.loaded:
        return {"error": "Not loaded"}
    
    players_data = parser._get_player_data()
    result = {
        "total_players": len(players_data),
        "players": []
    }
    
    for instance_id, char_info in list(players_data.items())[:2]:  # Show first 2 players
        player_info = {
            "instance_id": str(instance_id)[:8] + "...",
            "all_keys": list(char_info.keys()),
            "relevant_fields": {}
        }
        
        # Check for fields that might contain PlayerUId or owner info
        for key in ["PlayerUId", "NickName", "IsPlayer", "Level"]:
            if key in char_info:
                player_info["relevant_fields"][key] = char_info[key]
        
        result["players"].append(player_info)
    
    return result
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
