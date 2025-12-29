"""Base container building from save data (food bowls, storage, etc.)"""
import logging
from typing import List, Dict
from collections import defaultdict

from backend.models.models import BaseContainerInfo, ItemSlot
from backend.parser.extractors.map_objects import get_food_bowls, get_container_contents
from backend.parser.extractors.bases import get_base_data
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.loaders.data_loader import DataLoader
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load schemas
base_schema = SchemaManager.get("bases.yaml")


def build_base_containers(world_data: Dict, data_loader: DataLoader) -> Dict[str, List[BaseContainerInfo]]:
    """Build base container information grouped by base ID
    
    Currently extracts food bowls. Can be extended to include storage boxes, ranches, etc.
    
    Args:
        world_data: World save data from GVAS file
        data_loader: Data loader with localization mappings
        
    Returns:
        Dict mapping base_id to list of BaseContainerInfo objects
    """
    # Get all food bowls (can extend to get other container types here)
    food_bowls = get_food_bowls(world_data)
    
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
                
                # Get item name and icon from data loader
                item_data = data_loader.item_data.get(item_id, {})
                item_name = item_data.get("name", item_id)
                item_icon = item_data.get("icon")
                
                items.append(ItemSlot(
                    item_id=item_id,
                    item_name=item_name,
                    count=count,
                    icon=item_icon
                ))
        
        container_info = BaseContainerInfo(
            container_type="food_bowl",  # Generic type for categorization
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
    
    # TODO: Add other container types here (storage, ranches, etc.)
    # Example:
    # storage_boxes = get_storage_boxes(world_data)
    # for box in storage_boxes:
    #     containers_by_base[box.base_id].append(BaseContainerInfo(
    #         container_type="storage", ...
    #     ))
    
    logger.info(f"Built containers for {len(containers_by_base)} bases")
    return dict(containers_by_base)

