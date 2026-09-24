"""Relationship building between players, pals, and containers - schema-driven version"""
import logging
from pathlib import Path
from typing import Dict

from backend.parser.extractors.bases import BaseMeta
from backend.parser.extractors.players import extract_player_save_data
from backend.parser.utils.helpers import get_val
from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)


def build_player_mapping(players_data: Dict, guild_data: Dict, base_meta: Dict[str, BaseMeta],
                         players_dir: Path) -> tuple[Dict[str, Dict], Dict[str, str]]:
    """Build mapping from PlayerUId to player names and their containers
    
    Args:
        players_data: {instance_id: SaveParameter} for player characters (Level.sav)
        guild_data: extracted guild collection
        base_meta: base metadata from get_base_metadata()
        players_dir: Path to Players directory with .sav files
        
    Returns:
        Tuple of (player_uid_to_containers, player_names) dicts
    """
    player_uid_to_containers = {}
    player_names = {}
    
    logger.info(f"build_player_mapping: Found {len(players_data)} players in Level.sav")
    
    # Build temporary mapping of instance_id -> player name
    instance_to_name = {}
    for instance_id, char_info in players_data.items():
        player_name = get_val(char_info, "NickName", "Unknown")
        instance_to_name[str(instance_id)] = player_name
        logger.info(f"Player from Level.sav: {player_name} (instance_id: {instance_id[:16]}...)")
    
    guild_schema = SchemaManager.get("guilds.yaml")
    
    # Extract player save data from Players/*.sav files
    player_save_data = extract_player_save_data(players_dir)
    
    # Build mappings using extracted data
    for individual_id, save_info in player_save_data.items():
        player_uid = save_info["player_uid"]
        player_name = instance_to_name.get(individual_id, f"Player_{player_uid[:8].upper()}")
        
        player_uid_to_containers[player_uid] = {
            "name": player_name,
            "containers": save_info["containers"],
            "instance_id": individual_id,
            "location": save_info["location"],
            "party_container_id": save_info.get("party_container_id"),
            "details": save_info.get("details") or {},
        }
        player_names[player_uid] = player_name
        logger.debug(f"  -> {player_name}: PlayerUId={player_uid[:16]}..., {len(save_info['containers'])} containers, location={save_info['location'] is not None}")
    
    # Add base worker containers to player mappings
    guild_to_players = {}
    for guild_id, guild_info in guild_data.items():
        players = guild_schema.extract_field(guild_info, "players")
        if players:
            player_uids = [str(p.get("player_uid")) for p in players if isinstance(p, dict) and p.get("player_uid")]
            if player_uids:
                guild_to_players[str(guild_id)] = player_uids
    
    logger.info(f"Found {len(guild_to_players)} guilds with players")
    
    # Every member of a guild can see the guild's base worker containers
    for meta in base_meta.values():
        if not (meta.guild_id and meta.container_id):
            continue
        for player_uid in guild_to_players.get(meta.guild_id, []):
            if player_uid in player_uid_to_containers:
                player_uid_to_containers[player_uid]["containers"].append(meta.container_id)
    
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
    
    # Use schemas to get container data
    collections_schema = SchemaManager.get("collections.yaml")
    container_schema = SchemaManager.get("containers.yaml")
    containers = collections_schema.extract_collection(world_data, "containers")
    
    if not containers:
        logger.warning("No containers found")
        return pal_to_owner
    
    container_map = {}
    
    # Extract pal instance IDs from each container's slots
    for container_id, container_data in containers.items():
        slots = container_schema.extract_field(container_data, "slots")
        pal_ids = []
        
        for slot in slots:
            # Extract instance_id from slot using schema
            instance_id = container_schema.extract_field(slot, "slot_instance_id")
            
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
