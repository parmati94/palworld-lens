"""Character data extraction from save files"""
from typing import Dict


def get_character_data(world_data: Dict) -> Dict[str, Dict]:
    """Get character save data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping instance_id to character save parameter dict
    """
    if not world_data:
        return {}
    
    char_save_param = world_data.get("CharacterSaveParameterMap", {})
    if not isinstance(char_save_param, dict):
        return {}
        
    char_data = char_save_param.get("value", [])
    if not isinstance(char_data, list):
        return {}
        
    result = {}
    for entry in char_data:
        if not isinstance(entry, dict):
            continue
            
        key_data = entry.get("key", {})
        # Handle both dict and UUID types
        if isinstance(key_data, dict):
            instance_id = key_data.get("InstanceId", {}).get("value")
        else:
            instance_id = str(key_data)
            
        value_data = entry.get("value", {})
        if isinstance(value_data, dict):
            raw_data = value_data.get("RawData", {}).get("value", {})
            if isinstance(raw_data, dict):
                save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
                if instance_id and save_param:
                    result[instance_id] = save_param
                    
    return result


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
