"""Buildings palworld-save-tools does not know yet.

save-tools maps a map object's id to the concrete model class it should decode
(rawdata/map_concrete_model.py). A building missing from that table comes back as
raw bytes with no model type, and every view built on the model (Activity, storage)
skips it. Upstream's last commit predates Palworld 1.0, so the 1.0 buildings are
registered here until upstream catches up. Each entry names the class the pak's
blueprint uses, so the decoder already knows the layout.

Verified against a live save:
  StationDeforest3  Logging Site 2 (hardwood)  BP_BuildObject_StationDeforest3 -> PalMapObjectProductItemModel
"""
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

SAVE_TOOLS_MAP_OBJECT_EXTRAS = {
    "stationdeforest3": "PalMapObjectProductItemModel",
}


def register_missing_buildings() -> int:
    """Add the entries save-tools lacks (keys are lower-case map object ids). Returns how many were new."""
    from palworld_save_tools.rawdata import map_concrete_model as m
    table = m.MAP_OBJECT_NAME_TO_CONCRETE_MODEL_CLASS
    added = 0
    for key, cls in SAVE_TOOLS_MAP_OBJECT_EXTRAS.items():
        if key not in table:
            table[key] = cls
            added += 1
    if added:
        logger.info(f"Registered {added} building(s) save-tools does not know yet")
    return added
