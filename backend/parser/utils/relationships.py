"""Relationship building between players, pals, and containers - schema-driven version"""
import logging
from pathlib import Path
from typing import Dict

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.parser.extractors.characters import get_player_data
from backend.parser.extractors.guilds import get_guild_data
from backend.parser.extractors.bases import get_base_data
from backend.parser.utils.helpers import get_val
from backend.parser.utils.schema_loader import SchemaLoader
from backend.common.logging_config import get_logger

logger = get_logger(__name__)


def build_player_mapping(world_data: Dict, players_dir: Path) -> tuple[Dict[str, Dict], Dict[str, str]]:
    """Build mapping from PlayerUId to player names and their containers
    
    Args:
        world_data: World save data from GVAS file
        players_dir: Path to Players directory with .sav files
        
    Returns:
        Tuple of (player_uid_to_containers, player_names) dicts
    """
    player_uid_to_containers = {}
    player_names = {}
    
    # Get players from Level.sav first
    players_data = get_player_data(world_data)
    logger.info(f"build_player_mapping: Found {len(players_data)} players in Level.sav")
    
    # Build temporary mapping of instance_id -> player name
    instance_to_name = {}
    for instance_id, char_info in players_data.items():
        player_name = get_val(char_info, "NickName", "Unknown")
        instance_to_name[str(instance_id)] = player_name
        logger.info(f"Player from Level.sav: {player_name} (instance_id: {instance_id[:16]}...)")
    
    # Load schema for player data extraction (works for both Level.sav and Players/*.sav)
    player_schema = SchemaLoader("players.yaml")
    
    # Read Players/*.sav files to get PlayerUId and container IDs
    if players_dir and players_dir.exists():
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
                    
                    # Extract using schema (field names are top-level keys in save_data)
                    player_uid = player_schema.extract_field(save_data, "PlayerUId")
                    if not player_uid:
                        player_uid = formatted_uid
                    player_uid = str(player_uid)
                    
                    # Get IndividualId (links to Level.sav character instance)
                    individual_id = player_schema.extract_field(save_data, "IndividualId")
                    if individual_id:
                        individual_id = str(individual_id)
                    
                    player_name = instance_to_name.get(individual_id, f"Player_{filename_uid[:8].upper()}")
                    
                    # Get container IDs using schema
                    container_ids = []
                    otomo_container = player_schema.extract_field(save_data, "OtomoCharacterContainerId")
                    if otomo_container:
                        container_ids.append(str(otomo_container))
                    
                    storage_container = player_schema.extract_field(save_data, "PalStorageContainerId")
                    if storage_container:
                        container_ids.append(str(storage_container))
                    
                    player_uid_to_containers[player_uid] = {
                        "name": player_name,
                        "containers": container_ids,
                        "instance_id": individual_id
                    }
                    player_names[player_uid] = player_name
                    logger.debug(f"  -> {player_name}: PlayerUId={player_uid[:16]}..., {len(container_ids)} containers")
            except Exception as e:
                logger.warning(f"Failed to read player .sav {player_sav.name}: {e}")
    
    # Add base worker containers to player mappings
    guild_to_players = {}
    guild_data = get_guild_data(world_data)
    
    for guild_id, guild_info in guild_data.items():
        # Extract player UIDs from guild
        players = guild_info.get("players", [])
        if players:
            player_uids = [str(p.get("player_uid")) for p in players if isinstance(p, dict) and p.get("player_uid")]
            if player_uids:
                guild_to_players[str(guild_id)] = player_uids
    
    logger.info(f"Found {len(guild_to_players)} guilds with players")
    
    # Process base camps and link to players through guilds
    base_data = get_base_data(world_data)
    logger.info(f"Checking {len(base_data)} base camps for worker containers")
    
    for base_id, base_info in base_data.items():
        # Extract guild ID and container ID  
        # Note: Can't use schema here because fields aren't top-level keys in base_info
        raw_val = base_info.get("RawData", {}).get("value", {})
        guild_id = raw_val.get("group_id_belong_to")
        
        if guild_id:
            guild_id_str = str(guild_id)
            
            # Extract worker container ID
            container_id = base_info.get("WorkerDirector", {}).get("value", {}).get("RawData", {}).get("value", {}).get("container_id")
            
            if container_id:
                container_id_str = str(container_id)
                
                player_uids = guild_to_players.get(guild_id_str, [])
                for player_uid in player_uids:
                    if player_uid in player_uid_to_containers:
                        player_uid_to_containers[player_uid]["containers"].append(container_id_str)
                        player_name = player_uid_to_containers[player_uid]["name"]
                        logger.debug(f"  -> Added base worker container for {player_name}")
    
    logger.info(f"Mapped {len(player_names)} players with containers")
    return player_uid_to_containers, player_names


def build_pal_ownership(world_data: Dict, player_uid_to_containers: Dict) -> Dict[str, str]:
    """Build mapping from pal instance_id to owner
    
    Args:
        world_data: World save data from GVAS file
        player_uid_to_containers: Mapping of player UIDs to their container info
        
    Returns:
        Dict mapping pal instance_id to player name
    """
    pal_to_owner = {}
    
    # Use schema to get container data
    schema = SchemaLoader("collections.yaml")
    containers = schema.extract_collection(world_data, "containers")
    
    if not containers:
        logger.warning("No containers found")
        return pal_to_owner
    
    container_map = {}
    
    # Extract pal instance IDs from each container's slots
    for container_id, container_data in containers.items():
        slots = container_data.get("Slots", {}).get("value", {}).get("values", [])
        pal_ids = []
        
        for slot in slots:
            # Navigate to instance_id in slot
            instance_id = slot.get("RawData", {}).get("value", {}).get("instance_id")
            
            if instance_id and '00000000-0000-0000-0000-000000000000' not in str(instance_id):
                pal_ids.append(str(instance_id))
        
        # Always add to container_map, even if empty (to track player containers)
        container_map[container_id] = pal_ids
    
    logger.debug(f"Found {len(container_map)} containers with pals")
    logger.debug(f"Container map has {sum(len(v) for v in container_map.values())} total pal slots")
    logger.debug(f"Container IDs in map: {list(container_map.keys())[:5]}...")  # First 5 IDs
    
    # Map pals to players
    for player_uid, player_data in player_uid_to_containers.items():
        player_name = player_data["name"]
        player_containers = player_data["containers"]
        pal_count = 0
        
        logger.debug(f"Player {player_name} has containers: {player_containers}")
        
        for container_id in player_containers:
            if container_id in container_map:
                for pal_id in container_map[container_id]:
                    pal_to_owner[pal_id] = player_name
                    pal_count += 1
            else:
                logger.debug(f"  Container {container_id} not found in container_map")
        
        logger.debug(f"Player {player_name}: {pal_count} pals in {len(player_containers)} containers")
    
    logger.info(f"Loaded {len(pal_to_owner)} pals across all players")
    return pal_to_owner
