"""Pal building from save data"""
import logging
from typing import List, Dict

from backend.core.enums import EPalGenderType, EPalBaseCampWorkerSickType, EPalStatusHungerType
from backend.models.models import PalInfo, SkillInfo
from backend.parser.extractors.characters import get_character_data
from backend.parser.extractors.bases import get_base_assignments
from backend.parser.utils.helpers import get_val
from backend.parser.core.data_loader import DataLoader
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


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
        
        # Get friendly name - handle BOSS_ prefix
        lookup_id = char_id.replace("BOSS_", "") if char_id.startswith("BOSS_") else char_id
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
        
        lookup_id = char_id
        if char_id.startswith("BOSS_"):
            lookup_id = char_id[5:]
        max_stomach = data_loader.pal_max_stomach.get(lookup_id, 150)
        hunger = min((hunger_raw / max_stomach) * 100, 100.0)
        
        # Get sanity
        sanity = get_val(char_info, "SanityValue", 100.0)
        if not isinstance(sanity, (int, float)) or sanity != sanity:
            sanity = 100.0
        
        is_boss = get_val(char_info, "IsBoss", False) or char_id.startswith("BOSS_")
        
        # Extract active skills
        active_skills = []
        equip_waza = char_info.get("EquipWaza", {})
        if isinstance(equip_waza, dict) and "value" in equip_waza:
            waza_values = equip_waza["value"]
            if isinstance(waza_values, dict) and "values" in waza_values:
                for skill in waza_values["values"]:
                    skill_id = str(skill)
                    skill_data = data_loader.active_skill_data.get(skill_id, {})
                    if skill_data:
                        active_skills.append(SkillInfo(
                            name=skill_data["name"],
                            description=skill_data["description"]
                        ))
                    else:
                        skill_name = skill_id.replace("EPalWazaID::", "")
                        active_skills.append(SkillInfo(
                            name=skill_name,
                            description=""
                        ))
        
        # Extract passive skills
        passive_skills = []
        passive_list = char_info.get("PassiveSkillList", {})
        if isinstance(passive_list, dict) and "value" in passive_list:
            passive_values = passive_list["value"]
            if isinstance(passive_values, dict) and "values" in passive_values:
                for skill in passive_values["values"]:
                    skill_id = str(skill)
                    skill_data = data_loader.passive_skill_data.get(skill_id, {})
                    if skill_data:
                        passive_skills.append(SkillInfo(
                            name=skill_data["name"],
                            description=skill_data["description"]
                        ))
                    else:
                        passive_skills.append(SkillInfo(
                            name=skill_id,
                            description=""
                        ))
        
        # Get element types and work suitability
        element_types = []
        work_suitability = {}
        species_data = data_loader.pal_species_data.get(lookup_id, {})
        if species_data:
            element_types = species_data.get("element_types", [])
            work_suitability = species_data.get("work_suitability", {})
        
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
        
        pal = PalInfo(
            instance_id=str(instance_id),
            character_id=str(char_id),
            name=str(pal_name),
            nickname=get_val(char_info, "NickName"),
            level=get_val(char_info, "Level", 1),
            exp=get_val(char_info, "Exp", 0),
            owner_uid=owner_name,
            gender=gender,
            hp=get_val(char_info, "HP", 100),
            max_hp=get_val(char_info, "MaxHP", 100),
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
            is_lucky=get_val(char_info, "IsRarePal", False),
            is_boss=is_boss,
            base_id=assignment.get("base_id"),
            guild_id=assignment.get("guild_id"),
            base_name=assignment.get("base_name"),
            condition=condition,
            hunger_type=hunger_type
        )
        pals.append(pal)
    
    return pals
