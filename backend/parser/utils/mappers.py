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

def map_active_skills(skill_ids: List[str], skill_data_map: Dict[str, Dict]) -> List:
    """Transform active skill IDs to SkillInfo objects with names and descriptions
    
    Args:
        skill_ids: List of skill IDs from save data
        skill_data_map: Dictionary of skill data from DataLoader.active_skill_data
        
    Returns:
        List of SkillInfo objects with localized names and descriptions
    """
    from backend.models.models import SkillInfo
    
    skills = []
    for skill_id in skill_ids:
        skill_data = skill_data_map.get(skill_id, {})
        if skill_data:
            skills.append(SkillInfo(
                name=skill_data["name"],
                description=skill_data["description"]
            ))
        else:
            # Fallback for unmapped skills - strip enum prefix
            skill_name = skill_id.replace("EPalWazaID::", "")
            skills.append(SkillInfo(name=skill_name, description=""))
    return skills


def map_passive_skills(skill_ids: List[str], skill_data_map: Dict[str, Dict]) -> List:
    """Transform passive skill IDs to SkillInfo objects with names and descriptions
    
    Args:
        skill_ids: List of skill IDs from save data
        skill_data_map: Dictionary of skill data from DataLoader.passive_skill_data
        
    Returns:
        List of SkillInfo objects with localized names and descriptions
    """
    from backend.models.models import SkillInfo
    
    skills = []
    for skill_id in skill_ids:
        skill_data = skill_data_map.get(skill_id, {})
        if skill_data:
            skills.append(SkillInfo(
                name=skill_data["name"],
                description=skill_data["description"]
            ))
        else:
            # Fallback for unmapped skills
            skills.append(SkillInfo(name=skill_id, description=""))
    return skills
