"""Base camp extraction: the one place base metadata (guild, name, worker
container, coordinates) is derived. build_guilds, build_base_containers and
the pal base assignments all consume the same BaseMeta rows, so a base is
named identically everywhere it appears.

A base has three names: the game's number per guild ("Base 3", stable, what
the in-game UI shows), a derived PLACE (nearest fast-travel statue) and an
optional CUSTOM name from the app's base-name store. `name` is the custom
name when set, else "Base N"; `place` rides alongside for the UI to show.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from backend.common.base_names import nearest_landmark
from backend.parser.loaders.schema_loader import SchemaManager

base_schema = SchemaManager.get("bases.yaml")
pal_schema = SchemaManager.get("pals.yaml")

# The game's placeholder for a base that was never named.
_TEMPLATE_NAME = "新規生成拠点テンプレート名"


@dataclass
class BaseMeta:
    base_id: str
    guild_id: Optional[str]
    name: str
    container_id: Optional[str]     # worker container: pals assigned to this base live in it
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    number: int = 0                 # the game's per-guild numbering, in save order
    place: Optional[str] = None     # nearest fast-travel statue
    custom_name: Optional[str] = None


def get_base_metadata(base_data: Dict, landmarks: Optional[Iterable[Dict]] = None,
                      layers: Optional[Dict[str, Dict]] = None,
                      custom_names: Optional[Dict[str, str]] = None) -> Dict[str, BaseMeta]:
    """{base_id: BaseMeta} for every base that has a worker container.

    Naming: a name the game itself carries is kept (it never does today --
    every base has the template placeholder); otherwise the app's custom
    name; otherwise "Base N", numbered per guild in save order. `place` is
    the nearest landmark when coordinates and landmarks are available.
    """
    landmarks = list(landmarks or [])
    custom_names = custom_names or {}
    metas: Dict[str, BaseMeta] = {}
    for base_id, base_info in base_data.items():
        base_id = str(base_id)
        container_id = base_schema.extract_field(base_info, "worker_container_id")
        if not container_id:
            continue
        guild_id = base_schema.extract_field(base_info, "guild_id")
        raw_name = base_schema.extract_field(base_info, "base_name") or ""
        if _TEMPLATE_NAME in raw_name or not raw_name.strip():
            raw_name = ""
        coords = {}
        transform = base_schema.extract_field(base_info, "transform")
        if isinstance(transform, dict):
            translation = transform.get("translation") or {}
            coords = {k: translation.get(k) for k in ("x", "y", "z")}
        metas[base_id] = BaseMeta(
            base_id=base_id,
            guild_id=str(guild_id) if guild_id else None,
            name=raw_name.strip(),
            container_id=str(container_id),
            **coords,
        )

    counters: Dict[Optional[str], int] = {}
    for meta in metas.values():
        counters[meta.guild_id] = counters.get(meta.guild_id, 0) + 1
        meta.number = counters[meta.guild_id]
        meta.custom_name = custom_names.get(meta.base_id) or None
        if not meta.name:
            meta.name = meta.custom_name or f"Base {meta.number}"
        if landmarks:
            meta.place = nearest_landmark(meta.x, meta.y, layers or {}, landmarks)
    return metas


def get_base_assignments(char_data: Dict, base_meta: Dict[str, BaseMeta]) -> Dict[str, Dict[str, Optional[str]]]:
    """{pal instance_id: {base_id, guild_id, base_name, base_place}} for pals working at a base."""
    container_to_base = {m.container_id: m for m in base_meta.values() if m.container_id}
    assignments = {}
    for instance_id, save_param in char_data.items():
        if pal_schema.extract_field(save_param, "IsPlayer"):
            continue
        container_id = (((save_param.get("SlotId") or {}).get("value") or {})
                        .get("ContainerId", {}).get("value", {}).get("ID", {}).get("value"))
        meta = container_to_base.get(str(container_id)) if container_id else None
        if meta:
            assignments[str(instance_id)] = {
                "base_id": meta.base_id,
                "guild_id": meta.guild_id,
                "base_name": meta.name,
                "base_place": meta.place,
            }
    return assignments
