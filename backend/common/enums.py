"""Official Palworld game enums extracted from C++ header files

Source: https://gist.github.com/DRayX/ffcb68e23956e4ccda566173146a19c4
These enums match the actual game data structures and ensure correct save file parsing.
"""
from enum import IntEnum


class EPalGenderType(IntEnum):
    """Pal gender types"""
    NONE = 0
    MALE = 1
    FEMALE = 2


class EPalElementType(IntEnum):
    """Elemental types for pals"""
    NONE = 0
    NORMAL = 1
    FIRE = 2
    WATER = 3
    LEAF = 4
    ELECTRICITY = 5
    ICE = 6
    EARTH = 7
    DARK = 8
    DRAGON = 9
    MAX = 10


class EPalWorkSuitability(IntEnum):
    """Work suitability types for pals"""
    NONE = 0
    EMIT_FLAME = 1  # Kindling
    WATERING = 2
    SEEDING = 3  # Planting
    GENERATE_ELECTRICITY = 4  # Generating Electricity
    HANDCRAFT = 5  # Handiwork
    COLLECTION = 6  # Gathering
    DEFOREST = 7  # Lumbering
    MINING = 8
    OIL_EXTRACTION = 9
    PRODUCT_MEDICINE = 10  # Medicine Production
    COOL = 11  # Cooling
    TRANSPORT = 12  # Transporting
    MONSTER_FARM = 13  # Farming
    ANYONE = 14
    MAX = 15


class EPalBaseCampWorkerSickType(IntEnum):
    """Base camp worker sickness types"""
    NONE = 0
    COLD = 1
    SPRAIN = 2
    BULIMIA = 3
    GASTRIC_ULCER = 4
    FRACTURE = 5
    WEAKNESS = 6
    DEPRESSION_SPRAIN = 7
    DISTURBING_ELEMENT = 8
    MAX = 9


class EPalStatusHungerType(IntEnum):
    """Hunger status types"""
    DEFAULT = 0
    HUNGER = 1
    STARVATION = 2
    MAX = 3


class EPalBaseCampWorkerEventType(IntEnum):
    """Base camp worker event types"""
    NONE = 0
    ESCAPE = 1
    OVERWORK_DEATH = 2
    SICK = 3
    DODGE_WORK = 4
    DODGE_WORK_SHORT = 5
    DODGE_WORK_SLEEP = 6
    EAT_TOO_MUCH = 7
    TANTRUM = 8
    FIGHT_WITH_FRIEND = 9
    TURN_FOOD_BOX = 10
    DESTROY_BUILDING = 11
    MAX = 12


class EPalGroupType(IntEnum):
    """Guild/group types"""
    UNDEFINED = 0
    NEUTRAL = 1
    ORGANIZATION = 2
    INDEPENDENT_GUILD = 3
    GUILD = 4
    MAX = 5


class EPalTribeID(IntEnum):
    """Pal species tribe IDs - subset of commonly referenced ones"""
    NONE = 0
    ANUBIS = 1
    BAPHOMET = 2
    BAPHOMET_DARK = 3
    BASTET = 4
    BASTET_ICE = 5
    # ... (157 total in full enum)
    # See full list in gist: https://gist.github.com/DRayX/ffcb68e23956e4ccda566173146a19c4


class EPalPassiveSkillEffectType(IntEnum):
    """Passive skill effect types - commonly used ones"""
    NO = 0
    MAX_HP = 1
    MELEE_ATTACK = 2
    SHOT_ATTACK = 3
    DEFENSE = 4
    SUPPORT = 5
    CRAFT_SPEED = 6
    MOVE_SPEED = 7
    # ... (62 total in full enum)


# Mapping helpers for display
GENDER_DISPLAY = {
    EPalGenderType.NONE: "Unknown",
    EPalGenderType.MALE: "Male",
    EPalGenderType.FEMALE: "Female",
}

ELEMENT_DISPLAY = {
    EPalElementType.NONE: "None",
    EPalElementType.NORMAL: "Normal",
    EPalElementType.FIRE: "Fire",
    EPalElementType.WATER: "Water",
    EPalElementType.LEAF: "Grass",
    EPalElementType.ELECTRICITY: "Electric",
    EPalElementType.ICE: "Ice",
    EPalElementType.EARTH: "Ground",
    EPalElementType.DARK: "Dark",
    EPalElementType.DRAGON: "Dragon",
}

WORK_SUITABILITY_DISPLAY = {
    EPalWorkSuitability.NONE: "None",
    EPalWorkSuitability.EMIT_FLAME: "Kindling",
    EPalWorkSuitability.WATERING: "Watering",
    EPalWorkSuitability.SEEDING: "Planting",
    EPalWorkSuitability.GENERATE_ELECTRICITY: "Generating Electricity",
    EPalWorkSuitability.HANDCRAFT: "Handiwork",
    EPalWorkSuitability.COLLECTION: "Gathering",
    EPalWorkSuitability.DEFOREST: "Lumbering",
    EPalWorkSuitability.MINING: "Mining",
    EPalWorkSuitability.OIL_EXTRACTION: "Oil Extraction",
    EPalWorkSuitability.PRODUCT_MEDICINE: "Medicine Production",
    EPalWorkSuitability.COOL: "Cooling",
    EPalWorkSuitability.TRANSPORT: "Transporting",
    EPalWorkSuitability.MONSTER_FARM: "Farming",
}

SICKNESS_DISPLAY = {
    EPalBaseCampWorkerSickType.NONE: "Healthy",
    EPalBaseCampWorkerSickType.COLD: "Cold",
    EPalBaseCampWorkerSickType.SPRAIN: "Sprain",
    EPalBaseCampWorkerSickType.BULIMIA: "Bulimia",
    EPalBaseCampWorkerSickType.GASTRIC_ULCER: "Gastric Ulcer",
    EPalBaseCampWorkerSickType.FRACTURE: "Fracture",
    EPalBaseCampWorkerSickType.WEAKNESS: "Weakness",
    EPalBaseCampWorkerSickType.DEPRESSION_SPRAIN: "Depression",
    EPalBaseCampWorkerSickType.DISTURBING_ELEMENT: "Disturbing Element",
}

HUNGER_DISPLAY = {
    EPalStatusHungerType.DEFAULT: "Full",
    EPalStatusHungerType.HUNGER: "Hungry",
    EPalStatusHungerType.STARVATION: "Starving",
}
