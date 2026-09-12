"""Guild collection extraction."""
from typing import Dict

from backend.parser.loaders.schema_loader import SchemaManager

collections_schema = SchemaManager.get("collections.yaml")


def get_guild_data(world_data: Dict) -> Dict[str, Dict]:
    """{group_id: RawData dict} for every group (guilds and organisations)."""
    return collections_schema.extract_collection(world_data, "guilds")


def get_base_data(world_data: Dict) -> Dict[str, Dict]:
    """{base_id: base dict} (RawData + WorkerDirector) for every base camp."""
    return collections_schema.extract_collection(world_data, "bases")
