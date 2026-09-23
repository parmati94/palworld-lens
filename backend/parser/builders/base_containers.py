"""Base container building from save data (food bowls, storage, etc.)"""
import re
from typing import Dict, List, Optional
from collections import defaultdict

from backend.models.models import BaseContainerInfo, BaseLocation, GuildStorageInfo, ItemSlot, SchematicInfo
from backend.parser.extractors.bases import BaseMeta
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.mappers import building_row, map_building_name
from backend.common.logging_config import get_logger
from backend.common.schematics import rarity_name

logger = get_logger(__name__)

# 1.0 Guild Chest. The placed building has no ItemContainer module; its
# contents are the guild's single shared container (extractors/guilds.py).
GUILD_CHEST = "GuildChest"


def _natural(name: str):
    """'Base 10' after 'Base 2'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def is_guild_chest(container: Dict) -> bool:
    return GUILD_CHEST in (container.get("map_object_id") or "") or GUILD_CHEST in (container.get("concrete_type") or "")


def _items(container_id, item_index: Dict[str, List[Dict]], data: DataLoader) -> List[ItemSlot]:
    if not container_id:
        return []
    slots = []
    for entry in item_index.get(str(container_id), []):
        row = data.item(entry["static_id"])
        # A schematic keeps its blueprint icon; the UI layers the product's icon over it.
        schematic = data.schematic(entry["static_id"])
        slots.append(ItemSlot(
            item_id=entry["static_id"],
            item_name=row.get("localized_name") or entry["static_id"],
            count=entry["count"],
            icon=row.get("icon"),
            rarity=row.get("rarity") if rarity_name(row.get("rarity")) else None,
            type=row.get("type_a") or None,
            schematic=SchematicInfo(**schematic) if schematic else None,
        ))
    return slots


def _container(kind: str, building_type: str, display_name: str, raw: Dict,
               meta: BaseMeta, item_index, data: DataLoader) -> BaseContainerInfo:
    hp_max = raw.get("hp_max")
    return BaseContainerInfo(
        container_type=kind,
        building_type=building_type,
        display_name=display_name,
        building_icon=building_row(building_type, data).get("icon"),
        base_id=meta.base_id,
        base_name=meta.name,
        container_id=raw.get("container_id"),
        items=_items(raw.get("container_id"), item_index, data),
        hp_current=raw.get("hp_current"),
        hp_max=hp_max,
        is_damaged=bool(hp_max) and (raw.get("hp_current") or 0) < hp_max,
    )


def build_base_containers(base_meta: Dict[str, BaseMeta], food_bowls: List[Dict], storage_containers: List[Dict],
                          item_index: Dict[str, List[Dict]], data: DataLoader,
                          guild_storage: Optional[Dict[str, str]] = None) -> Dict[str, List[BaseContainerInfo]]:
    """{base_id: [containers]} for food bowls and storage at every known base.

    guild_storage is {guild_id: container_id} for the shared Guild Chest. A base
    gets one guild card no matter how many chests stand there, and each card
    lists every base of the guild that has one (shared_at).
    """
    by_base: Dict[str, List[BaseContainerInfo]] = defaultdict(list)
    guild_storage = guild_storage or {}
    guild_cards: Dict[str, List[BaseContainerInfo]] = defaultdict(list)   # guild_id -> one card per base

    for bowl in food_bowls:
        meta = base_meta.get(bowl.get("base_camp_id") or "")
        if not meta:
            continue
        concrete = bowl.get("concrete_type", "")
        if "Cooler" in concrete:
            building_type, name = "CoolerPalFoodBox", "Cold Food Box"
        elif "FoodBox" in concrete:
            building_type, name = "PalFoodBox", "Feed Box"
        else:
            building_type, name = concrete, concrete
        by_base[meta.base_id].append(_container("food_bowl", building_type, name, bowl, meta, item_index, data))

    for container in storage_containers:
        meta = base_meta.get(container.get("base_camp_id") or "")
        if not meta:
            continue
        # map_object_id is the building id (ItemChest_03, Cooler, ...) that keys
        # buildings.json / technologies.json; concrete_type is the class name.
        building_type = container.get("map_object_id") or container.get("concrete_type", "")
        if is_guild_chest(container):
            if not meta.guild_id or any(c.base_id == meta.base_id for c in guild_cards[meta.guild_id]):
                continue
            raw = dict(container, container_id=guild_storage.get(meta.guild_id))
            card = _container("guild", GUILD_CHEST, map_building_name(GUILD_CHEST, data), raw, meta, item_index, data)
            card.shared, card.guild_id = True, meta.guild_id
            guild_cards[meta.guild_id].append(card)
            by_base[meta.base_id].append(card)
            continue
        kind = "cooler" if ("Cooler" in building_type or "Refrigerator" in building_type) else "storage"
        by_base[meta.base_id].append(_container(kind, building_type, map_building_name(building_type, data),
                                                container, meta, item_index, data))

    for cards in guild_cards.values():
        # The game's own base number keeps the order stable whatever a base is called
        cards.sort(key=lambda c: (getattr(base_meta.get(c.base_id), "number", 0), _natural(c.base_name or "")))
        where = [BaseLocation(base_id=c.base_id, base_name=c.base_name or c.base_id,
                              number=getattr(base_meta.get(c.base_id), "number", 0),
                              place=getattr(base_meta.get(c.base_id), "place", None)) for c in cards]
        for card in cards:
            card.shared_at = where

    logger.info(f"Built containers for {len(by_base)} bases")
    return dict(by_base)


def build_guild_storage(by_base: Dict[str, List[BaseContainerInfo]]) -> Dict[str, GuildStorageInfo]:
    """{guild_id: shared chest + the bases it stands at}, from the built base containers."""
    out: Dict[str, GuildStorageInfo] = {}
    for containers in by_base.values():
        for c in containers:
            if c.shared and c.guild_id and c.guild_id not in out:
                out[c.guild_id] = GuildStorageInfo(guild_id=c.guild_id, container=c, bases=c.shared_at)
    return out
