"""Player building from save data"""
import logging
from typing import List, Optional, Dict

from backend.models.models import PlayerInfo
from backend.parser.extractors.characters import get_player_data
from backend.parser.extractors.guilds import get_guild_data
from backend.parser.utils.helpers import get_val
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


def build_players(world_data: Dict) -> List[PlayerInfo]:
    """Build list of all players from save data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        List of PlayerInfo objects
    """
    players_data = get_player_data(world_data)
    players = []
    
    for instance_id, char_info in players_data.items():
        player = PlayerInfo(
            uid=instance_id,
            player_name=get_val(char_info, "NickName", "Unknown"),
            level=get_val(char_info, "Level", 1),
            exp=get_val(char_info, "Exp", 0),
            hp=get_val(char_info, "HP", 100),
            max_hp=get_val(char_info, "MaxHP", 100),
            mp=get_val(char_info, "MP"),
            max_mp=get_val(char_info, "MaxMP"),
            hunger=get_val(char_info, "FullStomach", 100.0),
            sanity=get_val(char_info, "SanityValue", 100.0),
            guild_id=_get_player_guild(world_data, instance_id)
        )
        players.append(player)
    
    return players


def _get_player_guild(world_data: Dict, player_uid: str) -> Optional[str]:
    """Get the guild ID for a player
    
    Args:
        world_data: World save data from GVAS file
        player_uid: Player's character instance ID
        
    Returns:
        Guild ID string or None
    """
    guilds = get_guild_data(world_data)
    for guild_id, guild_info in guilds.items():
        group_type = get_val(guild_info, "group_type", "")
        if group_type != "EPalGroupType::Guild":
            continue
            
        members_data = guild_info.get("individual_character_handle_ids", [])
        if isinstance(members_data, list):
            for member in members_data:
                if isinstance(member, dict):
                    instance_id = member.get("instance_id")
                    if str(instance_id) == str(player_uid):
                        return str(guild_id)
    return None
