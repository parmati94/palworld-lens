"""Constants and mappings used throughout the application

Mappings aligned with official Palworld enums from:
https://gist.github.com/DRayX/ffcb68e23956e4ccda566173146a19c4

"""
from typing import Dict

# Condition/Status Mappings (aligned with EPalBaseCampWorkerSickType)
CONDITION_DISPLAY_NAMES: Dict[str, str] = {
    "Cold": "Sick",                      # EPalBaseCampWorkerSickType.COLD (shows as "Sick" in-game)
    "Sprain": "Sprain",                  # EPalBaseCampWorkerSickType.SPRAIN
    "Bulimia": "Overfull",               # EPalBaseCampWorkerSickType.BULIMIA
    "GastricUlcer": "Ulcer",             # EPalBaseCampWorkerSickType.GASTRIC_ULCER
    "Fracture": "Fracture",              # EPalBaseCampWorkerSickType.FRACTURE
    "Weakness": "Weakened",              # EPalBaseCampWorkerSickType.WEAKNESS
    "DepressionSprain": "Depressed",     # EPalBaseCampWorkerSickType.DEPRESSION_SPRAIN
    "DisturbingElement": "Upset",        # EPalBaseCampWorkerSickType.DISTURBING_ELEMENT
    # Legacy/alternate names for backwards compatibility
    "Sick": "Sick",
    "Ulcer": "Ulcer",
    "Depression": "Depressed",
    "GutWrenching": "Gut Wrenching"
}

CONDITION_DESCRIPTIONS: Dict[str, str] = {
    "Cold": "Work Speed -10. Cure: Low Grade Medical Supplies",
    "Sick": "Work Speed -10. Cure: Low Grade Medical Supplies",
    "Sprain": "Movement Speed -10. Cure: Low Grade Medical Supplies",
    "Bulimia": "Hunger depletion -100. Cure: Low Grade Medical Supplies",
    "GastricUlcer": "Work Speed -20, Movement Speed -10. Cure: Medical Supplies",
    "Ulcer": "Work Speed -20, Movement Speed -10. Cure: Medical Supplies",
    "Fracture": "Work Speed -10, Movement Speed -20. Cure: Medical Supplies",
    "Weakness": "Work Speed -20, Movement Speed -30. Cure: High Grade Medical Supplies",
    "DepressionSprain": "Work Speed -30, Movement Speed -20. Cure: High Grade Medical Supplies",
    "Depression": "Work Speed -30, Movement Speed -20. Cure: High Grade Medical Supplies",
    "DisturbingElement": "Elemental disturbance affecting work. Cure: High Grade Medical Supplies",
    "GutWrenching": "Severe digestive issues. Cure: High Grade Medical Supplies"
}

# Work Suitability icon slots: t_icon_research_palwork_<NN>_0.webp. Names come
# from data/json/l10n/en/work_suitability.json. Every work type that appears in
# pals.json MUST be listed here -- validate.py and tests/test_game_data.py check
# it, because an unlisted type used to fall through to slot 00 (the Kindling
# icon), which is how OilExtraction shipped wrong after 1.0.
WORK_ICON_MAPPING: Dict[str, str] = {
    "EmitFlame": "00",       # Kindling
    "Watering": "01",        # Watering  
    "Seeding": "02",         # Planting
    "GenerateElectricity": "03", # Generating Electricity
    "Handcraft": "04",       # Handiwork
    "Collection": "05",      # Gathering
    "Deforest": "06",        # Lumbering
    "Mining": "07",          # Mining
    "ProductMedicine": "08", # Medicine Production
    "Cool": "09",            # Cooling
    "Transport": "10",       # Transporting (box icon)
    "MonsterFarm": "11",     # Farming
    "OilExtraction": "13",   # Oil Extraction (1.0). The pak has no _12_ icon;
                             # 13 is the only research icon added with 1.0.
}

WORK_LEVEL_COLORS: Dict[int, str] = {
    1: "#9ca3af",  # gray-400
    2: "#22c55e",  # green-500
    3: "#3b82f6",  # blue-500
    4: "#8b5cf6",  # violet-500
    5: "#f59e0b",  # amber-500
}
