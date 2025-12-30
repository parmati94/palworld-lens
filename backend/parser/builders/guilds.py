"""Guild building from save data"""
import logging
from typing import List, Dict

from backend.models.models import GuildInfo
from backend.parser.loaders.schema_loader import SchemaManager
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Load YAML schema
guild_schema = SchemaManager.get("guilds.yaml")


def build_guilds(guilds_data: Dict, base_data: Dict) -> List[GuildInfo]:
    """Build list of all guilds from save data
    
    Args:
        guilds_data: Extracted guild data from get_guild_data()
        base_data: Extracted base data from get_base_data()
        
    Returns:
        List of GuildInfo objects
    """
    guilds = []
    
    # Get all base data and map bases to guilds (matching logic from get_base_assignments)
    base_schema = SchemaManager.get("bases.yaml")
    
    base_to_guild = {}
    base_to_name = {}
    base_to_container = {}
    
    # Extract base metadata using schema
    for base_id, base_info in base_data.items():
        base_id = str(base_id)
        
        # Extract guild ID using schema
        guild_id = base_schema.extract_field(base_info, "guild_id")
        if guild_id:
            base_to_guild[base_id] = str(guild_id)
        
        # Extract container ID using schema
        container_id = base_schema.extract_field(base_info, "worker_container_id")
        if container_id:
            base_to_container[base_id] = str(container_id)
    
    # Build mapping of guild_id -> bases (ONLY for bases with container_id)
    guild_bases = {}
    for base_id in base_to_container.keys():
        guild_id = base_to_guild.get(base_id)
        if guild_id:
            if guild_id not in guild_bases:
                guild_bases[guild_id] = []
            guild_bases[guild_id].append(base_id)
    
    # Assign sequential base names within each guild
    for guild_id, base_ids in guild_bases.items():
        for i, base_id in enumerate(base_ids):
            base_to_name[base_id] = f"Base {i + 1}"
    
    for guild_id, guild_info in guilds_data.items():
        # Only include actual player guilds
        group_type = guild_schema.extract_field(guild_info, "group_type")
        if group_type != "EPalGroupType::Guild":
            continue
        
        # Get members using schema
        members_list = []
        members_data = guild_schema.extract_field(guild_info, "individual_character_handle_ids")
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
        guild_name = guild_schema.extract_field(guild_info, "guild_name")
        if not guild_name:
            guild_name = guild_schema.extract_field(guild_info, "group_name")
        
        # Check if guild_name is a UUID (32 hex chars)
        if guild_name and len(guild_name) == 32 and all(c in '0123456789ABCDEFabcdef' for c in guild_name):
            guild_name = ""
        
        # Fallback names
        if not guild_name:
            admin_uid = guild_schema.extract_field(guild_info, "admin_player_uid")
            member_count = len(members_list)
            if admin_uid:
                guild_name = f"{str(admin_uid)[:8]}'s Guild ({member_count} members)"
            else:
                guild_name = f"Guild {str(guild_id)[:8]} ({member_count} members)"
        
        admin_uid = guild_schema.extract_field(guild_info, "admin_player_uid")
        
        # Get base locations for this guild
        guild_id_str = str(guild_id)
        base_locations = []
        if guild_id_str in guild_bases:
            for base_id in guild_bases[guild_id_str]:
                # Get base raw data for coordinates
                base_raw = base_data.get(base_id, {})
                transform = base_schema.extract_field(base_raw, "transform")
                
                # Extract coordinates from transform
                coords = {}
                if transform and isinstance(transform, dict):
                    translation = transform.get("translation", {})
                    if translation:
                        coords["x"] = translation.get("x")
                        coords["y"] = translation.get("y")
                        coords["z"] = translation.get("z")
                
                base_locations.append({
                    "base_id": base_id,
                    "base_name": base_to_name.get(base_id, f"Base {base_id[:8]}"),
                    **coords
                })
        
        guild = GuildInfo(
            guild_id=guild_id_str,
            guild_name=guild_name,
            admin_player_uid=str(admin_uid) if admin_uid else None,
            members=members_list,
            base_locations=base_locations
        )
        guilds.append(guild)
    
    return guilds
