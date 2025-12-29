"""Map object extraction from save data"""
import logging
from typing import Dict, List, Optional
from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load schema
map_object_schema = SchemaManager.get("structures.yaml")


def _extract_container_id_from_modules(module_map: List) -> Optional[str]:
    """Extract container ID from ItemContainer module in module_map
    
    Args:
        module_map: List of module entries from map_object_schema.extract_field()
        
    Returns:
        Container ID string or None if not found
    """
    if not module_map:
        return None
        
    for module_entry in module_map:
        if not isinstance(module_entry, dict):
            continue
            
        module_key = module_entry.get("key", "")
        if "ItemContainer" in str(module_key):
            raw_data = module_entry.get("value", {}).get("RawData", {}).get("value", {})
            container_id = raw_data.get("target_container_id")
            if container_id:
                return str(container_id)
    
    return None


def get_map_objects(world_data: Dict) -> Dict[str, Dict]:
    """Extract all map objects from world data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping map_object_id to map object data
    """
    map_object_data = world_data.get("MapObjectSaveData", {})
    
    if not map_object_data:
        logger.warning("No MapObjectSaveData found")
        return {}
    
    # Navigate to the values array
    values = map_object_data.get("value", {}).get("values", [])
    
    if not values:
        logger.warning("No map object values found")
        return {}
    
    map_objects = {}
    for obj in values:
        map_object_id = map_object_schema.extract_field(obj, "map_object_id")
        if map_object_id:
            map_objects[str(map_object_id)] = obj
    
    logger.info(f"Extracted {len(map_objects)} map objects")
    return map_objects


def get_food_bowls(world_data: Dict) -> List[Dict]:
    """Extract food bowls from map objects
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        List of food bowl data dicts with extracted fields
    """
    map_object_data = world_data.get("MapObjectSaveData", {})
    values = map_object_data.get("value", {}).get("values", [])
    
    food_bowls = []
    
    for obj in values:
        # Extract concrete model type
        concrete_type = map_object_schema.extract_field(obj, "concrete_model_type")
        
        # Filter for food bowls
        if not concrete_type or "FoodBox" not in concrete_type:
            continue
        
        # Extract basic fields
        base_camp_id = map_object_schema.extract_field(obj, "base_camp_id")
        instance_id = map_object_schema.extract_field(obj, "instance_id")
        hp_current = map_object_schema.extract_field(obj, "hp_current")
        hp_max = map_object_schema.extract_field(obj, "hp_max")
        
        # Extract container ID from ModuleMap using schema + helper
        module_map = map_object_schema.extract_field(obj, "module_map")
        container_id = _extract_container_id_from_modules(module_map)
        
        food_bowl = {
            "concrete_type": concrete_type,
            "base_camp_id": str(base_camp_id) if base_camp_id else None,
            "instance_id": str(instance_id) if instance_id else None,
            "hp_current": hp_current,
            "hp_max": hp_max,
            "container_id": str(container_id) if container_id else None
        }
        
        food_bowls.append(food_bowl)
    
    logger.info(f"Found {len(food_bowls)} food bowls")
    return food_bowls


def get_storage_containers(world_data: Dict) -> List[Dict]:
    """Extract storage containers (chests, coolers, etc.) from map objects
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        List of storage container data dicts with extracted fields
    """
    map_object_data = world_data.get("MapObjectSaveData", {})
    values = map_object_data.get("value", {}).get("values", [])
    
    storage_containers = []
    
    for obj in values:
        # Extract concrete model type
        concrete_type = map_object_schema.extract_field(obj, "concrete_model_type")
        
        if not concrete_type:
            continue
        
        # Filter for storage containers (chests, coolers, refrigerators)
        # Include various chest types and coolers, but exclude food bowls
        is_storage = False
        if "Chest" in concrete_type or "Box" in concrete_type or "Cooler" in concrete_type or "Refrigerator" in concrete_type:
            # Exclude food boxes (they're handled separately)
            if "FoodBox" not in concrete_type:
                is_storage = True
        
        if not is_storage:
            continue
        
        # Extract basic fields
        base_camp_id = map_object_schema.extract_field(obj, "base_camp_id")
        instance_id = map_object_schema.extract_field(obj, "instance_id")
        hp_current = map_object_schema.extract_field(obj, "hp_current")
        hp_max = map_object_schema.extract_field(obj, "hp_max")
        
        # Extract map_object_id which contains the actual chest type (e.g., "ItemChest_03", "Cooler")
        map_object_id = map_object_schema.extract_field(obj, "map_object_id")
        
        # Extract container ID from ModuleMap using schema + helper
        module_map = map_object_schema.extract_field(obj, "module_map")
        container_id = _extract_container_id_from_modules(module_map)
        
        storage_container = {
            "concrete_type": concrete_type,
            "map_object_id": str(map_object_id) if map_object_id else None,
            "base_camp_id": str(base_camp_id) if base_camp_id else None,
            "instance_id": str(instance_id) if instance_id else None,
            "hp_current": hp_current,
            "hp_max": hp_max,
            "container_id": str(container_id) if container_id else None
        }
        
        storage_containers.append(storage_container)
    
    # Log unique concrete types for debugging
    unique_types = set(c["concrete_type"] for c in storage_containers)
    logger.info(f"Found {len(storage_containers)} storage containers with types: {unique_types}")
    return storage_containers


def get_container_contents(world_data: Dict, container_id: str) -> List[Dict]:
    """Get items from a specific container
    
    Args:
        world_data: World save data from GVAS file
        container_id: Container ID to look up
        
    Returns:
        List of item dicts with static_id and count
    """
    if not container_id:
        return []
    
    item_container_data = world_data.get("ItemContainerSaveData", {})
    containers = item_container_data.get("value", [])
    
    for container_entry in containers:
        if not isinstance(container_entry, dict):
            continue
        
        # Check if this is our container
        entry_container_id = container_entry.get("key", {}).get("ID", {}).get("value")
        
        if str(entry_container_id) == str(container_id):
            # Found it! Extract slots
            slots = container_entry.get("value", {}).get("Slots", {}).get("value", {}).get("values", [])
            
            items = []
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                
                slot_data = slot.get("RawData", {}).get("value", {})
                item_info = slot_data.get("item", {})
                item_static_id = item_info.get("static_id")
                item_count = slot_data.get("count", 0)
                
                if item_static_id and item_count > 0:
                    items.append({
                        "static_id": item_static_id,
                        "count": item_count
                    })
            
            return items
    
    return []
