# Palworld Save Data Structure Guide

This document explains how to understand and work with the data structure provided by `palworld-save-tools`.

## Quick Start

Use the provided data explorer script:

```bash
# Show overall structure
python data_explorer.py overview

# Explore characters (players + pals)
python data_explorer.py characters --limit 3

# Focus on just pals
python data_explorer.py pals --limit 5

# Search for specific keys
python data_explorer.py search "Player"
python data_explorer.py search "Owner"
python data_explorer.py search "Guild"

# Dump specific data paths
python data_explorer.py dump "worldSaveData.value.CharacterSaveParameterMap"
```

## Data Architecture Overview

```
Level.sav (Binary)
    ↓ (decompress_sav_to_gvas)
GVAS Data (Unreal Engine Save Format)
    ↓ (GvasFile.read with type hints)
Parsed Python Dict Structure:
    ├── worldSaveData.value
    │   ├── CharacterSaveParameterMap (Players + Pals)
    │   ├── GroupSaveDataMap (Guilds)
    │   ├── BaseCampSaveData (Bases)
    │   ├── ItemContainerSaveData (Inventories)
    │   ├── DynamicItemSaveData (Item instances)
    │   └── ... (other game systems)
    └── ... (other top-level data)
```

## Core Data Structures

### 1. Character Data (Players + Pals)
**Location**: `worldSaveData.value.CharacterSaveParameterMap.value[]`

```python
{
    "key": {
        "InstanceId": {"value": "uuid-here"}
    },
    "value": {
        "RawData": {
            "value": {
                "object": {
                    "SaveParameter": {
                        "value": {
                            # This is where the actual character data lives
                            "IsPlayer": {"value": True/False},
                            "CharacterID": {"value": "PinkCat"}, 
                            "NickName": {"value": "Player Name"},
                            "Level": {"value": 25},
                            "OwnerPlayerUId": {"value": "player-uuid"},
                            # ... many more fields
                        }
                    }
                }
            }
        }
    }
}
```

### 2. Guild Data
**Location**: `worldSaveData.value.GroupSaveDataMap.value[]`

```python
{
    "key": {"value": "guild-uuid"},
    "value": {
        "RawData": {
            "value": {
                "object": {
                    "SaveParameter": {
                        "value": {
                            "guild_name": {"value": "My Guild"},
                            "group_type": {"value": "EPalGroupType::Guild"},
                            "individual_character_handle_ids": {
                                "value": [
                                    {"instance_id": "player-uuid"}
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
}
```

## Key Patterns in Palworld Data

### 1. Nested Value Structure
Most Palworld data follows this pattern:
```python
{"value": actual_data}
# or sometimes double-nested:
{"value": {"value": actual_data}}
```

### 2. Array/List Structure
Collections are typically:
```python
{
    "array_type": "specific_type",
    "value": [item1, item2, item3, ...]
}
```

### 3. UUID References
UUIDs are stored as:
```python
{
    "struct_type": "Guid", 
    "struct_id": "00000000-0000-0000-0000-000000000000",
    "value": "actual-uuid-here"
}
```

## Common Data Extraction Patterns

### Extract Value with Fallback
```python
def get_val(data_dict, key, default=None):
    """Safely extract nested values from Palworld data"""
    val = data_dict.get(key)
    if val is None:
        return default
        
    # Handle single nesting
    if isinstance(val, dict) and "value" in val:
        val = val["value"]
        # Handle double nesting
        if isinstance(val, dict) and "value" in val:
            val = val["value"]
    
    return val if val is not None else default
```

### Extract Character Data
```python
def extract_characters(world_data):
    """Extract all character data (players + pals)"""
    char_save_param = world_data.get("CharacterSaveParameterMap", {})
    char_data = char_save_param.get("value", [])
    
    result = {}
    for entry in char_data:
        # Get instance ID (the character's unique identifier)
        key_data = entry.get("key", {})
        instance_id = key_data.get("InstanceId", {}).get("value")
        
        # Get the actual character parameters
        value_data = entry.get("value", {})
        raw_data = value_data.get("RawData", {}).get("value", {})
        save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
        
        if instance_id:
            result[str(instance_id)] = save_param
    
    return result
```

## Important Field Reference

### Player-Specific Fields
- `IsPlayer`: `{"value": True}` - Identifies players vs pals
- `PlayerUId`: `{"value": "uuid"}` - Player's actual UUID (different from instance_id!)  
- `NickName`: `{"value": "PlayerName"}` - Display name
- `Level`: `{"value": 25}` - Player level
- `Exp`: `{"value": 12345}` - Experience points

### Pal-Specific Fields
- `CharacterID`: `{"value": "PinkCat"}` - Pal species identifier
- `OwnerPlayerUId`: `{"value": "uuid"}` - Who owns this pal (maps to PlayerUId!)
- `IsBoss`: `{"value": True/False}` - Boss pal indicator
- `IsRarePal`: `{"value": True/False}` - Lucky pal indicator
- `FullStomach`: `{"value": 150.0}` - Current hunger level

### Guild Fields
- `guild_name`: `{"value": "Guild Name"}` - Guild display name
- `group_type`: `{"value": "EPalGroupType::Guild"}` - Type of group
- `individual_character_handle_ids`: List of member UUIDs

## Data Relationships

### Player → Pal Ownership
```python
# Players have a PlayerUId field
player_uid = character_data["PlayerUId"]["value"]

# Pals reference this in OwnerPlayerUId
pal_owner = pal_data["OwnerPlayerUId"]["value"]

# They match!
if player_uid == pal_owner:
    print("This pal belongs to this player!")
```

### Player → Guild Membership
```python
# Players appear in guild member lists by instance_id (NOT PlayerUId)
guild_members = guild_data["individual_character_handle_ids"]["value"]
for member in guild_members:
    member_instance_id = member["instance_id"]
    # This matches the character's key.InstanceId.value
```

## Development Tips

### 1. Always Use the Explorer First
Before coding new features, run:
```bash
python data_explorer.py search "FieldName"
```

### 2. Handle Missing Data Gracefully
Palworld data can be inconsistent. Always provide defaults:
```python
level = get_val(char_data, "Level", 1)  # Default to level 1
```

### 3. Understand UUID vs Instance ID
- `instance_id`: Character's unique identifier in save file
- `PlayerUId`: Player's persistent UUID (used for ownership)
- Guild members reference `instance_id`, not `PlayerUId`!

### 4. Cache Expensive Operations
Parsing character data is expensive. Cache results:
```python
class SaveFileParser:
    def __init__(self):
        self._character_cache = None
        
    def get_characters(self):
        if self._character_cache is None:
            self._character_cache = self._extract_characters()
        return self._character_cache
```

## Common Issues & Solutions

### Issue: "None" showing for owner names
**Cause**: Owner UIDs don't match player UIDs  
**Solution**: Check if you're using `PlayerUId` vs `instance_id` correctly

### Issue: Data seems corrupted/missing
**Cause**: Incorrect nesting assumptions  
**Solution**: Use the explorer to verify actual structure:
```bash
python data_explorer.py dump "path.to.your.data"
```

### Issue: Performance problems
**Cause**: Re-parsing data on every request  
**Solution**: Cache parsed data in memory, only reload when file changes

## Advanced Usage

### Custom Type Handling
Sometimes you need to handle custom Palworld types:
```python
def extract_guid(guid_data):
    """Extract UUID from Palworld GUID structure"""
    if isinstance(guid_data, dict):
        return guid_data.get("value")
    return str(guid_data)
```

### Debugging Data Structure
Add this to any extraction function:
```python
def debug_structure(data, path="", max_depth=3):
    """Debug helper to understand data structure"""
    if isinstance(data, dict) and max_depth > 0:
        for key, value in data.items():
            print(f"{path}.{key}: {type(value).__name__}")
            if key in ["value", "SaveParameter"]:  # Dive deeper into important keys
                debug_structure(value, f"{path}.{key}", max_depth - 1)
```

This guide should give you everything you need to understand and work with Palworld save data! Use the explorer script to investigate any new data you encounter.