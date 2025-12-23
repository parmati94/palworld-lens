"""Guild data extraction from save files"""
from typing import Dict


def get_guild_data(world_data: Dict) -> Dict[str, Dict]:
    """Get guild data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping guild_id to guild raw data
    """
    if not world_data:
        return {}
    
    guild_save_param = world_data.get("GroupSaveDataMap", {})
    if not isinstance(guild_save_param, dict):
        return {}
        
    guild_data = guild_save_param.get("value", [])
    if not isinstance(guild_data, list):
        return {}
        
    result = {}
    for entry in guild_data:
        if not isinstance(entry, dict):
            continue
            
        # The key can be either a dict or a UUID directly
        key_data = entry.get("key")
        if isinstance(key_data, dict):
            guild_id = key_data.get("value")
        else:
            guild_id = str(key_data) if key_data else None
            
        if guild_id:
            value_data = entry.get("value", {})
            if isinstance(value_data, dict):
                raw_data = value_data.get("RawData", {}).get("value", {})
                if raw_data:
                    result[guild_id] = raw_data
                    
    return result
