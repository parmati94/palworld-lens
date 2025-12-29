"""Data transformation utilities for mapping game IDs to display values

Transformation Pattern Guidelines
=================================

Use PRE-TRANSFORMATION (in builder before model creation) when:
- Simple 1:1 name mapping (ID → Display Name)
- No additional metadata needed (icons, colors, etc.)
- Example: Pal names, skill names, element types

Use COMPUTED FIELDS (in model after creation) when:
- Complex multi-field enrichment needed
- Combining multiple data sources (IDs + icons + colors + descriptions)
- Example: work_suitability_display, condition_display

Data Source Guidelines
=====================

Use JSON (via DataLoader) for:
- Localized display names
- Game data that could change with updates
- Any data extracted from game files

Use constants.py for:
- Data NOT available in game files (descriptions we wrote)
- Lookup tables for icons, colors, UI metadata
- Enum display name mappings when JSON doesn't exist
"""

from typing import List, Dict


# ============================================================================
# List Mapping Helpers (ID lists → Display name lists/dicts)
# ============================================================================

def map_element_display_names(elements: List[str], element_map: Dict[str, str]) -> List[str]:
    """Map element type IDs to their localized display names
    
    This is a pre-transformation helper used in the builder before model creation.
    Elements are simple string replacements (Leaf→Grass, Earth→Ground), so we
    transform them early and store the final display values.
    
    Args:
        elements: List of element type IDs from game data (e.g., ['Leaf', 'Earth'])
        element_map: Dictionary mapping element IDs to localized names (from JSON)
        
    Returns:
        List of localized display names (e.g., ['Grass', 'Ground'])
        
    Example:
        >>> element_map = {"Leaf": "Grass", "Earth": "Ground"}
        >>> map_element_display_names(["Leaf", "Earth"], element_map)
        ['Grass', 'Ground']
    """
    return [element_map.get(element, element) for element in elements]


def map_work_suitability_names(work_types: List[str], work_map: Dict[str, str]) -> Dict[str, str]:
    """Map work type IDs to their localized display names
    
    Args:
        work_types: List of work type IDs (e.g., ['EmitFlame', 'Watering'])
        work_map: Dictionary mapping work IDs to localized names (from JSON)
        
    Returns:
        Dictionary mapping work type IDs to display names
        
    Example:
        >>> work_map = {"EmitFlame": "Kindling", "Watering": "Watering"}
        >>> map_work_suitability_names(["EmitFlame"], work_map)
        {'EmitFlame': 'Kindling'}
    """
    return {work_type: work_map.get(work_type, work_type) for work_type in work_types}


# ============================================================================
# Object Creation Helpers (IDs → Model objects with lookups)
# ============================================================================

def map_active_skills(
    skill_ids: List[str],
    skill_data_map: Dict[str, Dict],
    full_data_map: Dict[str, Dict],
    element_map: Dict[str, str]
) -> List:
    """Transform active skill IDs to SkillInfo objects with names, descriptions, element, and power
    
    Args:
        skill_ids: List of skill IDs from save data
        skill_data_map: Dictionary of l10n skill data from DataLoader.active_skill_data
        full_data_map: Dictionary of full skill data from DataLoader.active_skill_full_data
        element_map: Dictionary mapping element IDs to display names (for Leaf→Grass, etc.)
        
    Returns:
        List of SkillInfo objects with localized names, descriptions, element types, and power
    """
    from backend.models.models import SkillInfo
    
    skills = []
    for skill_id in skill_ids:
        skill_data = skill_data_map.get(skill_id, {})
        full_data = full_data_map.get(skill_id, {})
        
        if skill_data:
            # Get element from full data and map it to display name (Leaf→Grass, Earth→Ground)
            element = full_data.get("element")
            if element:
                element = element_map.get(element, element)
            
            skills.append(SkillInfo(
                name=skill_data["name"],
                description=skill_data["description"],
                element=element,
                power=full_data.get("power")
            ))
        else:
            # Fallback for unmapped skills - strip enum prefix
            skill_name = skill_id.replace("EPalWazaID::", "")
            skills.append(SkillInfo(name=skill_name, description=""))
    return skills


def map_passive_skills(
    skill_ids: List[str],
    skill_data_map: Dict[str, Dict],
    full_data_map: Dict[str, Dict]
) -> List:
    """Transform passive skill IDs to SkillInfo objects with names, descriptions, and rank
    
    Args:
        skill_ids: List of skill IDs from save data
        skill_data_map: Dictionary of l10n skill data from DataLoader.passive_skill_data
        full_data_map: Dictionary of full skill data from DataLoader.passive_skill_full_data
        
    Returns:
        List of SkillInfo objects with localized names, descriptions, and rank
    """
    from backend.models.models import SkillInfo
    
    skills = []
    for skill_id in skill_ids:
        skill_data = skill_data_map.get(skill_id, {})
        full_data = full_data_map.get(skill_id, {})
        
        if skill_data:
            skills.append(SkillInfo(
                skill_id=skill_id,
                name=skill_data["name"],
                description=skill_data["description"],
                rank=full_data.get("rank"),
                effects=full_data.get("effects", [])  # Include stat effects from JSON
            ))
        else:
            # Fallback for unmapped skills
            skills.append(SkillInfo(skill_id=skill_id, name=skill_id, description=""))
    return skills


def map_building_name(building_type: str, technology_data: Dict[str, Dict], building_data: Dict[str, Dict] = None) -> str:
    """Map building type to localized name with fallback logic
    
    Handles inconsistent naming between save files and technologies.json/buildings.json.
    For example: ItemChest → Infra_ItemChest_Grade_01
    
    Args:
        building_type: Building type ID from save data (e.g., 'ItemChest', 'Cooler', 'Shelf01_Iron')
        technology_data: Dictionary of technology data from DataLoader.technology_data
        building_data: Optional dictionary of building data from DataLoader.building_data
        
    Returns:
        Localized building name or formatted fallback
    """
    # Try direct lookup in technology data first
    tech_info = technology_data.get(building_type)
    if tech_info and "localized_name" in tech_info:
        return tech_info["localized_name"]
    
    # Try looking up in building_data (for furniture/shelves/etc)
    if building_data:
        building_info = building_data.get(building_type, {})
        localized_name = building_info.get("localized_name")
        if localized_name:
            return localized_name
    
    # Map chest variants to their Infra_ItemChest_Grade_XX equivalents
    # Save files use: ItemChest, ItemChest_02, ItemChest_03, ItemChest_04
    # technologies.json uses: Infra_ItemChest_Grade_01, Infra_ItemChest_Grade_02, etc.
    chest_mapping = {
        "ItemChest": "Infra_ItemChest_Grade_01",      # Wooden Chest
        "ItemChest_02": "Infra_ItemChest_Grade_02",  # Metal Chest
        "ItemChest_03": "Infra_ItemChest_Grade_03",  # Refined Metal Chest
        # ItemChest_04 already exists as-is in technologies.json (Advanced Chest)
    }
    
    if building_type in chest_mapping:
        tech_key = chest_mapping[building_type]
        tech_info = technology_data.get(tech_key)
        if tech_info and "localized_name" in tech_info:
            return tech_info["localized_name"]
    
    # Fallback: clean up the building_type for display
    return building_type.replace("_", " ").title()