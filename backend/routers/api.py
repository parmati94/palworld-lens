"""Main API endpoints for game data"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends
import httpx

from backend.common.logging_config import get_logger
from backend.common.auth import require_auth
from backend.common.config import config
from backend.common import pal_icons
from backend.common import online
from backend.common import item_detail
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
        players = await online.with_online(parser.get_players())
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
        return parser.base_containers_payload()
    except Exception as e:
        logger.error(f"Error getting base containers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity", dependencies=[Depends(require_auth)])
async def get_activity():
    """What every base is doing: machines, crops, incubators, stations, plus each guild's expeditions and lab."""
    if not parser.loaded:
        raise HTTPException(status_code=400, detail="No save file loaded")
    try:
        return parser.activity_payload()
    except Exception as e:
        logger.error(f"Error getting activity: {e}")
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


@router.get("/game-data", dependencies=[Depends(require_auth)])
async def get_game_data():
    """Static reference data the UI keys ids on: elements, work types, conditions, map layers."""
    return parser.data.reference()


@router.get("/items/{item_id}", dependencies=[Depends(require_auth)])
async def get_item(item_id: str):
    """One item described for the popup: name, description, category, weight, gear stats, schematic."""
    info = item_detail.describe_item(item_id, parser.data)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown item")
    return info


@router.get("/map-objects", dependencies=[Depends(require_auth)])
async def get_map_objects():
    """Static map markers (fast travel, alpha pals, predators, dungeons).

    Pal markers are enriched with the localized species name and the same
    icon candidate list the pals tab uses (backend/common/pal_icons.py), so
    the map never derives an icon name on its own.
    """
    objects = []
    for obj in parser.data.map_objects:
        out = dict(obj)
        pal_id = obj.get("pal")
        if pal_id:
            species = parser.data.species.resolve(pal_id)
            out["pal_name"] = parser.data.pal_name(species) if species else pal_id
            out["image_candidates"] = pal_icons.icon_candidates(pal_id)
        objects.append(out)
    return {"objects": objects, "total": len(objects)}


@router.get("/spawns", dependencies=[Depends(require_auth)])
async def get_spawns():
    """Wild spawner groups (data/json/spawns.json) plus the species that appear in them.

    `groups` is the generated file as-is: {name: {kind, radius, points: {layer:
    [[x, y]]}, pals: {species: {share, level, time?, boss?}}}}. `species` is
    the search list for the map: every id that spawns somewhere, with the same
    name and icon candidates the pals tab uses, so the map derives nothing.
    """
    data = parser.data
    groups = data.spawns
    by_species = {}
    for name, g in groups.items():
        for sid in g.get("pals", {}):
            by_species.setdefault(sid, []).append(name)
    species = []
    for sid, names in by_species.items():
        row = data.pals.get(sid) or {}
        species.append({
            "id": sid,
            "name": data.pal_name(sid) if sid in data.pals else sid,
            "image_candidates": pal_icons.icon_candidates(sid),
            "element_types": row.get("element_types") or [],
            "groups": names,
        })
    species.sort(key=lambda s: s["name"].lower())
    return {"groups": groups, "species": species, "total": len(species)}


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
