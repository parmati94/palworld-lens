"""Pal building from save data"""
import logging
from typing import List, Dict

from backend.models.models import PalInfo
from backend.parser.utils.mappers import (
    map_element_display_names,
    map_work_suitability_names,
    map_active_skills,
    map_passive_skills
)
from backend.parser.extractors.characters import get_character_data
from backend.parser.extractors.bases import get_base_assignments
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.stats import calculate_pal_stats, calculate_work_suitabilities, calculate_trust_level
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load YAML schema
pal_schema = SchemaManager.get("pals.yaml")


def _get_lookup_id(char_id: str, data_loader: DataLoader) -> str:
    """Get the appropriate lookup ID for a character, handling BOSS_ prefix intelligently.
    
    Some BOSS_ characters (like BOSS_Ninja, humanoid NPCs) have their own entries in pals.json.
    Others (like BOSS_CatBat for alpha pals) don't and need the prefix removed.
    
    Handles case-insensitive lookups for inconsistencies like Boss_LazyCatFish vs LazyCatfish.
    
    Args:
        char_id: Character ID from save file
        data_loader: DataLoader instance with pal data loaded
        
    Returns:
        Lookup ID to use for pal_names and pal_species_data
    """
    # First, check if the character ID with BOSS_ prefix exists
    if char_id.startswith("BOSS_") or char_id.startswith("Boss_"):
        # Try with the BOSS_ prefix first (exact match)
        if char_id in data_loader.pal_names or char_id in data_loader.pal_species_data:
            return char_id
        
        # If not found, remove the prefix
        stripped_id = char_id[5:]
        
        # Try exact match first
        if stripped_id in data_loader.pal_names or stripped_id in data_loader.pal_species_data:
            return stripped_id
        
        # Fall back to case-insensitive lookup (e.g., LazyCatFish vs LazyCatfish)
        stripped_lower = stripped_id.lower()
        for key in data_loader.pal_names.keys():
            if key.lower() == stripped_lower:
                return key
        
        # If still not found, return the stripped ID
        return stripped_id
    
    return char_id


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
        is_player = pal_schema.extract_field(char_info, "IsPlayer")
        if is_player:
            continue
        
        char_id = pal_schema.extract_field(char_info, "CharacterID")
        
        # Get lookup ID - checks if BOSS_ version exists before stripping prefix
        lookup_id = _get_lookup_id(char_id, data_loader)
        pal_name = data_loader.pal_names.get(lookup_id, char_id)
        
        # Extract fields using YAML schema
        gender = pal_schema.extract_field(char_info, "Gender")
        owner_name = pal_to_owner.get(str(instance_id))
        
        # Calculate hunger percentage
        hunger_raw = pal_schema.extract_field(char_info, "FullStomach")
        stomach_lookup_id = char_id[5:] if char_id.startswith(("BOSS_", "Boss_")) else char_id
        max_stomach = data_loader.pal_max_stomach.get(stomach_lookup_id, 150)
        hunger = min((hunger_raw / max_stomach) * 100, 100.0)
        
        # Extract condition fields
        sanity = pal_schema.extract_field(char_info, "SanityValue")
        is_boss = pal_schema.extract_field(char_info, "IsBoss") or char_id.startswith(("BOSS_", "Boss_"))
        
        # Extract active and passive skills
        active_skill_ids = [str(s) for s in pal_schema.extract_list(char_info, "EquipWaza")]
        active_skills = map_active_skills(
            active_skill_ids,
            data_loader.active_skill_data,
            data_loader.active_skill_full_data,
            data_loader.element_display_names
        )
        
        passive_skill_ids = [str(s) for s in pal_schema.extract_list(char_info, "PassiveSkillList")]
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
            base_work_suitability = species_data.get("work_suitability", {})
            
            # Extract work suitability upgrade data if present
            condensor_rank = pal_schema.extract_field(char_info, "Rank")
            manual_upgrades = None
            
            # Extract manual work suitability upgrades using YAML schema
            upgrade_entries = pal_schema.extract_list(char_info, "GotWorkSuitabilityAddRankList")
            if upgrade_entries:
                manual_upgrades = {}
                for entry in upgrade_entries:
                    work_type = entry.get("work_type")
                    rank_bonus = entry.get("rank_bonus")
                    if work_type and rank_bonus:
                        manual_upgrades[work_type] = manual_upgrades.get(work_type, 0) + rank_bonus
            
            # Only calculate if there are upgrades to apply
            if condensor_rank == 5 or manual_upgrades:
                work_suitability = calculate_work_suitabilities(
                    base_work_suitability,
                    condensor_rank,
                    manual_upgrades
                )
            else:
                # No upgrades, just use base values
                work_suitability = base_work_suitability
            
            # Map work type IDs to display names
            work_suitability_names = map_work_suitability_names(
                list(work_suitability.keys()),
                data_loader.work_suitability_names
            )
        
        # Get base assignment
        assignment = base_assignments.get(str(instance_id), {})
        
        # Extract condition and hunger status using YAML schema
        condition = pal_schema.extract_field(char_info, "WorkerSick")
        hunger_type = pal_schema.extract_field(char_info, "HungerType")
        
        # Extract stat fields using YAML schema
        level = pal_schema.extract_field(char_info, "Level")
        talent_hp = pal_schema.extract_field(char_info, "Talent_HP")
        talent_melee = pal_schema.extract_field(char_info, "Talent_Melee")
        talent_shot = pal_schema.extract_field(char_info, "Talent_Shot")
        talent_defense = pal_schema.extract_field(char_info, "Talent_Defense")
        rank = pal_schema.extract_field(char_info, "Rank")
        friendship_points = pal_schema.extract_field(char_info, "Friendship")
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
            is_alpha=is_alpha_pal,
            passive_skills=passive_skills  # Now includes effects data
        )
        
        pal = PalInfo(
            instance_id=str(instance_id),
            character_id=str(char_id),
            name=str(pal_name),
            nickname=pal_schema.extract_field(char_info, "NickName"),
            level=level,
            exp=pal_schema.extract_field(char_info, "Exp"),
            owner_uid=owner_name,
            gender=gender,
            hp=pal_schema.extract_field(char_info, "Hp"),
            max_hp=calculated_stats["hp"],
            mp=pal_schema.extract_field(char_info, "MP"),
            max_mp=pal_schema.extract_field(char_info, "MaxMP"),
            hunger=hunger,
            sanity=sanity,
            rank=rank,
            rank_hp=pal_schema.extract_field(char_info, "Rank_HP"),
            rank_attack=pal_schema.extract_field(char_info, "Rank_Attack"),
            rank_defense=pal_schema.extract_field(char_info, "Rank_Defense"),
            rank_craftspeed=pal_schema.extract_field(char_info, "Rank_CraftSpeed"),
            talent_hp=talent_hp,
            talent_melee=talent_melee,
            talent_shot=talent_shot,
            talent_defense=talent_defense,
            active_skills=active_skills,
            passive_skills=passive_skills,
            element_types=element_types,
            work_suitability=work_suitability,
            work_suitability_names=work_suitability_names,
            is_lucky=pal_schema.extract_field(char_info, "IsRarePal"),
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
