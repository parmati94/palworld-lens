"""Base container building from save data (food bowls, storage, etc.)"""
from typing import Dict, List
from collections import defaultdict

from backend.models.models import BaseContainerInfo, ItemSlot
from backend.parser.extractors.bases import BaseMeta
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.mappers import map_building_name
from backend.common.logging_config import get_logger

logger = get_logger(__name__)


def _items(container_id, item_index: Dict[str, List[Dict]], data: DataLoader) -> List[ItemSlot]:
    if not container_id:
        return []
    slots = []
    for entry in item_index.get(str(container_id), []):
        row = data.item(entry["static_id"])
        slots.append(ItemSlot(
            item_id=entry["static_id"],
            item_name=row.get("localized_name") or entry["static_id"],
            count=entry["count"],
            icon=row.get("icon"),
        ))
    return slots


def _container(kind: str, building_type: str, display_name: str, raw: Dict,
               meta: BaseMeta, item_index, data: DataLoader) -> BaseContainerInfo:
    hp_max = raw.get("hp_max")
    return BaseContainerInfo(
        container_type=kind,
        building_type=building_type,
        display_name=display_name,
        building_icon=(data.buildings.get(building_type) or {}).get("icon"),
        base_id=meta.base_id,
        base_name=meta.name,
        container_id=raw.get("container_id"),
        items=_items(raw.get("container_id"), item_index, data),
        hp_current=raw.get("hp_current"),
        hp_max=hp_max,
        is_damaged=bool(hp_max) and (raw.get("hp_current") or 0) < hp_max,
    )


def build_base_containers(base_meta: Dict[str, BaseMeta], food_bowls: List[Dict], storage_containers: List[Dict],
                          item_index: Dict[str, List[Dict]], data: DataLoader) -> Dict[str, List[BaseContainerInfo]]:
    """{base_id: [containers]} for food bowls and storage at every known base."""
    by_base: Dict[str, List[BaseContainerInfo]] = defaultdict(list)

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
        kind = "cooler" if ("Cooler" in building_type or "Refrigerator" in building_type) else "storage"
        by_base[meta.base_id].append(_container(kind, building_type, map_building_name(building_type, data),
                                                container, meta, item_index, data))

    logger.info(f"Built containers for {len(by_base)} bases")
    return dict(by_base)
