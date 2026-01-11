"""Main API endpoints for game data"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends
import httpx

from backend.common.logging_config import get_logger
from backend.common.auth import require_auth
from backend.common.config import config
from backend.parser import parser

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/info", dependencies=[Depends(require_auth)])
async def get_save_info():
    """Get basic save file information"""
    return parser.get_save_info()


@router.get("/players", dependencies=[Depends(require_auth)])
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


@router.get("/guilds", dependencies=[Depends(require_auth)])
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


@router.get("/base-containers", dependencies=[Depends(require_auth)])
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


@router.get("/pals", dependencies=[Depends(require_auth)])
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


@router.get("/map-objects", dependencies=[Depends(require_auth)])
async def get_map_objects():
    """Get static map objects (alpha pals, fast travel points, etc.)"""
    try:
        map_objects = parser.data.map_objects
        
        # Enrich alpha pals with localized names
        alpha_pals = []
        for obj in map_objects:
            if obj.get('type') == 'alpha_pal':
                enriched = dict(obj)
                pal_id = obj.get('pal')
                if pal_id:
                    # Add localized name
                    enriched['pal_name'] = parser.data.pal_names.get(pal_id, pal_id)
                    # Level already comes from map_objects.json
                alpha_pals.append(enriched)
        
        # Fast travel points already have localized_name
        fast_travel = [obj for obj in map_objects if obj.get('type') == 'fast_travel']
        
        return {
            "alpha_pals": alpha_pals,
            "fast_travel": fast_travel,
            "total": len(map_objects)
        }
    except Exception as e:
        logger.error(f"Error getting map objects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rcon/status", dependencies=[Depends(require_auth)])
async def get_rcon_status():
    """Get RCON server information aggregated from multiple endpoints"""
    if not config.RCON_HOST or not config.RCON_PASSWORD:
        raise HTTPException(
            status_code=503, 
            detail="RCON is not configured. Set RCON_HOST, RCON_PORT, and RCON_PASSWORD environment variables."
        )
    
    base_url = f"http://{config.RCON_HOST}:{config.RCON_PORT}"
    # RCON API uses Basic Auth with username 'admin'
    auth = ("admin", config.RCON_PASSWORD)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Make all RCON API calls in parallel with Basic Auth
            info_task = client.get(f"{base_url}/v1/api/info", auth=auth)
            players_task = client.get(f"{base_url}/v1/api/players", auth=auth)
            settings_task = client.get(f"{base_url}/v1/api/settings", auth=auth)
            metrics_task = client.get(f"{base_url}/v1/api/metrics", auth=auth)
            
            # Wait for all responses
            info_response, players_response, settings_response, metrics_response = await asyncio.gather(
                info_task, players_task, settings_task, metrics_task,
                return_exceptions=True
            )
            
            result = {
                "info": None,
                "players": None,
                "settings": None,
                "metrics": None,
                "errors": {}
            }
            
            # Process info response
            if isinstance(info_response, Exception):
                result["errors"]["info"] = str(info_response)
            elif info_response.status_code == 200:
                result["info"] = info_response.json()
            else:
                result["errors"]["info"] = f"HTTP {info_response.status_code}"
            
            # Process players response
            if isinstance(players_response, Exception):
                result["errors"]["players"] = str(players_response)
            elif players_response.status_code == 200:
                result["players"] = players_response.json()
            else:
                result["errors"]["players"] = f"HTTP {players_response.status_code}"
            
            # Process settings response
            if isinstance(settings_response, Exception):
                result["errors"]["settings"] = str(settings_response)
            elif settings_response.status_code == 200:
                result["settings"] = settings_response.json()
            else:
                result["errors"]["settings"] = f"HTTP {settings_response.status_code}"
            
            # Process metrics response
            if isinstance(metrics_response, Exception):
                result["errors"]["metrics"] = str(metrics_response)
            elif metrics_response.status_code == 200:
                result["metrics"] = metrics_response.json()
            else:
                result["errors"]["metrics"] = f"HTTP {metrics_response.status_code}"
            
            return result
            
    except Exception as e:
        logger.error(f"Error fetching RCON data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to RCON server: {str(e)}")
