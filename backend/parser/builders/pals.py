"""Pal building from save data"""
import logging
from typing import List, Dict

from backend.core.enums import EPalGenderType, EPalBaseCampWorkerSickType, EPalStatusHungerType
from backend.models.models import PalInfo
from backend.parser.utils.mappers import (
    map_element_display_names,
    map_work_suitability_names,
    map_active_skills,
    map_passive_skills
)
from backend.parser.extractors.characters import get_character_data
from backend.parser.extractors.bases import get_base_assignments
from backend.parser.utils.helpers import get_val
from backend.parser.core.data_loader import DataLoader
from backend.parser.utils.stats import calculate_pal_stats
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


def _extract_hp(char_info: Dict, key: str, default: float = 100) -> int:
    """Extract HP value from save data and convert from milli-HP to actual HP
    
    HP is stored as FixedPoint64 (milli-HP, scaled by 1000).
    Full structure: {'value': {'Value': {'value': 582000}}} -> 582 HP
    
    Args:
        char_info: Character save parameter dict
        key: Key to extract (Hp)
        default: Default value if not found
        
    Returns:
        Actual HP value (divided by 1000)
    """
    hp_data = char_info.get(key)
    if hp_data is None:
        logger.debug(f"HP field '{key}' not found in char_info")
        return default
    
    # Handle nested structure: {'value': {'Value': {'value': 582000}}}
    if isinstance(hp_data, dict):
        # First check for 'value' key at top level
        if "value" in hp_data:
            value_wrapper = hp_data["value"]
            if isinstance(value_wrapper, dict) and "Value" in value_wrapper:
                value_data = value_wrapper["Value"]
                if isinstance(value_data, dict) and "value" in value_data:
                    milli_hp = value_data["value"]
                    # Convert from milli-HP to actual HP
                    actual_hp = int(milli_hp / 1000) if isinstance(milli_hp, (int, float)) else default
                    logger.info(f"✓ Extracted {key}: {milli_hp} milli-HP -> {actual_hp} HP")
                    return actual_hp
        # Fallback: check for 'Value' directly (simpler structure)
        elif "Value" in hp_data:
            value_data = hp_data["Value"]
            if isinstance(value_data, dict) and "value" in value_data:
                milli_hp = value_data["value"]
                actual_hp = int(milli_hp / 1000) if isinstance(milli_hp, (int, float)) else default
                logger.info(f"✓ Extracted {key}: {milli_hp} milli-HP -> {actual_hp} HP")
                return actual_hp
    
    # Final fallback to get_val
    val = get_val(char_info, key, default)
    if isinstance(val, (int, float)):
        # If it's a large number, assume it's milli-HP
        if val > 10000:
            logger.info(f"✓ Extracted {key} via get_val: {val} -> {int(val / 1000)} HP")
            return int(val / 1000)
        return int(val)
    
    logger.warning(f"HP extraction failed for {key}, returning default {default}")
    return default


def build_pals(world_data: Dict, data_loader: DataLoader, pal_to_owner: Dict[str, str]) -> List[PalInfo]:
    """Build list of all pals from save data
    
    Args:
        world_data: World save data from GVAS file
        data_loader: Data loader with localization mappings
        pal_to_owner: Mapping of pal instance_id to owner name
        
    Returns:
        List of PalInfo objects
    """
    base_assignments = get_base_assignments(world_data)
    char_data = get_character_data(world_data)
    pals = []
    
    for instance_id, char_info in char_data.items():
        # Skip players
        is_player = get_val(char_info, "IsPlayer", False)
        if is_player:
            continue
        
        char_id = get_val(char_info, "CharacterID", "Unknown")
        
        # Get friendly name - handle BOSS_ and Boss_ prefix
        lookup_id = char_id
        if char_id.startswith("BOSS_"):
            lookup_id = char_id[5:]  # Remove "BOSS_"
        elif char_id.startswith("Boss_"):
            lookup_id = char_id[5:]  # Remove "Boss_"
        pal_name = data_loader.pal_names.get(lookup_id, char_id)
        
        # Get gender using official enum
        gender_data = char_info.get("Gender", {})
        gender = "Unknown"
        if isinstance(gender_data, dict):
            gender_val = gender_data.get("value", {})
            if isinstance(gender_val, dict):
                gender_raw = gender_val.get("value", "Unknown")
            else:
                gender_raw = str(gender_val) if gender_val else "Unknown"
        else:
            gender_raw = str(gender_data) if gender_data else "Unknown"
        
        # Parse enum value
        if gender_raw.startswith("EPalGenderType::"):
            gender_raw = gender_raw.replace("EPalGenderType::", "")
        
        # Map to display name using enum
        if gender_raw == "Male" or gender_raw == str(EPalGenderType.MALE):
            gender = "Male"
        elif gender_raw == "Female" or gender_raw == str(EPalGenderType.FEMALE):
            gender = "Female"
        else:
            gender = "Unknown"
        
        # Get owner
        owner_name = pal_to_owner.get(str(instance_id))
        
        # Calculate hunger percentage
        hunger_raw = get_val(char_info, "FullStomach", 150.0)
        if not isinstance(hunger_raw, (int, float)) or hunger_raw != hunger_raw:
            hunger_raw = 150.0
        
        stomach_lookup_id = char_id
        if char_id.startswith("BOSS_") or char_id.startswith("Boss_"):
            stomach_lookup_id = char_id[5:]
        max_stomach = data_loader.pal_max_stomach.get(stomach_lookup_id, 150)
        hunger = min((hunger_raw / max_stomach) * 100, 100.0)
        
        # Get sanity
        sanity = get_val(char_info, "SanityValue", 100.0)
        if not isinstance(sanity, (int, float)) or sanity != sanity:
            sanity = 100.0
        
        is_boss = get_val(char_info, "IsBoss", False) or char_id.startswith("BOSS_") or char_id.startswith("Boss_")
        
        # Extract active skills
        active_skill_ids = []
        equip_waza = char_info.get("EquipWaza", {})
        if isinstance(equip_waza, dict) and "value" in equip_waza:
            waza_values = equip_waza["value"]
            if isinstance(waza_values, dict) and "values" in waza_values:
                active_skill_ids = [str(skill) for skill in waza_values["values"]]
        active_skills = map_active_skills(
            active_skill_ids,
            data_loader.active_skill_data,
            data_loader.active_skill_full_data,
            data_loader.element_display_names
        )
        
        # Extract passive skills
        passive_skill_ids = []
        passive_list = char_info.get("PassiveSkillList", {})
        if isinstance(passive_list, dict) and "value" in passive_list:
            passive_values = passive_list["value"]
            if isinstance(passive_values, dict) and "values" in passive_values:
                passive_skill_ids = [str(skill) for skill in passive_values["values"]]
        passive_skills = map_passive_skills(
            passive_skill_ids,
            data_loader.passive_skill_data,
            data_loader.passive_skill_full_data
        )
        
        # Get element types and work suitability
        element_types = []
        work_suitability = {}
        work_suitability_names = {}
        species_data = data_loader.pal_species_data.get(lookup_id, {})
        if species_data:
            element_types = species_data.get("element_types", [])
            # Map element IDs to localized display names
            element_types = map_element_display_names(element_types, data_loader.element_display_names)
            work_suitability = species_data.get("work_suitability", {})
            # Map work type IDs to display names
            work_suitability_names = map_work_suitability_names(
                list(work_suitability.keys()),
                data_loader.work_suitability_names
            )
        
        # Get base assignment
        assignment = base_assignments.get(str(instance_id), {})
        
        # Extract condition/status using official enum
        condition = None
        worker_sick = char_info.get("WorkerSick", {})
        if isinstance(worker_sick, dict) and "value" in worker_sick:
            sick_value = worker_sick["value"]
            if isinstance(sick_value, dict) and "value" in sick_value:
                condition_full = sick_value["value"]
                if isinstance(condition_full, str) and "::" in condition_full:
                    sick_enum_name = condition_full.split("::")[-1]
                    # Map to official enum values
                    if sick_enum_name != "None":
                        condition = sick_enum_name
        
        # Extract hunger type using official enum
        hunger_type = None
        hunger_type_data = char_info.get("HungerType", {})
        if isinstance(hunger_type_data, dict) and "value" in hunger_type_data:
            hunger_value = hunger_type_data["value"]
            if isinstance(hunger_value, dict) and "value" in hunger_value:
                hunger_full = hunger_value["value"]
                if isinstance(hunger_full, str) and "::" in hunger_full:
                    hunger_enum_name = hunger_full.split("::")[-1]
                    # Map enum name to official values
                    if hunger_enum_name == "Hunger" or hunger_enum_name == str(EPalStatusHungerType.HUNGER):
                        hunger_type = "Hunger"
                    elif hunger_enum_name == "Starvation" or hunger_enum_name == str(EPalStatusHungerType.STARVATION):
                        hunger_type = "Starvation"
                    elif hunger_enum_name == "Default" or hunger_enum_name == str(EPalStatusHungerType.DEFAULT):
                        hunger_type = "Default"
                    else:
                        hunger_type = hunger_enum_name
        
        # Calculate actual stats using the precise formulas
        level = get_val(char_info, "Level", 1)
        talent_hp = get_val(char_info, "Talent_HP", 0)
        talent_melee = get_val(char_info, "Talent_Melee", 0)
        talent_shot = get_val(char_info, "Talent_Shot", 0)
        talent_defense = get_val(char_info, "Talent_Defense", 0)
        rank = get_val(char_info, "Rank", 1)
        
        # Extract FriendshipPoint (Trust system)
        friendship_points = get_val(char_info, "FriendshipPoint", 0)
        from backend.parser.utils.stats import calculate_trust_level
        trust_level = calculate_trust_level(friendship_points, data_loader.trust_thresholds)
        
        # Get species scaling data and friendship multipliers from already-loaded data
        # Use the same lookup_id that we use for pal names (handles BOSS_ prefix etc.)
        species_scaling = None
        friendship_multipliers = None
        species_data = data_loader.pal_species_data.get(lookup_id)
        if species_data:
            if "scaling" in species_data:
                species_scaling = species_data["scaling"]
            # Extract friendship multipliers for Trust bonus calculations
            friendship_multipliers = {
                "friendship_hp": species_data.get("friendship_hp", 0),
                "friendship_shotattack": species_data.get("friendship_shotattack", 0),
                "friendship_defense": species_data.get("friendship_defense", 0),
                "friendship_craftspeed": species_data.get("friendship_craftspeed", 0)
            }
        else:
            logger.warning(f"No species data found for lookup_id: {lookup_id} (original char_id: {char_id})")
            # Debug: print available keys only once
            if not hasattr(data_loader, '_debug_keys_logged'):
                available_keys = list(data_loader.pal_species_data.keys())[:10]
                logger.debug(f"Available species keys (first 10): {available_keys}")
                data_loader._debug_keys_logged = True
        
        # Detect if this is an Alpha/Boss pal (applies 1.2x HP multiplier)
        is_alpha_pal = char_id.startswith("BOSS_") or char_id.startswith("Boss_")
        
        calculated_stats = calculate_pal_stats(
            species_scaling=species_scaling,
            level=level,
            talent_hp=talent_hp,
            talent_melee=talent_melee,
            talent_shot=talent_shot,
            talent_defense=talent_defense,
            rank=rank,
            trust_level=trust_level,
            friendship_multipliers=friendship_multipliers,
            is_alpha=is_alpha_pal
        )
        
        pal = PalInfo(
            instance_id=str(instance_id),
            character_id=str(char_id),
            name=str(pal_name),
            nickname=get_val(char_info, "NickName"),
            level=get_val(char_info, "Level", 1),
            exp=get_val(char_info, "Exp", 0),
            owner_uid=owner_name,
            gender=gender,
            hp=_extract_hp(char_info, "Hp", 100),
            max_hp=calculated_stats["hp"],  # Use calculated HP as max
            mp=get_val(char_info, "MP"),
            max_mp=get_val(char_info, "MaxMP"),
            hunger=hunger,
            sanity=sanity,
            rank=get_val(char_info, "Rank", 1),
            rank_hp=get_val(char_info, "Rank_HP", 0),
            rank_attack=get_val(char_info, "Rank_Attack", 0),
            rank_defense=get_val(char_info, "Rank_Defense", 0),
            rank_craftspeed=get_val(char_info, "Rank_CraftSpeed", 0),
            talent_hp=get_val(char_info, "Talent_HP", 0),
            talent_melee=get_val(char_info, "Talent_Melee", 0),
            talent_shot=get_val(char_info, "Talent_Shot", 0),
            talent_defense=get_val(char_info, "Talent_Defense", 0),
            active_skills=active_skills,
            passive_skills=passive_skills,
            element_types=element_types,
            work_suitability=work_suitability,
            work_suitability_names=work_suitability_names,
            is_lucky=get_val(char_info, "IsRarePal", False),
            is_boss=is_boss,
            base_id=assignment.get("base_id"),
            guild_id=assignment.get("guild_id"),
            base_name=assignment.get("base_name"),
            condition=condition,
            hunger_type=hunger_type,
            calculated_attack=calculated_stats["attack"],
            calculated_defense=calculated_stats["defense"],
            calculated_hp=calculated_stats["hp"],
            calculated_work_speed=calculated_stats["work_speed"],
            friendship_points=friendship_points,
            trust_level=trust_level
        )
        pals.append(pal)
    
    return pals
