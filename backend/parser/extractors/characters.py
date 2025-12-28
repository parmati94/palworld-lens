"""Character data extraction - schema-driven version"""
from typing import Dict

from backend.parser.loaders.schema_loader import SchemaManager

# Singleton instance
_schema = None


def _get_schema():
    """Get or create SchemaLoader singleton"""
    global _schema
    if _schema is None:
        _schema = SchemaManager.get("collections.yaml")
    return _schema


def get_character_data(world_data: Dict) -> Dict[str, Dict]:
    """Get character save data using schema-driven extraction
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping instance_id to character save parameter dict
    """
    schema = _get_schema()
    return schema.extract_collection(world_data, "characters")


def get_player_data(world_data: Dict) -> Dict[str, Dict]:
    """Get player character data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping instance_id to player character data
    """
    char_data = get_character_data(world_data)
    players = {}
    
    for instance_id, char_info in char_data.items():
        # Check if this is a player character
        is_player_data = char_info.get("IsPlayer", {})
        if isinstance(is_player_data, dict):
            is_player = is_player_data.get("value", False)
        else:
            is_player = bool(is_player_data)
            
        if is_player:
            players[str(instance_id)] = char_info
    
    return players
