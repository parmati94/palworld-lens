"""Data models for the application"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, computed_field, Field
from enum import Enum
from backend.common import pal_icons
from backend.common.constants import CONDITION_DISPLAY_NAMES, CONDITION_DESCRIPTIONS


class SkillInfo(BaseModel):
    """Skill information with name, description, and game data"""
    name: str
    skill_id: Optional[str] = None  # Internal skill ID for lookups
    description: Optional[str] = None
    element: Optional[str] = None  # For active skills - element type
    power: Optional[int] = None  # For active skills - attack power
    rank: Optional[int] = None  # For passive skills - rank (-3 to 4, no 0)
    effects: Optional[List[Dict]] = None  # For passive skills - stat effects (MaxHP, Defense, etc.)

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
    species_id: Optional[str] = None  # pals.json key the character_id resolved to (None = unknown species)
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
    element_types: List[str] = []  # element ids (Leaf, Earth, ...); names/icons via /api/game-data
    work_suitability: Dict[str, int] = {}  # work type id -> level; names/icons via /api/game-data
    is_lucky: bool = False
    is_boss: bool = False
    # Base assignment fields (only set for pals at bases)
    base_id: Optional[str] = None
    guild_id: Optional[str] = None
    base_name: Optional[str] = None
    base_place: Optional[str] = None
    # Condition/status fields
    condition: Optional[str] = None  # WorkerSick condition (e.g., "Sick", "Sprain", "Bulimia", etc.)
    hunger_type: Optional[str] = None  # HungerType status (e.g., "Hunger")
    
    # Calculated stats fields (computed from base stats + level + IVs + ranks)
    calculated_attack: Optional[int] = None
    calculated_defense: Optional[int] = None
    calculated_hp: Optional[int] = None
    calculated_work_speed: Optional[int] = None
    friendship_points: Optional[int] = None
    trust_level: Optional[int] = None
    
    @computed_field
    def all_conditions(self) -> List[Dict[str, str]]:
        """Get all active conditions with their display info
        
        Returns list of dicts with 'type', 'name', and 'description' keys.
        Type is 'sickness', 'injury', or 'hunger' for UI styling.
        """
        conditions = []
        
        # Check for sickness (WorkerSick) - PURPLE badge
        if self.condition:
            conditions.append({
                "type": "sickness",
                "name": CONDITION_DISPLAY_NAMES.get(self.condition, self.condition),
                "description": CONDITION_DESCRIPTIONS.get(self.condition, self.condition)
            })
        
        # Check for Major Injury (HP = 0) - RED badge
        if self.hp <= 0:
            conditions.append({
                "type": "injury",
                "name": "Major Injury",
                "description": "Pal is incapacitated. Place in Palbox to recover over 10 minutes."
            })
        
        # Check for Starvation - RED badge
        if self.hunger_type == "Starvation":
            conditions.append({
                "type": "hunger",
                "name": "Starving",
                "description": "Pal is starving and needs food immediately."
            })
        
        return conditions
    
    @computed_field
    def condition_display(self) -> Optional[str]:
        """Get highest priority condition for table display
        
        Priority: Sickness > Major Injury > Starvation
        Returns only the name of the highest priority condition.
        """
        conditions = self.all_conditions
        if not conditions:
            return None
        
        # Return the first condition (they're added in priority order)
        return conditions[0]["name"]
    
    @computed_field
    def condition_description(self) -> Optional[str]:
        """Get description for highest priority condition"""
        conditions = self.all_conditions
        if not conditions:
            return None
        
        return conditions[0]["description"]
    
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
        """Primary icon stem: /img/t_<image_id>_icon_normal.webp (see backend/common/pal_icons.py)"""
        return pal_icons.image_id(self.character_id)

    @computed_field
    def image_candidates(self) -> List[str]:
        """Fallback icon stems, most specific first. Variant ids (PREDATOR_, GYM_, _Oilrig, ...)
        rarely have their own texture; the frontend walks this list on <img> error."""
        return pal_icons.icon_candidates(self.character_id)

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
    # Stat points allocation
    stat_points_hp: int = 0
    stat_points_stamina: int = 0
    stat_points_attack: int = 0
    stat_points_weight: int = 0
    stat_points_capture: int = 0
    stat_points_work_speed: int = 0
    # Extra stat points (from statues/ancient tech)
    ex_stat_points_hp: int = 0
    ex_stat_points_stamina: int = 0
    ex_stat_points_attack: int = 0
    ex_stat_points_weight: int = 0
    ex_stat_points_work_speed: int = 0
    # Calculated stats
    calculated_max_hp: Optional[int] = None
    calculated_stamina: Optional[int] = None
    calculated_attack: Optional[int] = None
    calculated_weight: Optional[int] = None
    calculated_work_speed: Optional[int] = None

class BaseLocation(BaseModel):
    """Base location information"""
    base_id: str
    base_name: str                  # custom name if set, else "Base N"
    number: int = 0                 # the game's per-guild number (stable sort key)
    place: Optional[str] = None     # nearest fast-travel statue
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class GuildInfo(BaseModel):
    """Guild information"""
    guild_id: str
    guild_name: str
    admin_player_uid: Optional[str] = None
    admin_player_name: Optional[str] = None
    members: List[str] = []
    base_locations: List[BaseLocation] = []


class SchematicInfo(BaseModel):
    """What a schematic unlocks (data/json/schematics.json). The slot keeps the game's blueprint
    icon; the UI draws `icon` (the product's) on top of it at 80%, the way the game's item widget does."""
    product_id: str
    product_name: str
    kind: str                      # "item" | "building"
    icon: Optional[str] = None     # the product's icon
    rarity: Optional[int] = None   # the schematic's tier, 0 Common .. 4 Legendary
    rarity_name: Optional[str] = None


class ItemSlot(BaseModel):
    """Item in a container slot"""
    item_id: str
    item_name: str
    count: int
    icon: Optional[str] = None
    rarity: Optional[int] = None   # the game's tier, 0 Common .. 4 Legendary (None when the table has no sane value)
    type: Optional[str] = None     # items.json type_a: Weapon, Armor, Material, Consume, Blueprint, ...
    schematic: Optional[SchematicInfo] = None  # set for blueprint items


class ItemRef(BaseModel):
    """An item named for the Activity view (a product, an input, an egg), with an optional count."""
    item_id: str
    item_name: str
    icon: Optional[str] = None
    rarity: Optional[int] = None
    count: int = 0


class ActivityPal(BaseModel):
    """A pal named on an Activity card (assigned to a job, sent on an expedition)."""
    instance_id: str
    name: str
    species_id: Optional[str] = None
    image_candidates: List[str] = []
    level: int = 0


class CropInfo(BaseModel):
    crop_id: str
    name: str
    icon: Optional[str] = None
    growth: Optional[float] = None      # 0..1
    watered: Optional[float] = None     # 0..1
    required_s: Optional[float] = None
    progress_s: Optional[float] = None


class EggInfo(BaseModel):
    egg: Optional[ItemRef] = None
    hatched_species_id: Optional[str] = None    # set once the egg has hatched and waits for pickup
    hatched_name: Optional[str] = None
    hatched_image_candidates: List[str] = []


class ExpeditionInfo(BaseModel):
    mission_id: Optional[str] = None
    name: Optional[str] = None
    difficulty: Optional[str] = None
    seconds: Optional[int] = None
    state: str = "idle"                 # idle | out | back
    seconds_left: Optional[float] = None
    elapsed: Optional[float] = None
    pals: List[ActivityPal] = []
    haul: List[ItemRef] = []            # rewards sitting in the station


class ActivityJob(BaseModel):
    """One building doing (or not doing) something at a base."""
    instance_id: str
    kind: str                           # machine | station | crop | incubator | ranch | breeding | generator | expedition | lab
    building_type: str
    display_name: str
    building_icon: Optional[str] = None
    base_id: str
    status: str                         # working | ready | unstaffed | no_materials | idle
    recipe_id: Optional[str] = None
    product: Optional[ItemRef] = None
    order_remaining: int = 0
    craftable_now: int = 0
    unit_work: Optional[float] = None
    unit_done: Optional[float] = None
    progress: Optional[float] = None    # 0..1 on the unit in hand
    inputs: List[ItemRef] = []
    outputs: List[ItemRef] = []
    assigned: List[ActivityPal] = []
    crop: Optional[CropInfo] = None
    egg: Optional[EggInfo] = None
    expedition: Optional[ExpeditionInfo] = None
    stored_energy: Optional[float] = None
    energy_max: Optional[float] = None          # generator capacity from its blueprint; progress = fill
    is_damaged: bool = False


class LabResearch(BaseModel):
    research_id: str
    name: str
    category: Optional[str] = None
    work: float = 0
    done: float = 0
    progress: Optional[float] = None
    complete: bool = False


class LabInfo(BaseModel):
    guild_id: str
    base_id: Optional[str] = None       # where the lab stands
    current: Optional[LabResearch] = None
    completed: int = 0
    parked: List[LabResearch] = []      # started, not in hand
    known: int = 0                      # research entries in the game table
    assigned: List[ActivityPal] = []


class BaseActivity(BaseModel):
    base_id: str
    jobs: List[ActivityJob] = []
    working: int = 0
    ready: int = 0
    stuck: int = 0                      # unstaffed + no_materials
    idle: int = 0


class GuildActivity(BaseModel):
    guild_id: str
    lab: Optional[LabInfo] = None
    expeditions: List[ActivityJob] = []


class ActivityPayload(BaseModel):
    """Everything the Activity view shows; timers are as of `as_of_ticks` (the save's real-time clock)."""
    bases: Dict[str, BaseActivity] = {}
    guilds: Dict[str, GuildActivity] = {}
    as_of_ticks: Optional[int] = None


class BaseContainerInfo(BaseModel):
    """Base container information (food bowls, storage, etc.)"""
    container_type: str  # "food_bowl", "storage", "ranch", etc.
    building_type: str  # "PalFoodBox", "CoolerPalFoodBox", "ItemChest", etc.
    display_name: str  # "Feed Box", "Cold Food Box", "Wooden Chest", etc.
    building_icon: Optional[str] = None  # Icon for the building itself
    base_id: str
    base_name: Optional[str] = None
    container_id: Optional[str] = None
    items: List[ItemSlot] = []
    hp_current: Optional[int] = None
    hp_max: Optional[int] = None
    is_damaged: bool = False
    # 1.0 Guild Chest: one container per guild, mirrored at every base a chest stands.
    shared: bool = False
    guild_id: Optional[str] = None
    shared_at: List[BaseLocation] = []  # every base where this shared chest stands

    @computed_field
    def total_item_count(self) -> int:
        """Total number of items in this container"""
        return sum(item.count for item in self.items)
    
    @computed_field
    def unique_item_count(self) -> int:
        """Number of unique items (item types) in this container"""
        return len(self.items)
    
    @computed_field
    def is_empty(self) -> bool:
        """Whether the container has no items"""
        return len(self.items) == 0 or self.total_item_count == 0


class GuildStorageInfo(BaseModel):
    """A guild's shared chest: the same container wherever a Guild Chest is placed."""
    guild_id: str
    container: BaseContainerInfo
    bases: List[BaseLocation] = []

