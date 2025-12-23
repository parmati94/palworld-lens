"""Player building from save data"""
import logging
from typing import List, Optional, Dict
import math

from backend.models.models import PlayerInfo
from backend.parser.extractors.characters import get_player_data
from backend.parser.extractors.guilds import get_guild_data
from backend.parser.utils.helpers import get_val
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# Stat name mappings (Chinese to English keys)
STAT_NAME_MAP = {
    "最大HP": "hp",
    "最大SP": "stamina",
    "攻撃力": "attack",
    "所持重量": "weight",
    "捕獲率": "capture",
    "作業速度": "work_speed"
}


def build_players(world_data: Dict) -> List[PlayerInfo]:
    """Build list of all players from save data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        List of PlayerInfo objects
    """
    players_data = get_player_data(world_data)
    players = []
    
    for instance_id, char_info in players_data.items():
        # Extract stat points
        stat_points = _extract_stat_points(char_info, "GotStatusPointList")
        ex_stat_points = _extract_stat_points(char_info, "GotExStatusPointList")
        
        # Get level
        level = get_val(char_info, "Level", 1)
        
        # Calculate stats
        calculated_stats = _calculate_player_stats(
            level=level,
            stat_points=stat_points,
            ex_stat_points=ex_stat_points
        )
        
        # Get current HP (FixedPoint64 format, divide by 1000)
        hp_data = char_info.get("Hp", {})
        if isinstance(hp_data, dict):
            hp_value = hp_data.get("Value", {})
            if isinstance(hp_value, dict):
                hp_value = hp_value.get("value", 0)
            elif isinstance(hp_value, (int, float)):
                pass
            else:
                hp_value = 0
        else:
            hp_value = hp_data if isinstance(hp_data, (int, float)) else 0
        
        current_hp = int(hp_value / 1000) if hp_value else calculated_stats["hp"]
        
        player = PlayerInfo(
            uid=instance_id,
            player_name=get_val(char_info, "NickName", "Unknown"),
            level=level,
            exp=get_val(char_info, "Exp", 0),
            hp=current_hp,
            max_hp=calculated_stats["hp"],
            mp=get_val(char_info, "MP"),
            max_mp=calculated_stats["stamina"],
            hunger=get_val(char_info, "FullStomach", 100.0),
            sanity=get_val(char_info, "SanityValue", 100.0),
            guild_id=_get_player_guild(world_data, instance_id),
            stat_points_hp=stat_points["hp"],
            stat_points_stamina=stat_points["stamina"],
            stat_points_attack=stat_points["attack"],
            stat_points_weight=stat_points["weight"],
            stat_points_capture=stat_points["capture"],
            stat_points_work_speed=stat_points["work_speed"],
            ex_stat_points_hp=ex_stat_points["hp"],
            ex_stat_points_stamina=ex_stat_points["stamina"],
            ex_stat_points_attack=ex_stat_points["attack"],
            ex_stat_points_weight=ex_stat_points["weight"],
            ex_stat_points_work_speed=ex_stat_points["work_speed"],
            calculated_max_hp=calculated_stats["hp"],
            calculated_stamina=calculated_stats["stamina"],
            calculated_attack=calculated_stats["attack"],
            calculated_weight=calculated_stats["weight"],
            calculated_work_speed=calculated_stats["work_speed"]
        )
        players.append(player)
    
    return players


def _extract_stat_points(char_info: Dict, field_name: str) -> Dict[str, int]:
    """Extract stat points from GotStatusPointList or GotExStatusPointList
    
    Args:
        char_info: Character save parameter dict
        field_name: Field name (GotStatusPointList or GotExStatusPointList)
        
    Returns:
        Dict mapping stat type to points allocated
    """
    result = {
        "hp": 0,
        "stamina": 0,
        "attack": 0,
        "weight": 0,
        "capture": 0,
        "work_speed": 0
    }
    
    stat_list = char_info.get(field_name, {})
    if not isinstance(stat_list, dict):
        return result
    
    # Navigate through the nested structure
    value_data = stat_list.get("value", {})
    if not isinstance(value_data, dict):
        return result
    
    values = value_data.get("values", [])
    if not isinstance(values, list):
        return result
    
    # Extract stat points from each entry
    for entry in values:
        if not isinstance(entry, dict):
            continue
        
        # Get stat name
        stat_name_data = entry.get("StatusName", {})
        if isinstance(stat_name_data, dict):
            stat_name = stat_name_data.get("value", "")
        else:
            stat_name = str(stat_name_data)
        
        # Get stat points
        stat_point_data = entry.get("StatusPoint", {})
        if isinstance(stat_point_data, dict):
            stat_points = stat_point_data.get("value", 0)
        else:
            stat_points = int(stat_point_data) if stat_point_data else 0
        
        # Map to our keys
        mapped_key = STAT_NAME_MAP.get(stat_name)
        if mapped_key and mapped_key in result:
            result[mapped_key] = stat_points
    
    return result


def _calculate_player_stats(level: int, stat_points: Dict[str, int], 
                            ex_stat_points: Dict[str, int]) -> Dict[str, int]:
    """Calculate player stats based on level and stat points
    
    Player stats formula (base values before equipment bonuses):
    - HP: 500 + (StatPoints × 100)
    - Stamina: 100 + (StatPoints × 10)
    - Attack: 100 + (StatPoints × 2)
    - Work Speed: 100 + (StatPoints × 50)
    - Weight: 300 + (StatPoints × 50)
    
    Note: Level does NOT provide automatic HP bonus. HP is purely based on stat points.
    
    Args:
        level: Player level (not used in calculation, kept for future compatibility)
        stat_points: Regular stat points from GotStatusPointList
        ex_stat_points: Extra stat points from GotExStatusPointList (statues/tech)
        
    Returns:
        Dict with calculated stat values
    """
    # Combine regular and extra stat points
    total_hp_points = stat_points["hp"] + ex_stat_points["hp"]
    total_stamina_points = stat_points["stamina"] + ex_stat_points["stamina"]
    total_attack_points = stat_points["attack"] + ex_stat_points["attack"]
    total_weight_points = stat_points["weight"] + ex_stat_points["weight"]
    total_work_points = stat_points["work_speed"] + ex_stat_points["work_speed"]
    
    # Calculate stats (armor modifier = 1.0 for now, as we don't have equipment data)
    # HP: 500 base + 100 per stat point (NO level bonus)
    calculated_hp = 500 + (total_hp_points * 100)
    
    # Stamina: 100 base + 10 per stat point
    calculated_stamina = 100 + (total_stamina_points * 10)
    
    # Attack: 100 base + 2 per stat point
    calculated_attack = 100 + (total_attack_points * 2)
    
    # Work Speed: 100 base + 50 per stat point
    calculated_work_speed = 100 + (total_work_points * 50)
    
    # Weight: 300 base + 50 per stat point
    calculated_weight = 300 + (total_weight_points * 50)
    
    return {
        "hp": calculated_hp,
        "stamina": calculated_stamina,
        "attack": calculated_attack,
        "work_speed": calculated_work_speed,
        "weight": calculated_weight
    }


def _get_player_guild(world_data: Dict, player_uid: str) -> Optional[str]:
    """Get the guild ID for a player
    
    Args:
        world_data: World save data from GVAS file
        player_uid: Player's character instance ID
        
    Returns:
        Guild ID string or None
    """
    guilds = get_guild_data(world_data)
    for guild_id, guild_info in guilds.items():
        group_type = get_val(guild_info, "group_type", "")
        if group_type != "EPalGroupType::Guild":
            continue
            
        members_data = guild_info.get("individual_character_handle_ids", [])
        if isinstance(members_data, list):
            for member in members_data:
                if isinstance(member, dict):
                    instance_id = member.get("instance_id")
                    if str(instance_id) == str(player_uid):
                        return str(guild_id)
    return None
