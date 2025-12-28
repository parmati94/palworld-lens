"""Base camp data extraction - schema-driven version"""
from typing import Dict

from backend.parser.utils.schema_loader import SchemaLoader

# Singleton instance
_schema = None


def _get_schema() -> SchemaLoader:
    """Get or create SchemaLoader singleton"""
    global _schema
    if _schema is None:
        _schema = SchemaLoader("collections.yaml")
    return _schema


def get_base_data(world_data: Dict) -> Dict[str, Dict]:
    """Get base camp data using schema-driven extraction
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping base_id to base raw data
    """
    schema = _get_schema()
    return schema.extract_collection(world_data, "bases")


def get_base_assignments(world_data: Dict) -> Dict[str, Dict[str, str]]:
    """Get base assignment mapping for pals at bases.
    
    Returns dict mapping instance_id -> {base_id, guild_id, base_name}
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping pal instance_id to base assignment info
    """
    if not world_data:
        return {}
    
    from backend.parser.utils.schema_loader import SchemaLoader
    
    # Load schema for extracting nested fields
    pal_schema = SchemaLoader("pals.yaml")
    base_schema = SchemaLoader("bases.yaml")
    
    # Get base data using schema-driven extraction
    base_data = get_base_data(world_data)
    
    base_to_container = {}
    base_to_guild = {}
    base_to_name = {}
    
    # Extract base metadata using schema
    for base_id, base_info in base_data.items():
        base_id = str(base_id)
        
        # Extract guild ID using schema
        guild_id = base_schema.extract_field(base_info, "guild_id")
        if guild_id:
            base_to_guild[base_id] = str(guild_id)
        
        # Extract name using schema
        name_str = base_schema.extract_field(base_info, "base_name")
        
        # Store raw name - we'll assign sequential numbers later
        if name_str and "新規生成拠点テンプレート名" in name_str:
            base_to_name[base_id] = "template"
        elif not name_str or not name_str.strip():
            base_to_name[base_id] = "unnamed"
        else:
            base_to_name[base_id] = name_str
        
        # Extract container ID using schema
        container_id = base_schema.extract_field(base_info, "worker_container_id")
        if container_id:
            base_to_container[base_id] = str(container_id)
    
    # Assign sequential base names within each guild
    guild_bases = {}
    for base_id in base_to_container.keys():
        guild_id = base_to_guild.get(base_id)
        if guild_id:
            if guild_id not in guild_bases:
                guild_bases[guild_id] = []
            guild_bases[guild_id].append(base_id)
    
    for guild_id, base_ids in guild_bases.items():
        for i, base_id in enumerate(base_ids):
            original_name = base_to_name.get(base_id, f"Base {base_id[:8]}")
            if original_name in ["template", "unnamed"] or original_name.startswith("Base "):
                base_to_name[base_id] = f"Base {i + 1}"
    
    # Get character data using schema-driven extraction
    from backend.parser.extractors.characters import get_character_data
    char_data = get_character_data(world_data)
    
    assignments = {}
    
    for instance_id, save_param in char_data.items():
        # Skip players using schema
        is_player = pal_schema.extract_field(save_param, "IsPlayer")
        if is_player:
            continue
        
        # Extract pal's container ID - use simpler .get() chain
        pal_container_id = save_param.get("SlotId", {}).get("value", {}).get("ContainerId", {}).get("value", {}).get("ID", {}).get("value")
        
        if pal_container_id:
            pal_container_id = str(pal_container_id)
            
            # Find which base this container belongs to
            for base_id, container_id in base_to_container.items():
                if container_id == pal_container_id:
                    guild_id = base_to_guild.get(base_id)
                    base_name = base_to_name.get(base_id, f"Base {base_id[:8]}")
                    
                    assignments[str(instance_id)] = {
                        "base_id": base_id,
                        "guild_id": guild_id,
                        "base_name": base_name
                    }
                    break
    
    return assignments
