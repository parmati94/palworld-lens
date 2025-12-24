"""Relationship building between players, pals, and containers"""
import logging
from pathlib import Path
from typing import Dict

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.parser.extractors.characters import get_player_data
from backend.parser.utils.helpers import get_val
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
                    
                    save_data = gvas_file.properties.get("SaveData", {})
                    if isinstance(save_data, dict):
                        save_val = save_data.get("value", {})
                        if isinstance(save_val, dict):
                            # Get PlayerUId
                            player_uid = formatted_uid
                            player_uid_data = save_val.get("PlayerUId", {})
                            if isinstance(player_uid_data, dict) and "value" in player_uid_data:
                                player_uid = str(player_uid_data["value"])
                            
                            # Get IndividualId to match with Level.sav
                            individual_id = None
                            ind_id_data = save_val.get("IndividualId", {})
                            if isinstance(ind_id_data, dict) and "value" in ind_id_data:
                                ind_val = ind_id_data["value"]
                                if isinstance(ind_val, dict) and "InstanceId" in ind_val:
                                    inst_id_data = ind_val["InstanceId"]
                                    if isinstance(inst_id_data, dict) and "value" in inst_id_data:
                                        individual_id = str(inst_id_data["value"])
                            
                            player_name = instance_to_name.get(individual_id, f"Player_{filename_uid[:8].upper()}")
                            
                            # Get container IDs
                            container_ids = []
                            for field in ["OtomoCharacterContainerId", "PalStorageContainerId"]:
                                if field in save_val:
                                    cont_data = save_val[field]
                                    if isinstance(cont_data, dict) and "value" in cont_data:
                                        cont_val = cont_data["value"]
                                        if isinstance(cont_val, dict) and "ID" in cont_val:
                                            id_data = cont_val["ID"]
                                            if isinstance(id_data, dict) and "value" in id_data:
                                                container_ids.append(str(id_data["value"]))
                            
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
    guild_data = world_data.get("GroupSaveDataMap", {})
    if isinstance(guild_data, dict):
        guilds = guild_data.get("value", [])
        for guild in guilds:
            if isinstance(guild, dict):
                guild_id = guild.get("key")
                value = guild.get("value", {})
                if isinstance(value, dict):
                    raw_data = value.get("RawData", {})
                    if isinstance(raw_data, dict):
                        raw_val = raw_data.get("value", {})
                        if isinstance(raw_val, dict):
                            players = raw_val.get("players", [])
                            if players and guild_id:
                                player_uids = []
                                for player in players:
                                    if isinstance(player, dict):
                                        player_uid = player.get("player_uid")
                                        if player_uid:
                                            player_uids.append(str(player_uid))
                                if player_uids:
                                    guild_to_players[str(guild_id)] = player_uids
    
    logger.info(f"Found {len(guild_to_players)} guilds with players")
    
    # Process base camps and link to players through guilds
    base_camp_data = world_data.get("BaseCampSaveData", {})
    if isinstance(base_camp_data, dict):
        base_camps = base_camp_data.get("value", [])
        logger.info(f"Checking {len(base_camps)} base camps for worker containers")
        
        for base in base_camps:
            if isinstance(base, dict):
                value = base.get("value", {})
                if isinstance(value, dict):
                    raw_data = value.get("RawData", {})
                    if isinstance(raw_data, dict):
                        raw_val = raw_data.get("value", {})
                        if isinstance(raw_val, dict):
                            guild_id = raw_val.get("group_id_belong_to")
                            if guild_id:
                                guild_id_str = str(guild_id)
                                
                                worker_dir = value.get("WorkerDirector", {})
                                if isinstance(worker_dir, dict):
                                    wd_val = worker_dir.get("value", {})
                                    if isinstance(wd_val, dict):
                                        wd_raw = wd_val.get("RawData", {})
                                        if isinstance(wd_raw, dict):
                                            wd_raw_val = wd_raw.get("value", {})
                                            if isinstance(wd_raw_val, dict):
                                                container_id = wd_raw_val.get("container_id")
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
    
    char_container_data = world_data.get("CharacterContainerSaveData", {})
    if not isinstance(char_container_data, dict):
        logger.warning("CharacterContainerSaveData not found")
        return pal_to_owner
    
    containers = char_container_data.get("value", [])
    container_map = {}
    
    # Build container ID to pal instance IDs mapping
    for container in containers:
        if not isinstance(container, dict):
            continue
        
        key_data = container.get("key", {})
        if isinstance(key_data, dict) and "ID" in key_data:
            container_id_data = key_data["ID"]
            if isinstance(container_id_data, dict) and "value" in container_id_data:
                container_id = str(container_id_data["value"])
                
                value_data = container.get("value", {})
                if isinstance(value_data, dict):
                    slots_data = value_data.get("Slots", {})
                    if isinstance(slots_data, dict):
                        slots_value = slots_data.get("value", {})
                        if isinstance(slots_value, dict):
                            slots = slots_value.get("values", [])
                            pal_ids = []
                            for slot in slots:
                                if isinstance(slot, dict) and "RawData" in slot:
                                    slot_raw = slot["RawData"]
                                    if isinstance(slot_raw, dict) and "value" in slot_raw:
                                        slot_val = slot_raw["value"]
                                        if isinstance(slot_val, dict) and "instance_id" in slot_val:
                                            pal_instance_id = str(slot_val["instance_id"])
                                            if pal_instance_id and '00000000-0000-0000-0000-000000000000' not in pal_instance_id:
                                                pal_ids.append(pal_instance_id)
                            if pal_ids:
                                container_map[container_id] = pal_ids
    
    logger.debug(f"Found {len(container_map)} containers with pals")
    
    # Map pals to players
    for player_uid, player_data in player_uid_to_containers.items():
        player_name = player_data["name"]
        player_containers = player_data["containers"]
        pal_count = 0
        
        for container_id in player_containers:
            if container_id in container_map:
                for pal_id in container_map[container_id]:
                    pal_to_owner[pal_id] = player_name
                    pal_count += 1
        
        logger.debug(f"Player {player_name}: {pal_count} pals in {len(player_containers)} containers")
    
    logger.info(f"Loaded {len(pal_to_owner)} pals across all players")
    return pal_to_owner
