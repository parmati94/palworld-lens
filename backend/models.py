"""Data models for the application"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, computed_field
from enum import Enum

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
    player_count: int = 0
    guild_count: int = 0
    pal_count: int = 0
    last_updated: Optional[str] = None

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
    work_suitability: Dict[str, int] = {}
    work_suitability_display: List[Dict[str, Any]] = []  # Rich work suitability data with names, icons, levels
    is_lucky: bool = False
    is_boss: bool = False
    # Base assignment fields (only set for pals at bases)
    base_id: Optional[str] = None
    guild_id: Optional[str] = None
    base_name: Optional[str] = None
    
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

