"""Extract data from individual Players/*.sav files"""
import logging
from pathlib import Path
from typing import Dict, Optional

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load schema
player_schema = SchemaManager.get("players.yaml")


def extract_player_save_data(players_dir: Path) -> Dict[str, Dict]:
    """Extract data from Players/*.sav files
    
    Args:
        players_dir: Path to Players directory with .sav files
        
    Returns:
        Dict mapping IndividualId (instance_id) to player save data including:
        - player_uid: PlayerUId from the .sav file
        - location: {x, y, z} coordinates from LastTransform
        - containers: List of container IDs
    """
    player_save_data = {}
    
    if not players_dir or not players_dir.exists():
        return player_save_data
    
    for player_sav in players_dir.glob("*.sav"):
        try:
            filename_uid = player_sav.stem
            if len(filename_uid) == 32:
                formatted_uid = f"{filename_uid[0:8]}-{filename_uid[8:12]}-{filename_uid[12:16]}-{filename_uid[16:20]}-{filename_uid[20:32]}"
                formatted_uid = formatted_uid.lower()
                
                with open(player_sav, "rb") as f:
                    sav_data = f.read()
                
                raw_gvas, _ = decompress_sav_to_gvas(sav_data)
                gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
                
                # Navigate to SaveData.value (the "root" for Players/*.sav fields)
                save_data = gvas_file.properties.get("SaveData", {}).get("value", {})
                
                # Extract PlayerUId
                player_uid = player_schema.extract_field(save_data, "PlayerUId")
                if not player_uid:
                    player_uid = formatted_uid
                player_uid = str(player_uid)
                
                # Get IndividualId (links to Level.sav character instance)
                individual_id = player_schema.extract_field(save_data, "IndividualId")
                if not individual_id:
                    logger.warning(f"No IndividualId found in {player_sav.name}")
                    continue
                individual_id = str(individual_id)
                
                # Extract location from LastTransform
                location = None
                last_transform = player_schema.extract_field(save_data, "LastTransform")
                if last_transform and isinstance(last_transform, dict):
                    x = last_transform.get("x")
                    y = last_transform.get("y")
                    z = last_transform.get("z")
                    if x is not None and y is not None:
                        location = {"x": float(x), "y": float(y), "z": float(z) if z is not None else 0.0}
                
                # Get container IDs
                container_ids = []
                otomo_container = player_schema.extract_field(save_data, "OtomoCharacterContainerId")
                if otomo_container:
                    container_ids.append(str(otomo_container))
                
                storage_container = player_schema.extract_field(save_data, "PalStorageContainerId")
                if storage_container:
                    container_ids.append(str(storage_container))
                
                player_save_data[individual_id] = {
                    "player_uid": player_uid,
                    "location": location,
                    "containers": container_ids,
                    "party_container_id": str(otomo_container) if otomo_container else None,
                    "details": extract_player_details(save_data),
                }
                
                logger.debug(f"Extracted player save data: individual_id={individual_id[:16]}..., location={location is not None}, containers={len(container_ids)}")
                
        except Exception as e:
            logger.warning(f"Failed to read player .sav {player_sav.name}: {e}")
    
    return player_save_data


# .NET ticks are 100 ns since 0001-01-01; this many of them fall before the Unix epoch
_UNIX_EPOCH_TICKS = 621355968000000000


def net_ticks_to_iso(ticks) -> Optional[str]:
    """LastOnlineDateTime (.NET ticks, UTC; the last login, not logout) -> ISO 8601, or None when unset."""
    if not isinstance(ticks, (int, float)) or ticks <= _UNIX_EPOCH_TICKS:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp((ticks - _UNIX_EPOCH_TICKS) / 10_000_000, tz=timezone.utc).isoformat()


def _map_size(entries) -> int:
    """Entries in a save MapProperty ([{key, value}] once parsed) with a truthy value."""
    return sum(1 for e in (entries or []) if isinstance(e, dict) and e.get("value"))


def _map_sum(entries) -> int:
    return sum(int(e.get("value") or 0) for e in (entries or []) if isinstance(e, dict))


def extract_player_details(save_data: Dict) -> Dict:
    """The rest of a Players/*.sav worth showing: the player's item containers, tech tree
    standing, records and last login. Container ids resolve in Level.sav's item index."""
    f = player_schema.extract_field
    cid = lambda name: (str(f(save_data, name)) if f(save_data, name) else None)
    return {
        "containers": {
            "bag": cid("CommonContainerId"),
            "key_items": cid("EssentialContainerId"),
            "weapons": cid("WeaponLoadOutContainerId"),
            "gear": cid("PlayerEquipArmorContainerId"),
            "food": cid("FoodEquipContainerId"),
        },
        "tech": {
            "unlocked": len(f(save_data, "UnlockedRecipeTechnologyNames") or []),
            "points": int(f(save_data, "TechnologyPoint") or 0),
            "ancient_points": int(f(save_data, "bossTechnologyPoint") or 0),
        },
        "records": {
            "towers": _map_size(f(save_data, "TowerBossDefeatFlag")),
            "alphas": _map_size(f(save_data, "NormalBossDefeatFlag")),
            "paldeck": _map_size(f(save_data, "PaldeckUnlockFlag")),
            "caught": _map_sum(f(save_data, "PalCaptureCount")),
            "fast_travels": _map_size(f(save_data, "FastTravelPointUnlockFlag")),
            "dungeons": int(f(save_data, "NormalDungeonClearCount") or 0) + int(f(save_data, "FixedDungeonClearCount") or 0),
        },
        "last_online": net_ticks_to_iso(f(save_data, "LastOnlineDateTime")),
    }
