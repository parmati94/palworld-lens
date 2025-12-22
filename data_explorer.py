#!/usr/bin/env python3
"""
Palworld Save Data Explorer
===========================

This script helps you explore and understand the data structure provided by palworld-save-tools.
Use this to debug, understand data relationships, and plan new features.

Usage:
    python data_explorer.py [command] [options]

Commands:
    overview        - Show high-level save structure
    characters      - Explore character data (players + pals)
    players         - Focus on player data specifically  
    pals            - Focus on pal data specifically
    guilds          - Explore guild/group data
    world           - Show world-level data
    search KEY      - Search for keys containing 'KEY'
    dump PATH       - Dump data at specific path (e.g., worldSaveData.value.CharacterSaveParameterMap)

Examples:
    python data_explorer.py overview
    python data_explorer.py characters --limit 3
    python data_explorer.py search "Player"
    python data_explorer.py dump "worldSaveData.value.GroupSaveDataMap"
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

class SaveDataExplorer:
    """Interactive explorer for Palworld save data"""
    
    def __init__(self, save_path: str):
        self.save_path = Path(save_path)
        self.gvas_data: Optional[Dict] = None
        self.world_data: Optional[Dict] = None
        self.load_save()
    
    def load_save(self):
        """Load and parse the save file"""
        print(f"🔍 Loading save file: {self.save_path}")
        
        try:
            # Read the .sav file
            with open(self.save_path, "rb") as f:
                sav_data = f.read()
            print(f"📁 Read {len(sav_data):,} bytes from disk")
            
            # Decompress to GVAS
            raw_gvas, _ = decompress_sav_to_gvas(sav_data)
            print(f"📦 Decompressed to {len(raw_gvas):,} bytes GVAS data")
            
            # Parse GVAS with type hints
            gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
            self.gvas_data = gvas_file.properties
            self.world_data = self.gvas_data.get("worldSaveData", {}).get("value", {})
            
            print("✅ Save file loaded and parsed successfully!")
            print(f"🌍 World data contains {len(self.world_data)} top-level keys")
            
        except Exception as e:
            print(f"❌ Failed to load save: {e}")
            sys.exit(1)
    
    def show_overview(self):
        """Show high-level save structure"""
        print("\n" + "="*60)
        print("📊 SAVE FILE OVERVIEW")
        print("="*60)
        
        print(f"\n🗂️  Top-level GVAS properties ({len(self.gvas_data)} total):")
        for key in sorted(self.gvas_data.keys()):
            value = self.gvas_data[key]
            print(f"  • {key}: {type(value).__name__}")
        
        print(f"\n🌍 World data keys ({len(self.world_data)} total):")
        for key in sorted(self.world_data.keys()):
            value = self.world_data[key]
            size_info = ""
            
            # Try to get size info for collections
            if isinstance(value, dict) and "value" in value:
                inner_value = value["value"]
                if isinstance(inner_value, list):
                    size_info = f" ({len(inner_value)} items)"
                elif isinstance(inner_value, dict):
                    size_info = f" ({len(inner_value)} keys)"
            
            print(f"  • {key}: {type(value).__name__}{size_info}")
    
    def explore_characters(self, limit: int = 5):
        """Explore character data structure"""
        print("\n" + "="*60)
        print("👥 CHARACTER DATA EXPLORATION")
        print("="*60)
        
        char_save_param = self.world_data.get("CharacterSaveParameterMap", {})
        if not isinstance(char_save_param, dict):
            print("❌ No CharacterSaveParameterMap found")
            return
        
        char_data = char_save_param.get("value", [])
        if not isinstance(char_data, list):
            print("❌ CharacterSaveParameterMap.value is not a list")
            return
        
        print(f"📊 Found {len(char_data)} characters total")
        print(f"🔍 Showing structure of first {min(limit, len(char_data))} characters:\n")
        
        players = []
        pals = []
        
        for i, entry in enumerate(char_data[:limit]):
            if not isinstance(entry, dict):
                continue
                
            # Extract character info
            key_data = entry.get("key", {})
            instance_id = key_data.get("InstanceId", {}).get("value", "Unknown")
            
            value_data = entry.get("value", {})
            raw_data = value_data.get("RawData", {}).get("value", {})
            save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
            
            # Check if player
            is_player = save_param.get("IsPlayer", {}).get("value", False)
            char_id = save_param.get("CharacterID", {}).get("value", "Unknown")
            nickname = save_param.get("NickName", {}).get("value", "No Name")
            
            char_type = "👤 PLAYER" if is_player else "🦎 PAL"
            
            print(f"{i+1}. {char_type}")
            print(f"   Instance ID: {str(instance_id)[:8]}...")
            print(f"   Character ID: {char_id}")
            print(f"   Name: {nickname}")
            
            if is_player:
                players.append(entry)
                # Show player-specific fields
                level = save_param.get("Level", {}).get("value", 1)
                exp = save_param.get("Exp", {}).get("value", 0)
                print(f"   Level: {level}, XP: {exp}")
                
                # Show player unique fields
                player_uid = save_param.get("PlayerUId", {}).get("value", "None")
                print(f"   PlayerUID: {player_uid}")
                
            else:
                pals.append(entry)
                # Show pal-specific fields
                owner_uid = save_param.get("OwnerPlayerUId", {}).get("value", "None")
                is_boss = save_param.get("IsBoss", {}).get("value", False)
                is_lucky = save_param.get("IsRarePal", {}).get("value", False)
                print(f"   Owner UID: {owner_uid}")
                print(f"   Boss: {is_boss}, Lucky: {is_lucky}")
            
            # Show all available fields
            print(f"   Available fields ({len(save_param)} total):")
            for field_key in sorted(save_param.keys())[:10]:  # Show first 10
                print(f"     • {field_key}")
            if len(save_param) > 10:
                print(f"     ... and {len(save_param) - 10} more")
            
            print()
        
        print(f"📈 Summary: {len(players)} players, {len(pals)} pals in sample")
    
    def explore_players(self, limit: int = 3):
        """Focus specifically on player data"""
        print("\n" + "="*60)
        print("👤 PLAYER DATA DEEP DIVE")
        print("="*60)
        
        players = self._get_players()
        print(f"Found {len(players)} players total\n")
        
        for i, (instance_id, player_data) in enumerate(list(players.items())[:limit]):
            print(f"Player {i+1}: {str(instance_id)[:8]}...")
            print("Raw data structure:")
            self._pretty_print_dict(player_data, max_depth=3, indent=2)
            print()
    
    def explore_pals(self, limit: int = 3):
        """Focus specifically on pal data"""
        print("\n" + "="*60)
        print("🦎 PAL DATA DEEP DIVE") 
        print("="*60)
        
        pals = self._get_pals()
        print(f"Found {len(pals)} pals total\n")
        
        for i, (instance_id, pal_data) in enumerate(list(pals.items())[:limit]):
            char_id = pal_data.get("CharacterID", {}).get("value", "Unknown")
            print(f"Pal {i+1}: {char_id} ({str(instance_id)[:8]}...)")
            print("Raw data structure:")
            self._pretty_print_dict(pal_data, max_depth=3, indent=2)
            print()
    
    def explore_guilds(self):
        """Explore guild/group data"""
        print("\n" + "="*60)
        print("🏛️ GUILD DATA EXPLORATION")
        print("="*60)
        
        guild_save_param = self.world_data.get("GroupSaveDataMap", {})
        if not isinstance(guild_save_param, dict):
            print("❌ No GroupSaveDataMap found")
            return
        
        guild_data = guild_save_param.get("value", [])
        if not isinstance(guild_data, list):
            print("❌ GroupSaveDataMap.value is not a list")
            return
        
        print(f"📊 Found {len(guild_data)} groups total\n")
        
        for i, entry in enumerate(guild_data):
            if not isinstance(entry, dict):
                continue
            
            # Extract guild info
            key_data = entry.get("key")
            guild_id = key_data.get("value") if isinstance(key_data, dict) else str(key_data)
            
            value_data = entry.get("value", {})
            raw_data = value_data.get("RawData", {}).get("value", {})
            save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
            
            guild_name = save_param.get("guild_name", {}).get("value", "Unnamed")
            group_type = save_param.get("group_type", {}).get("value", "Unknown")
            
            print(f"Guild {i+1}:")
            print(f"  ID: {str(guild_id)[:8]}...")
            print(f"  Name: {guild_name}")
            print(f"  Type: {group_type}")
            
            # Show members if available
            members = save_param.get("individual_character_handle_ids", {}).get("value", [])
            print(f"  Members: {len(members) if isinstance(members, list) else 0}")
            
            print(f"  Available fields ({len(save_param)} total):")
            for field_key in sorted(save_param.keys())[:8]:
                print(f"    • {field_key}")
            print()
    
    def search_keys(self, search_term: str):
        """Search for keys containing the search term"""
        print(f"\n🔍 Searching for keys containing '{search_term}'...")
        print("="*60)
        
        matches = []
        self._search_recursive(self.gvas_data, search_term.lower(), "", matches)
        
        if matches:
            print(f"Found {len(matches)} matches:\n")
            for path, key, value in matches[:20]:  # Limit to first 20
                value_type = type(value).__name__
                size_info = ""
                if isinstance(value, (list, dict)):
                    size_info = f" ({len(value)} items)"
                
                print(f"  {path}.{key}: {value_type}{size_info}")
                
            if len(matches) > 20:
                print(f"  ... and {len(matches) - 20} more matches")
        else:
            print("No matches found.")
    
    def dump_path(self, path: str):
        """Dump data at a specific path"""
        print(f"\n📤 Dumping data at path: {path}")
        print("="*60)
        
        try:
            data = self.gvas_data
            for part in path.split("."):
                if isinstance(data, dict):
                    data = data.get(part)
                else:
                    print(f"❌ Cannot navigate to '{part}' - parent is not a dict")
                    return
            
            if data is None:
                print("❌ Path not found")
                return
            
            self._pretty_print_dict(data, max_depth=4)
            
        except Exception as e:
            print(f"❌ Error accessing path: {e}")
    
    def _get_players(self) -> Dict[str, Dict]:
        """Extract player data"""
        players = {}
        char_data = self._get_all_characters()
        
        for instance_id, char_info in char_data.items():
            is_player = char_info.get("IsPlayer", {}).get("value", False)
            if is_player:
                players[instance_id] = char_info
        
        return players
    
    def _get_pals(self) -> Dict[str, Dict]:
        """Extract pal data"""
        pals = {}
        char_data = self._get_all_characters()
        
        for instance_id, char_info in char_data.items():
            is_player = char_info.get("IsPlayer", {}).get("value", False)
            if not is_player:
                pals[instance_id] = char_info
        
        return pals
    
    def _get_all_characters(self) -> Dict[str, Dict]:
        """Get all character data (players + pals)"""
        char_save_param = self.world_data.get("CharacterSaveParameterMap", {})
        char_data = char_save_param.get("value", [])
        
        result = {}
        for entry in char_data:
            if not isinstance(entry, dict):
                continue
            
            key_data = entry.get("key", {})
            instance_id = key_data.get("InstanceId", {}).get("value")
            
            if instance_id:
                value_data = entry.get("value", {})
                raw_data = value_data.get("RawData", {}).get("value", {})
                save_param = raw_data.get("object", {}).get("SaveParameter", {}).get("value", {})
                result[str(instance_id)] = save_param
        
        return result
    
    def _search_recursive(self, data: Any, search_term: str, path: str, matches: List):
        """Recursively search for keys"""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                
                if search_term in key.lower():
                    matches.append((path, key, value))
                
                # Continue searching deeper
                self._search_recursive(value, search_term, current_path, matches)
                
        elif isinstance(data, list):
            for i, item in enumerate(data[:10]):  # Limit list search depth
                current_path = f"{path}[{i}]"
                self._search_recursive(item, search_term, current_path, matches)
    
    def _pretty_print_dict(self, data: Any, max_depth: int = 2, current_depth: int = 0, indent: int = 0):
        """Pretty print data structure with depth limit"""
        spaces = "  " * indent
        
        if current_depth >= max_depth:
            print(f"{spaces}{type(data).__name__}(...)")
            return
        
        if isinstance(data, dict):
            if len(data) == 0:
                print(f"{spaces}{{}}")
            else:
                print(f"{spaces}{{")
                for key, value in list(data.items())[:10]:  # Limit items shown
                    if isinstance(value, (dict, list)):
                        print(f"{spaces}  {key}:")
                        self._pretty_print_dict(value, max_depth, current_depth + 1, indent + 2)
                    else:
                        print(f"{spaces}  {key}: {repr(value)}")
                if len(data) > 10:
                    print(f"{spaces}  ... {len(data) - 10} more items")
                print(f"{spaces}}}")
                
        elif isinstance(data, list):
            if len(data) == 0:
                print(f"{spaces}[]")
            else:
                print(f"{spaces}[")
                for i, item in enumerate(data[:5]):  # Limit items shown
                    print(f"{spaces}  [{i}]:")
                    self._pretty_print_dict(item, max_depth, current_depth + 1, indent + 2)
                if len(data) > 5:
                    print(f"{spaces}  ... {len(data) - 5} more items")
                print(f"{spaces}]")
        else:
            print(f"{spaces}{repr(data)}")


def main():
    parser = argparse.ArgumentParser(description="Explore Palworld save data structure")
    parser.add_argument("command", nargs="?", default="overview", 
                       help="Command to run (overview, characters, players, pals, guilds, world, search, dump)")
    parser.add_argument("argument", nargs="?", 
                       help="Additional argument for search term or dump path")
    parser.add_argument("--save", default="/app/saves/Level.sav", 
                       help="Path to Level.sav file")
    parser.add_argument("--limit", type=int, default=5, 
                       help="Limit number of items shown")
    
    args = parser.parse_args()
    
    # Check if save file exists
    save_path = Path(args.save)
    if not save_path.exists():
        print(f"❌ Save file not found: {save_path}")
        print("Available alternatives:")
        for alt_path in ["/home/paul/.gamedata/palworld/Pal/Saved/SaveGames/0/*/Level.sav"]:
            from glob import glob
            matches = glob(alt_path)
            for match in matches:
                print(f"  • {match}")
        sys.exit(1)
    
    # Create explorer and run command
    explorer = SaveDataExplorer(args.save)
    
    if args.command == "overview":
        explorer.show_overview()
    elif args.command == "characters":
        explorer.explore_characters(args.limit)
    elif args.command == "players":
        explorer.explore_players(args.limit)
    elif args.command == "pals":
        explorer.explore_pals(args.limit)
    elif args.command == "guilds":
        explorer.explore_guilds()
    elif args.command == "world":
        explorer.show_overview()
    elif args.command == "search":
        if not args.argument:
            print("❌ Please provide a search term")
            sys.exit(1)
        explorer.search_keys(args.argument)
    elif args.command == "dump":
        if not args.argument:
            print("❌ Please provide a path to dump")
            sys.exit(1)
        explorer.dump_path(args.argument)
    else:
        print(f"❌ Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()