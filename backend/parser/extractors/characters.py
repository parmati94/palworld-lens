"""Character collection extraction (players and pals share one map)."""
from typing import Dict

from backend.parser.loaders.schema_loader import SchemaManager

collections_schema = SchemaManager.get("collections.yaml")
pal_schema = SchemaManager.get("pals.yaml")


def get_character_data(world_data: Dict) -> Dict[str, Dict]:
    """{instance_id: SaveParameter dict} for every character in the save."""
    return collections_schema.extract_collection(world_data, "characters")


def split_players(char_data: Dict[str, Dict]) -> Dict[str, Dict]:
    """The subset of an already-extracted character map that are players."""
    return {iid: info for iid, info in char_data.items() if pal_schema.extract_field(info, "IsPlayer")}
