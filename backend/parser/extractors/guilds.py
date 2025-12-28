"""Guild data extraction - schema-driven version"""
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


def get_guild_data(world_data: Dict) -> Dict[str, Dict]:
    """Get guild data using schema-driven extraction
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping guild_id to guild raw data
    """
    schema = _get_schema()
    return schema.extract_collection(world_data, "guilds")
