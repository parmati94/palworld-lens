"""Base camp data extraction from save files"""
from typing import Dict


def get_base_data(world_data: Dict) -> Dict[str, Dict]:
    """Get base camp data
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping base_id to base raw data
    """
    if not world_data:
        return {}
    
    base_camp_param = world_data.get("BaseCampSaveData", {})
    if not isinstance(base_camp_param, dict):
        return {}
    
    base_data = base_camp_param.get("value", [])
    if not isinstance(base_data, list):
        return {}
    
    result = {}
    for entry in base_data:
        if not isinstance(entry, dict):
            continue
        
        # The key can be either a dict or a UUID directly
        key_data = entry.get("key")
        if isinstance(key_data, dict):
            base_id = key_data.get("value")
        else:
            base_id = str(key_data) if key_data else None
        
        if base_id:
            value_data = entry.get("value", {})
            if isinstance(value_data, dict):
                raw_data = value_data.get("RawData", {}).get("value", {})
                if raw_data:
                    result[base_id] = raw_data
    
    return result


def get_base_assignments(world_data: Dict) -> Dict[str, Dict[str, str]]:
    """Get base assignment mapping for pals at bases.
    
    Returns dict mapping instance_id -> {base_id, guild_id, base_name}
    
    Args:
        world_data: World save data from GVAS file
        
    Returns:
        Dict mapping pal instance_id to base assignment info
    """
    if not world_data:
        return {}
    
    # Get base data and extract WorkerDirector container IDs
    base_camp_param = world_data.get("BaseCampSaveData", {})
    base_data = base_camp_param.get("value", [])
    
    base_to_container = {}
    base_to_guild = {}
    base_to_name = {}
    
    for entry in base_data:
        if not isinstance(entry, dict):
            continue
        
        # Get base ID
        key_data = entry.get("key")
        if isinstance(key_data, dict):
            base_id = key_data.get("value")
        else:
            base_id = str(key_data) if key_data else None
        
        if not base_id:
            continue
        
        base_id = str(base_id)
        
        value_data = entry.get("value", {})
        if not isinstance(value_data, dict):
            continue
        
        # Get name and guild from RawData
        raw_data = value_data.get("RawData", {})
        if isinstance(raw_data, dict) and "value" in raw_data:
            raw_val = raw_data["value"]
            if isinstance(raw_val, dict):
                # Get name
                name = raw_val.get("name")
                if isinstance(name, dict):
                    name = name.get("value")
                
                name_str = str(name) if name else ""
                
                # Store raw name - we'll assign sequential numbers later
                if "新規生成拠点テンプレート名" in name_str:
                    base_to_name[base_id] = "template"
                elif not name_str.strip():
                    base_to_name[base_id] = "unnamed"
                else:
                    base_to_name[base_id] = name_str
                
                # Get guild
                guild_id = raw_val.get("group_id_belong_to")
                if isinstance(guild_id, dict):
                    guild_id = guild_id.get("value") or guild_id.get("id")
                if guild_id:
                    base_to_guild[base_id] = str(guild_id)
        
        # Get WorkerDirector container ID
        worker_director = value_data.get("WorkerDirector", {})
        if isinstance(worker_director, dict) and "value" in worker_director:
            wd_value = worker_director["value"]
            if isinstance(wd_value, dict) and "RawData" in wd_value:
                wd_raw = wd_value["RawData"]
                if isinstance(wd_raw, dict) and "value" in wd_raw:
                    wd_raw_val = wd_raw["value"]
                    if isinstance(wd_raw_val, dict):
                        container_id = wd_raw_val.get("container_id")
                        if isinstance(container_id, dict):
                            container_id = container_id.get("value") or container_id.get("id")
                        if container_id:
                            base_to_container[base_id] = str(container_id)
    
    # Assign sequential base names within each guild
    guild_bases = {}
    for base_id in base_to_container.keys():
        guild_id = base_to_guild.get(base_id)
        if guild_id:
            if guild_id not in guild_bases:
                guild_bases[guild_id] = []
            guild_bases[guild_id].append(base_id)
    
    for guild_id, base_ids in guild_bases.items():
        for i, base_id in enumerate(base_ids):
            original_name = base_to_name.get(base_id, f"Base {base_id[:8]}")
            if original_name in ["template", "unnamed"] or original_name.startswith("Base "):
                base_to_name[base_id] = f"Base {i + 1}"
    
    # Now map container IDs to pals
    char_save_param = world_data.get("CharacterSaveParameterMap", {})
    char_data = char_save_param.get("value", [])
    
    assignments = {}
    
    for entry in char_data:
        if not isinstance(entry, dict):
            continue
        
        value_data = entry.get("value", {})
        if not isinstance(value_data, dict):
            continue
        
        raw_data = value_data.get("RawData", {}).get("value", {})
        if not isinstance(raw_data, dict):
            continue
        
        save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
        if not isinstance(save_param, dict):
            continue
        
        # Skip players
        is_player = save_param.get("IsPlayer", {})
        if isinstance(is_player, dict):
            is_player = is_player.get("value", False)
        if is_player:
            continue
        
        # Get instance ID
        key_data = entry.get("key", {})
        if isinstance(key_data, dict):
            instance_id = key_data.get("InstanceId", {}).get("value")
        else:
            instance_id = str(key_data)
        
        if not instance_id:
            continue
        
        # Get pal's container ID from SlotId
        slot_id = save_param.get("SlotId", {})
        if isinstance(slot_id, dict):
            slot_id_value = slot_id.get("value", {})
            if isinstance(slot_id_value, dict):
                pal_container_struct = slot_id_value.get("ContainerId", {})
                if isinstance(pal_container_struct, dict):
                    pal_container_value = pal_container_struct.get("value", {})
                    if isinstance(pal_container_value, dict):
                        pal_container_id_struct = pal_container_value.get("ID", {})
                        if isinstance(pal_container_id_struct, dict):
                            pal_container_id = pal_container_id_struct.get("value")
                            
                            if pal_container_id:
                                pal_container_id = str(pal_container_id)
                                
                                # Find which base this container belongs to
                                for base_id, container_id in base_to_container.items():
                                    if container_id == pal_container_id:
                                        guild_id = base_to_guild.get(base_id)
                                        base_name = base_to_name.get(base_id, f"Base {base_id[:8]}")
                                        
                                        assignments[str(instance_id)] = {
                                            "base_id": base_id,
                                            "guild_id": guild_id,
                                            "base_name": base_name
                                        }
                                        break
    
    return assignments
