"""Data models for the application"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, computed_field
from enum import Enum
from backend.core.constants import (
    CONDITION_DISPLAY_NAMES,
    CONDITION_DESCRIPTIONS,
    WORK_ICON_MAPPING,
    WORK_LEVEL_COLORS,
)


def map_element_display_names(elements: List[str], element_map: Dict[str, str]) -> List[str]:
    """Map element type IDs to their localized display names
    
    Args:
        elements: List of element type IDs (e.g., ['Leaf', 'Earth'])
        element_map: Dictionary mapping element IDs to display names
        
    Returns:
        List of localized display names (e.g., ['Grass', 'Ground'])
    """
    return [element_map.get(element, element) for element in elements]


class SkillInfo(BaseModel):
    """Skill information with name and description"""
    name: str
    description: Optional[str] = None

class PalGender(str, Enum):
    """Pal gender"""
    MALE = "Male"
    FEMALE = "Female"

class SaveInfo(BaseModel):
    """Basic save file information"""
    world_name: str
    loaded: bool
    level_path: Optional[str] = None
    level_meta_path: Optional[str] = None
    player_count: int = 0
    guild_count: int = 0
    pal_count: int = 0
    last_updated: Optional[str] = None
    file_size: Optional[int] = None
    level_meta_size: Optional[int] = None

class PalInfo(BaseModel):
    """Pal information"""
    instance_id: str
    character_id: str
    name: str
    nickname: Optional[str] = None
    level: int
    exp: int
    owner_uid: Optional[str] = None
    gender: str
    hp: int
    max_hp: int
    mp: Optional[int] = None
    max_mp: Optional[int] = None
    hunger: float
    sanity: float  # SAN
    location: Optional[str] = None
    rank: int = 1
    rank_hp: int = 0
    rank_attack: int = 0
    rank_defense: int = 0
    rank_craftspeed: int = 0
    talent_hp: int = 0
    talent_melee: int = 0
    talent_shot: int = 0
    talent_defense: int = 0
    passive_skills: List[SkillInfo] = []
    active_skills: List[SkillInfo] = []
    element_types: List[str] = []
    work_suitability: Dict[str, int] = {}  # Maps work type ID to level
    work_suitability_names: Dict[str, str] = {}  # Maps work type ID to display name
    is_lucky: bool = False
    is_boss: bool = False
    # Base assignment fields (only set for pals at bases)
    base_id: Optional[str] = None
    guild_id: Optional[str] = None
    base_name: Optional[str] = None
    # Condition/status fields
    condition: Optional[str] = None  # WorkerSick condition (e.g., "Sick", "Sprain", "Bulimia", etc.)
    hunger_type: Optional[str] = None  # HungerType status (e.g., "Hunger")
    
    @computed_field
    def condition_display(self) -> Optional[str]:
        """Get user-friendly condition name for UI"""
        if not self.condition:
            return None
        
        # Return mapped value if exists, otherwise return the raw condition name
        # This allows unknown conditions to still display
        return CONDITION_DISPLAY_NAMES.get(self.condition, self.condition)
    
    @computed_field
    def condition_description(self) -> Optional[str]:
        """Get detailed description of condition including effects and cure"""
        # Handle hunger type
        if self.hunger_type == "Hunger":
            return "Pal needs food urgently"
        
        if not self.condition:
            return None
        
        return CONDITION_DESCRIPTIONS.get(self.condition, self.condition)
    
    @computed_field
    def work_suitability_display(self) -> List[Dict[str, Any]]:
        """Convert work suitability dict to rich display data with names, icons, and color-coded levels"""
        display_data = []
        for work_type, level in self.work_suitability.items():
            if level > 0:
                display_name = self.work_suitability_names.get(work_type, work_type)
                icon_num = WORK_ICON_MAPPING.get(work_type, "00")
                color = WORK_LEVEL_COLORS.get(level, "#9ca3af")
                
                display_data.append({
                    "type": work_type,
                    "name": display_name,
                    "level": level,
                    "icon": f"t_icon_research_palwork_{icon_num}_0",
                    "color": color
                })
        
        return display_data
    
    @computed_field
    def display_name(self) -> str:
        """Clean display name for UI - uses proper localized name"""
        # Always use the localized name (self.name), which comes from l10n/en/pals.json
        # The parser already handles BOSS_ prefix removal for lookups
        return self.name
    
    @computed_field
    def is_alpha(self) -> bool:
        """Returns true if this is an alpha pal (boss only, not lucky - wild pals can't be both)"""
        return self.is_boss and not self.is_lucky
    
    @computed_field
    def image_id(self) -> str:
        """Get the image filename for this pal"""
        # Remove boss prefix for image lookup
        base_id = self.character_id
        if base_id.startswith("BOSS_"):
            base_id = base_id[5:]
        return base_id.lower()

class PlayerInfo(BaseModel):
    """Player information"""
    uid: str
    player_name: str
    nickname: Optional[str] = None
    level: int
    exp: int
    hp: int
    max_hp: int
    mp: Optional[int] = None
    max_mp: Optional[int] = None
    hunger: float
    sanity: float
    guild_id: Optional[str] = None
    last_online: Optional[str] = None
    location: Optional[Dict[str, float]] = None

class GuildInfo(BaseModel):
    """Guild information"""
    guild_id: str
    guild_name: str
    admin_player_uid: Optional[str] = None
    members: List[str] = []
    base_locations: List[Dict[str, Any]] = []

