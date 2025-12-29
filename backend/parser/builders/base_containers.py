"""Base container building from save data (food bowls, storage, etc.)"""
import logging
from typing import List, Dict
from collections import defaultdict

from backend.models.models import BaseContainerInfo, ItemSlot
from backend.parser.extractors.structures import get_food_bowls, get_storage_containers, get_container_contents
from backend.parser.extractors.bases import get_base_data
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.mappers import map_building_name
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load schemas
base_schema = SchemaManager.get("bases.yaml")


def build_base_containers(world_data: Dict, data_loader: DataLoader) -> Dict[str, List[BaseContainerInfo]]:
    """Build base container information grouped by base ID
    
    Extracts food bowls and storage containers (chests, coolers, etc.)
    
    Args:
        world_data: World save data from GVAS file
        data_loader: Data loader with localization mappings
        
    Returns:
        Dict mapping base_id to list of BaseContainerInfo objects
    """
    # Get all food bowls and storage containers
    food_bowls = get_food_bowls(world_data)
    storage_containers = get_storage_containers(world_data)
    
    # Get base data for names
    base_data = get_base_data(world_data)
    base_names = {}
    for base_id, base_info in base_data.items():
        base_name = base_schema.extract_field(base_info, "base_name")
        if base_name:
            base_names[str(base_id)] = base_name
    
    # Group by base
    containers_by_base = defaultdict(list)
    
    # Process food bowls
    for bowl in food_bowls:
        base_id = bowl.get("base_camp_id")
        if not base_id:
            continue
        
        # Determine container type and building type
        concrete_type = bowl.get("concrete_type", "")
        
        # Map concrete model types to friendly names
        if "CoolerPalFoodBox" in concrete_type or "Cooler" in concrete_type:
            building_type = "CoolerPalFoodBox"
            display_name = "Cold Food Box"
        elif "FoodBox" in concrete_type:
            building_type = "PalFoodBox"
            display_name = "Feed Box"
        else:
            building_type = concrete_type
            display_name = concrete_type
        
        # Get building icon from building data
        building_info = data_loader.building_data.get(building_type, {})
        building_icon = building_info.get("icon")
        
        # Get container contents
        container_id = bowl.get("container_id")
        items = []
        
        if container_id:
            container_contents = get_container_contents(world_data, container_id)
            
            for item in container_contents:
                item_id = item["static_id"]
                count = item["count"]
                
                # Get item name and icon from data loader with case-insensitive fallback
                item_data = data_loader.item_data.get(item_id)
                if not item_data:
                    # Try case-insensitive lookup
                    item_data = next((v for k, v in data_loader.item_data.items() if k.lower() == item_id.lower()), {})
                item_name = item_data.get("name", item_id)
                item_icon = item_data.get("icon")
                
                items.append(ItemSlot(
                    item_id=item_id,
                    item_name=item_name,
                    count=count,
                    icon=item_icon
                ))
        
        container_info = BaseContainerInfo(
            container_type="food_bowl",
            building_type=building_type,  # Specific building type
            display_name=display_name,
            building_icon=building_icon,
            base_id=base_id,
            base_name=base_names.get(base_id),
            container_id=container_id,
            items=items,
            hp_current=bowl.get("hp_current"),
            hp_max=bowl.get("hp_max"),
            is_damaged=(bowl.get("hp_current", 0) < bowl.get("hp_max", 1)) if bowl.get("hp_max") else False
        )
        
        containers_by_base[base_id].append(container_info)
    
    # Process storage containers (chests, coolers, etc.)
    for container in storage_containers:
        base_id = container.get("base_camp_id")
        if not base_id:
            continue
        
        concrete_type = container.get("concrete_type", "")
        map_object_id = container.get("map_object_id", "")
        
        # Use map_object_id as the building type (e.g., "ItemChest_03", "Cooler", "Refrigerator")
        # This matches the keys in buildings.json and technologies.json
        building_type = map_object_id if map_object_id else concrete_type
        
        # Determine container type (storage vs cooler) from building data
        building_info = data_loader.building_data.get(building_type, {})
        type_b = building_info.get("type_b", "")
        
        if "Cooler" in building_type or "Refrigerator" in building_type:
            container_type = "cooler"
        elif "Chest" in building_type or type_b == "Infra_Storage":
            container_type = "storage"
        else:
            # Fallback to storage for unknown types
            container_type = "storage"
        
        # Get display name using mapper (handles technology key mapping and building_data lookup)
        display_name = map_building_name(building_type, data_loader.technology_data, data_loader.building_data)
        
        # Get building icon from building data
        building_info = data_loader.building_data.get(building_type, {})
        building_icon = building_info.get("icon")
        
        # Get container contents
        container_id = container.get("container_id")
        items = []
        
        if container_id:
            container_contents = get_container_contents(world_data, container_id)
            
            for item in container_contents:
                item_id = item["static_id"]
                count = item["count"]
                
                # Get item name and icon from data loader with case-insensitive fallback
                item_data = data_loader.item_data.get(item_id)
                if not item_data:
                    # Try case-insensitive lookup
                    item_data = next((v for k, v in data_loader.item_data.items() if k.lower() == item_id.lower()), {})
                item_name = item_data.get("name", item_id)
                item_icon = item_data.get("icon")
                
                items.append(ItemSlot(
                    item_id=item_id,
                    item_name=item_name,
                    count=count,
                    icon=item_icon
                ))
        
        container_info = BaseContainerInfo(
            container_type=container_type,
            building_type=building_type,
            display_name=display_name,
            building_icon=building_icon,
            base_id=base_id,
            base_name=base_names.get(base_id),
            container_id=container_id,
            items=items,
            hp_current=container.get("hp_current"),
            hp_max=container.get("hp_max"),
            is_damaged=(container.get("hp_current", 0) < container.get("hp_max", 1)) if container.get("hp_max") else False
        )
        
        containers_by_base[base_id].append(container_info)
    
    logger.info(f"Built containers for {len(containers_by_base)} bases")
    return dict(containers_by_base)

