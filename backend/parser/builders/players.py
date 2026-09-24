"""Player building from save data"""
import logging
from typing import List, Optional, Dict
import math

from backend.common.loadout import enhance_stats, food_effects, shield_max
from backend.models.models import FoodBuff, PlayerInfo, PlayerRecords, PlayerTech, StatLine
from backend.parser.utils.mappers import item_ref, pal_ref
from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load YAML schema
player_schema = SchemaManager.get("players.yaml")

# Stat name mappings (Chinese to English keys)
STAT_NAME_MAP = {
    "最大HP": "hp",
    "最大SP": "stamina",
    "攻撃力": "attack",
    "所持重量": "weight",
    "捕獲率": "capture",
    "作業速度": "work_speed"
}


def build_players(players_data: Dict, guilds_data: Dict, player_uid_to_containers: Dict = None,
                  item_index: Dict = None, data=None, pals: List = None, container_sizes: Dict = None) -> List[PlayerInfo]:
    """Build list of all players from save data
    
    Args:
        players_data: Extracted player data from get_player_data()
        guilds_data: Extracted guild data from get_guild_data()
        player_uid_to_containers: Mapping of player UID to container and location data
        item_index: {container_id: [{static_id, count}]} from Level.sav, for what the player carries
        data: static game data (item names, icons)
        pals: the built PalInfo list, for the party
        container_sizes: {container_id: slot count}, for the bag's size
        
    Returns:
        List of PlayerInfo objects
    """
    players = []
    
    for instance_id, char_info in players_data.items():
        # Extract stat points using YAML schema
        stat_points = _extract_stat_points(char_info, "GotStatusPointList")
        ex_stat_points = _extract_stat_points(char_info, "GotExStatusPointList")
        
        # Extract fields using YAML schema
        level = player_schema.extract_field(char_info, "Level")
        
        # Calculate stats
        calculated_stats = _calculate_player_stats(
            level=level,
            stat_points=stat_points,
            ex_stat_points=ex_stat_points
        )
        
        # Get location from player_uid_to_containers (from Players/*.sav LastTransform)
        location = None
        save_info = {}
        if player_uid_to_containers:
            for player_uid, player_data in player_uid_to_containers.items():
                if player_data.get("instance_id") == instance_id:
                    location = player_data.get("location")
                    save_info = player_data
                    break
        details = save_info.get("details") or {}
        kit = _kit(details.get("containers") or {}, item_index or {}, data, container_sizes or {})

        # The status screen: base from level + points, then what the worn gear and the running dish add
        food_id = player_schema.extract_field(char_info, "FoodWithStatusEffect")
        food_id = str(food_id) if food_id and str(food_id) != "None" else None
        gear_ids = [i.item_id for i in kit["gear"]]
        loadout = getattr(data, "loadout", None) or {}
        stats = {k: StatLine(**v) for k, v in enhance_stats(
            {**calculated_stats, "defense": (loadout.get("player_base") or {}).get("defense", 100)},
            gear_ids, food_id, loadout, getattr(data, "passive_skills", None) or {}).items()}

        # HP - the save's current HP against the enhanced max (gear adds HP, so the base alone would clamp it)
        current_hp = player_schema.extract_field(char_info, "Hp")
        max_hp = stats["hp"].total
        if not current_hp or current_hp > max_hp:
            current_hp = max_hp
        food_buff = None
        if food_id:
            dish = data.item(food_id) if data is not None else {}
            secs = player_schema.extract_field(char_info, "FoodEffectSecondsLeft")
            food_buff = FoodBuff(item_id=food_id, item_name=dish.get("localized_name") or food_id, icon=dish.get("icon"),
                                 seconds_left=int(secs) if isinstance(secs, int) else None,
                                 effects=food_effects(food_id, loadout))
        
        player = PlayerInfo(
            uid=instance_id,
            player_name=player_schema.extract_field(char_info, "NickName"),
            level=level,
            exp=player_schema.extract_field(char_info, "Exp"),
            hp=current_hp,
            max_hp=max_hp,
            mp=player_schema.extract_field(char_info, "MP"),
            max_mp=calculated_stats["stamina"],
            hunger=player_schema.extract_field(char_info, "FullStomach"),
            sanity=player_schema.extract_field(char_info, "SanityValue"),
            guild_id=_get_player_guild(guilds_data, instance_id),
            location=location,
            last_online=details.get("last_online"),
            party=_party(save_info.get("party_container_id"), pals or []),
            gear=kit["gear"],
            weapons=kit["weapons"],
            food=kit["food"],
            bag=kit["bag"],
            bag_slots=kit["bag_slots"],
            weapon_slots=kit["weapon_slots"],
            food_slots=kit["food_slots"],
            key_items=kit["key_items"],
            gold=kit["gold"],
            carried_weight=kit["carried_weight"],
            tech=PlayerTech(**details["tech"]) if details.get("tech") else None,
            records=PlayerRecords(**details["records"]) if details.get("records") else None,
            stats=stats,
            shield_hp=int(player_schema.extract_field(char_info, "ShieldHP") or 0),
            shield_max=shield_max(gear_ids, loadout),
            food_buff=food_buff,
            unspent_points=int(player_schema.extract_field(char_info, "UnusedStatusPoint") or 0),
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


def _party(container_id: Optional[str], pals: List) -> List:
    """The pals riding in this party container, in slot order."""
    if not container_id:
        return []
    riders = [p for p in pals if getattr(p, "container_id", None) == container_id]
    riders.sort(key=lambda p: (p.slot_index is None, p.slot_index or 0))
    return [pal_ref(p) for p in riders]


GOLD = "Money"


def _kit(containers: Dict[str, Optional[str]], item_index: Dict, data, container_sizes: Dict = None) -> Dict:
    """What the player carries, as item tiles per container, plus the bag's size, the gold (also
    totalled on its own, the way the game prints it under the grid) and the weight of all of it."""
    out: Dict = {"gear": [], "weapons": [], "food": [], "bag": [], "key_items": [], "bag_slots": 0, "weapon_slots": 0,
                 "food_slots": 0, "gold": 0, "carried_weight": 0.0}
    if data is None:
        return out
    weight = 0.0
    for role in ("gear", "weapons", "food", "bag", "key_items"):
        for entry in item_index.get(containers.get(role) or "", []):
            item_id, count = entry["static_id"], entry["count"]
            weight += float(data.item(item_id).get("weight") or 0) * count
            if role == "bag" and item_id == GOLD:
                out["gold"] += count          # totalled here; the coin tile stays in the grid, as in the game
            ref = item_ref(item_id, data, count)
            ref.slot_index = entry.get("slot")
            out[role].append(ref)
    for role, key in (("bag", "bag_slots"), ("weapons", "weapon_slots"), ("food", "food_slots")):
        out[key] = int((container_sizes or {}).get(containers.get(role) or "", 0) or 0)
    out["carried_weight"] = round(weight, 1)
    return out


def _extract_stat_points(char_info: Dict, field_name: str) -> Dict[str, int]:
    """Extract stat points from GotStatusPointList or GotExStatusPointList using YAML schema
    
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
    
    # Use YAML schema to extract structured list
    stat_entries = player_schema.extract_list(char_info, field_name)
    
    for entry in stat_entries:
        stat_name = entry.get("stat_name", "")
        stat_points = entry.get("stat_points", 0)
        
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
        ex_stat_points: Extra stat points from elixirs (GotExStatusPointList)
        
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


def _get_player_guild(guilds_data: Dict, player_uid: str) -> Optional[str]:
    """Get the guild ID for a player
    
    Args:
        guilds_data: Extracted guild data from get_guild_data()
        player_uid: Player's character instance ID
        
    Returns:
        Guild ID string or None
    """
    for guild_id, guild_info in guilds_data.items():
        # Extract group_type manually since we don't have guild schema loaded here
        group_type_data = guild_info.get("group_type", {})
        if isinstance(group_type_data, dict):
            group_type = group_type_data.get("value", "")
        else:
            group_type = str(group_type_data)
            
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
