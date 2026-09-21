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


def get_guild_storage(world_data: Dict) -> Dict[str, str]:
    """{guild_id: item container id} for every guild's shared chest (1.0+).

    Lives in GuildExtraSaveDataMap, not on the placed Guild Chest map object:
    that object only carries a GuildSecurity module. Every chest a guild
    places opens the same container, so this is one entry per guild.
    """
    entries = (world_data.get("GuildExtraSaveDataMap") or {}).get("value") or []
    storage: Dict[str, str] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        guild_id = entry.get("key")
        raw = ((((entry.get("value") or {}).get("GuildItemStorage") or {}).get("value") or {})
               .get("RawData") or {}).get("value") or {}
        container_id = raw.get("container_id") if isinstance(raw, dict) else None
        if guild_id and container_id:
            storage[str(guild_id)] = str(container_id)
    return storage
