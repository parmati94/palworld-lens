"""What a base is doing: machines, crops, incubators, stations, expeditions, the lab.

Reads three save collections once each and returns plain dicts for
builders/activity.py to join with the game data and the pal list:

  WorkSaveData          one record per worked building: state, per-unit amount,
                        progress on the unit in hand, assigned pals
  MapObjectSaveData     the buildings themselves; only the concrete model
                        classes in backend.common.activity.KINDS are kept
  GuildExtraSaveDataMap the guild's Lab block (research in hand + work done)
  GameTimeSaveData      the world clock, for expedition timers

Field paths are declared in schemas/activity.yaml (kind-specific fields) and
schemas/structures.yaml (map-object identity). The ModuleMap is a list keyed by
module type, which the schema format cannot express, so it is walked here --
the same way structures.py finds a chest's container.
"""
from typing import Any, Dict, List, Optional

from backend.common.activity import GROUND_EGG_MODEL, KINDS, NONE
from backend.common.logging_config import get_logger
from backend.parser.loaders.schema_loader import SchemaManager

logger = get_logger(__name__)

activity_schema = SchemaManager.get("activity.yaml")
map_object_schema = SchemaManager.get("structures.yaml")

ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def _guid(v: Any) -> Optional[str]:
    s = str(v) if v is not None else None
    return None if not s or s == ZERO_GUID else s


def _id_or_none(v: Any) -> Optional[str]:
    return None if v in (None, "", NONE) else str(v)


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _module_raw(module_map: List, module_type: str) -> Dict:
    """RawData of the module named `module_type` (ItemContainer, Workee, ...) in a ModuleMap."""
    for entry in module_map or []:
        if isinstance(entry, dict) and module_type in str(entry.get("key", "")):
            raw = ((entry.get("value") or {}).get("RawData") or {}).get("value")
            return raw if isinstance(raw, dict) else {}
    return {}


def decode_multi_eggs(raw) -> List[Dict]:
    """The large incubator's per-egg block, which save-tools leaves as bytes.

    [{slot, work_id, character_id, nickname, temp_diff}] in slot order. The work id is the
    key into WorkSaveData for that egg's timer. Layout (verified on a live 3-egg incubator):
    u32 lead, u32 count, per egg: u32 slot, guid work id, property list (SaveParameter) until
    None, i32 temp diff, guid, 8 bytes; then 4 trailing bytes. Empty incubators are 12 zero bytes.
    """
    if not raw:
        return []
    data = bytes(raw) if not isinstance(raw, (bytes, bytearray)) else bytes(raw)
    if len(data) <= 12:
        return []
    try:
        from palworld_save_tools.archive import FArchiveReader
        from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
        reader = FArchiveReader(data, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, debug=False)
        reader.u32()
        count = reader.u32()
        out = []
        for _ in range(min(count, 64)):
            slot = reader.u32()
            work_id = reader.guid()
            props = reader.properties_until_end()
            temp = reader.i32()
            reader.guid()
            reader.data.read(8)
            param = ((props.get("SaveParameter") or {}).get("value") or {})
            out.append({
                "slot": int(slot),
                "work_id": _guid(work_id),
                "character_id": _id_or_none((param.get("CharacterID") or {}).get("value")),
                "nickname": _id_or_none((param.get("NickName") or {}).get("value")),
                "temp_diff": int(temp),
            })
        return out
    except Exception as e:      # a layout we have not seen: show the eggs without timers rather than fail the load
        logger.warning(f"Could not decode a large incubator's egg block ({len(data)} bytes): {e}")
        return []


def index_works(world_data: Dict) -> Dict[str, Dict]:
    """{work_id: {type, state, unit, done, assigned: [pal instance ids], owner_model_id}}."""
    out: Dict[str, Dict] = {}
    for w in ((world_data.get("WorkSaveData") or {}).get("value") or {}).get("values") or []:
        if not isinstance(w, dict):
            continue
        wid = _guid(activity_schema.extract_field(w, "work_id"))
        if not wid:
            continue
        assigned = []
        for a in activity_schema.extract_field(w, "work_assign_map") or []:
            raw = (((a.get("value") or {}).get("RawData") or {}).get("value") or {}) if isinstance(a, dict) else {}
            pid = _guid((raw.get("assigned_individual_id") or {}).get("instance_id"))
            if pid:
                assigned.append(pid)
        out[wid] = {
            "type": str(activity_schema.extract_field(w, "workable_type") or "").split("::")[-1],
            "state": activity_schema.extract_field(w, "work_state"),
            "unit": _num(activity_schema.extract_field(w, "work_unit")),
            "done": _num(activity_schema.extract_field(w, "work_done")),
            "assigned": assigned,
            "owner_model_id": _guid(activity_schema.extract_field(w, "work_owner_model_id")),
        }
    return out


def get_activity_objects(world_data: Dict) -> List[Dict]:
    """Every building at a base whose concrete model is one the Activity view draws."""
    out: List[Dict] = []
    values = ((world_data.get("MapObjectSaveData") or {}).get("value") or {}).get("values") or []
    f, g = activity_schema.extract_field, map_object_schema.extract_field
    for obj in values:
        if not isinstance(obj, dict):
            continue
        kind = KINDS.get(g(obj, "concrete_model_type") or "")
        if not kind:
            continue
        base_id = _guid(g(obj, "base_camp_id"))
        if not base_id:
            continue
        module_map = g(obj, "module_map") or []
        out.append({
            "kind": kind,
            "map_object_id": g(obj, "map_object_id"),
            "instance_id": _guid(g(obj, "instance_id")),
            "base_camp_id": base_id,
            "hp_current": g(obj, "hp_current"),
            "hp_max": g(obj, "hp_max"),
            "container_id": _guid(_module_raw(module_map, "ItemContainer").get("target_container_id")),
            "work_id": _guid(_module_raw(module_map, "Workee").get("target_work_id")),
            # machine
            "recipe_id": _id_or_none(f(obj, "recipe_id")),
            "order_total": f(obj, "order_total"),
            "order_left": f(obj, "order_left"),
            "speed_rate": f(obj, "speed_rate"),
            # station
            "product_item_id": _id_or_none(f(obj, "product_item_id")),
            # crop
            "crop_id": f(obj, "crop_id"),
            "crop_state": f(obj, "crop_state"),
            "crop_required": _num(f(obj, "crop_required")),
            "crop_progress": _num(f(obj, "crop_progress")),
            "crop_watered": _num(f(obj, "crop_watered")),
            "crop_work_rate": _num(f(obj, "crop_work_rate")),
            # incubator
            "hatched_character_id": _id_or_none(f(obj, "hatched_character_id")),
            "hatched_nickname": _id_or_none(f(obj, "hatched_nickname")),
            "egg_temp_diff": f(obj, "egg_temp_diff"),
            "multi_eggs": decode_multi_eggs(f(obj, "multi_egg_bytes")) if kind == "incubator" else [],
            # breeding farm
            "spawned_egg_ids": [_guid(e) for e in (f(obj, "spawned_egg_ids") or []) if _guid(e)],
            # generator
            "stored_energy": _num(f(obj, "stored_energy")),
            # expedition
            "mission_id": _id_or_none(f(obj, "mission_id")),
            "mission_state": f(obj, "mission_state"),
            "mission_start_ticks": f(obj, "mission_start_ticks"),
            "mission_pals": [_guid(p.get("instance_id")) for p in (f(obj, "mission_pals") or []) if isinstance(p, dict)],
        })
    logger.info(f"Found {len(out)} activity buildings at bases")
    return out


def index_ground_eggs(world_data: Dict, item_index: Dict[str, List[Dict]]) -> Dict[str, str]:
    """{egg map object's Model instance id: egg item id} for every egg lying on the ground.

    A breeding farm lays eggs as separate map objects and lists them in spawned_egg_instance_ids;
    this is the other half of that join. The egg object's container holds the one PalEgg item.
    """
    out: Dict[str, str] = {}
    g = map_object_schema.extract_field
    for obj in ((world_data.get("MapObjectSaveData") or {}).get("value") or {}).get("values") or []:
        if not isinstance(obj, dict) or g(obj, "concrete_model_type") != GROUND_EGG_MODEL:
            continue
        model_id = _guid(g(obj, "instance_id"))
        cid = _guid(_module_raw(g(obj, "module_map") or [], "ItemContainer").get("target_container_id"))
        items = item_index.get(cid or "", [])
        egg = next((str(i["static_id"]) for i in items if str(i.get("static_id", "")).startswith("PalEgg")), None)
        if model_id and egg:
            out[model_id] = egg
    return out


def get_guild_labs(world_data: Dict) -> Dict[str, Dict]:
    """{guild_id: {current: research id or None, progress: {research id: work done}}}."""
    out: Dict[str, Dict] = {}
    for entry in (world_data.get("GuildExtraSaveDataMap") or {}).get("value") or []:
        if not isinstance(entry, dict) or not entry.get("key"):
            continue
        value = entry.get("value") or {}
        progress = {}
        for r in activity_schema.extract_field(value, "lab_research_info") or []:
            if isinstance(r, dict) and r.get("research_id") and (r.get("work_amount") or 0) > 0:
                progress[str(r["research_id"])] = float(r["work_amount"])
        out[str(entry["key"])] = {"current": _id_or_none(activity_schema.extract_field(value, "lab_current_research_id")),
                                  "progress": progress}
    return out


def get_real_time_ticks(world_data: Dict) -> Optional[int]:
    """The world's real-time clock at save time (100 ns ticks), for expedition timers."""
    v = (((world_data.get("GameTimeSaveData") or {}).get("value") or {}).get("RealDateTimeTicks") or {}).get("value")
    return int(v) if isinstance(v, (int, float)) else None
