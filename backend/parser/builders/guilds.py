"""Guild building from save data"""
from typing import Dict, List

from backend.models.models import GuildInfo, BaseLocation
from backend.parser.extractors.bases import BaseMeta
from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

guild_schema = SchemaManager.get("guilds.yaml")


def _is_uuid_like(name: str) -> bool:
    return len(name) == 32 and all(c in '0123456789ABCDEFabcdef' for c in name)


def build_guilds(guilds_data: Dict, base_meta: Dict[str, BaseMeta], player_names: Dict[str, str]) -> List[GuildInfo]:
    """Build every player guild that has members.

    Args:
        guilds_data: extracted guild collection
        base_meta: base metadata (get_base_metadata); bases are grouped by guild_id
        player_names: {PlayerUId: name} so the guild admin can be shown by name
    """
    bases_by_guild: Dict[str, List[BaseMeta]] = {}
    for meta in base_meta.values():
        if meta.guild_id:
            bases_by_guild.setdefault(meta.guild_id, []).append(meta)

    guilds = []
    for guild_id, guild_info in guilds_data.items():
        if guild_schema.extract_field(guild_info, "group_type") != "EPalGroupType::Guild":
            continue

        members_data = guild_schema.extract_field(guild_info, "individual_character_handle_ids")
        members = [str(m["instance_id"]) for m in (members_data or [])
                   if isinstance(m, dict) and m.get("instance_id")]
        if not members:
            continue

        admin_uid = guild_schema.extract_field(guild_info, "admin_player_uid")
        admin_uid = str(admin_uid) if admin_uid else None
        admin_name = player_names.get(admin_uid) if admin_uid else None

        guild_name = (guild_schema.extract_field(guild_info, "guild_name")
                      or guild_schema.extract_field(guild_info, "group_name") or "")
        if _is_uuid_like(guild_name):
            guild_name = ""
        if not guild_name:
            owner = admin_name or (admin_uid[:8] if admin_uid else None)
            guild_name = f"{owner}'s Guild ({len(members)} members)" if owner else f"Guild {str(guild_id)[:8]} ({len(members)} members)"

        guild_id_str = str(guild_id)
        guilds.append(GuildInfo(
            guild_id=guild_id_str,
            guild_name=guild_name,
            admin_player_uid=admin_uid,
            admin_player_name=admin_name,
            members=members,
            base_locations=[
                BaseLocation(base_id=m.base_id, base_name=m.name, number=m.number, place=m.place, x=m.x, y=m.y, z=m.z)
                for m in bases_by_guild.get(guild_id_str, [])
            ],
        ))
    return guilds
