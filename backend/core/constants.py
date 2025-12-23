"""Constants and mappings used throughout the application

Mappings aligned with official Palworld enums from:
https://gist.github.com/DRayX/ffcb68e23956e4ccda566173146a19c4

See backend.core.enums for the actual enum definitions.
"""
from typing import Dict

# Condition/Status Mappings (aligned with EPalBaseCampWorkerSickType)
CONDITION_DISPLAY_NAMES: Dict[str, str] = {
    "Sick": "Sick/Cold",        # UNVERIFIED - inferred from game UI
    "Sprain": "Sprain",          # UNVERIFIED - inferred from game UI
    "Bulimia": "Overfull",       # CONFIRMED - found in save file
    "Ulcer": "Ulcer",            # UNVERIFIED - inferred from game UI
    "Depression": "Depressed",   # UNVERIFIED - inferred from game UI
    "GutWrenching": "Gut Wrenching",  # UNVERIFIED - inferred from game UI
    "Weakness": "Weakened",      # UNVERIFIED - inferred from game UI
    "Fracture": "Fracture"       # UNVERIFIED - inferred from game UI
}

CONDITION_DESCRIPTIONS: Dict[str, str] = {
    "Sick": "Work Speed -10. Cure: Low Grade Medical Supplies",
    "Sprain": "Movement Speed -10. Cure: Low Grade Medical Supplies",
    "Bulimia": "Hunger depletion -100. Cure: Low Grade Medical Supplies",
    "Ulcer": "Work Speed -20, Movement Speed -10. Cure: Medical Supplies",
    "Fracture": "Work Speed -10, Movement Speed -20. Cure: Medical Supplies",
    "Weakness": "Work Speed -20, Movement Speed -30. Cure: High Grade Medical Supplies",
    "Depression": "Work Speed -30, Movement Speed -20. Cure: High Grade Medical Supplies",
    "GutWrenching": "Severe digestive issues. Cure: High Grade Medical Supplies"
}

# Work Suitability Mappings (names come from JSON - see data_loader.work_suitability_names)
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
}

WORK_LEVEL_COLORS: Dict[int, str] = {
    1: "#9ca3af",  # gray-400
    2: "#22c55e",  # green-500
    3: "#3b82f6",  # blue-500
    4: "#8b5cf6",  # violet-500
    5: "#f59e0b",  # amber-500
}
