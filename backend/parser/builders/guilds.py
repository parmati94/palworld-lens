"""Guild building from save data"""
import logging
from typing import List, Dict

from backend.models.models import GuildInfo
from backend.parser.extractors.guilds import get_guild_data
from backend.parser.utils.helpers import get_val
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


def build_guilds(world_data: Dict) -> List[GuildInfo]:
    """Build list of all guilds from save data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        List of GuildInfo objects
    """
    guilds_data = get_guild_data(world_data)
    guilds = []
    
    for guild_id, guild_info in guilds_data.items():
        # Only include actual player guilds
        group_type = get_val(guild_info, "group_type", "")
        if group_type != "EPalGroupType::Guild":
            continue
        
        # Get members
        members_list = []
        members_data = guild_info.get("individual_character_handle_ids", [])
        if isinstance(members_data, list):
            for member in members_data:
                if isinstance(member, dict):
                    instance_id = member.get("instance_id")
                    if instance_id:
                        members_list.append(str(instance_id))
        
        # Only include guilds with members
        if not members_list:
            continue
        
        # Get guild name
        guild_name = get_val(guild_info, "guild_name", "")
        if not guild_name:
            guild_name = get_val(guild_info, "group_name", "")
        
        # Check if guild_name is a UUID (32 hex chars)
        if guild_name and len(guild_name) == 32 and all(c in '0123456789ABCDEFabcdef' for c in guild_name):
            guild_name = ""
        
        # Fallback names
        if not guild_name:
            admin_uid = get_val(guild_info, "admin_player_uid")
            member_count = len(members_list)
            if admin_uid:
                guild_name = f"{str(admin_uid)[:8]}'s Guild ({member_count} members)"
            else:
                guild_name = f"Guild {str(guild_id)[:8]} ({member_count} members)"
        
        admin_uid = get_val(guild_info, "admin_player_uid")
        
        guild = GuildInfo(
            guild_id=str(guild_id),
            guild_name=guild_name,
            admin_player_uid=str(admin_uid) if admin_uid else None,
            members=members_list
        )
        guilds.append(guild)
    
    return guilds
