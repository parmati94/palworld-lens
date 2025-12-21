"""Save file parser - wraps palworld-save-tools library"""
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.config import config
from backend.logging_config import get_logger
from backend.models import SaveInfo, PalInfo, PlayerInfo, GuildInfo, GuildBasePalsInfo, BaseInfo

logger = get_logger(__name__)

class SaveFileParser:
    """Parser for Palworld save files"""
    
    def __init__(self):
        self.level_sav_path: Optional[Path] = None
        self.players_dir: Optional[Path] = None
        self.gvas_data: Optional[Dict] = None
        self.world_data: Optional[Dict] = None
        self.loaded = False
        self.last_load_time: Optional[datetime] = None
        self.pal_names: Dict[str, str] = {}
        self.pal_max_stomach: Dict[str, int] = {}  # Maps pal character_id to max stomach
        self.player_uid_to_instance: Dict[str, str] = {}  # Maps PlayerUId to instance_id
        self.player_names: Dict[str, str] = {}  # Maps PlayerUId to player names
        self._load_pal_names()
        self._load_pal_data()
    
    def _load_pal_names(self):
        """Load pal name mappings from JSON"""
        try:
            # Load English localization
            pals_json = config.DATA_PATH / "json" / "l10n" / "en" / "pals.json"
            if pals_json.exists():
                with open(pals_json, 'r') as f:
                    data = json.load(f)
                    # Create mapping from ID to localized name
                    for pal_id, pal_info in data.items():
                        if isinstance(pal_info, dict):
                            self.pal_names[pal_id] = pal_info.get("localized_name", pal_id)
                logger.info(f"Loaded {len(self.pal_names)} pal names")
            else:
                logger.warning(f"Pal names file not found: {pals_json}")
        except Exception as e:
            logger.warning(f"Could not load pal names: {e}")
    
    def _load_pal_data(self):
        """Load pal data including max stomach values from JSON"""
        try:
            # Load pal data from local data directory
            pals_json = config.DATA_PATH / "json" / "pals.json"
            if pals_json.exists():
                with open(pals_json, 'r') as f:
                    data = json.load(f)
                    # Extract max_full_stomach for each pal
                    for pal_id, pal_info in data.items():
                        if isinstance(pal_info, dict) and "max_full_stomach" in pal_info:
                            self.pal_max_stomach[pal_id] = pal_info["max_full_stomach"]
                logger.info(f"Loaded max stomach data for {len(self.pal_max_stomach)} pals")
            else:
                logger.warning(f"Pal data file not found: {pals_json}")
        except Exception as e:
            logger.warning(f"Could not load pal data: {e}")
        
    def load(self) -> bool:
        """Load save files from mounted directory"""
        try:
            self.level_sav_path = config.get_level_sav_path()
            self.players_dir = config.get_players_dir()
            
            if not self.level_sav_path:
                logger.warning("Level.sav not found in mounted directory")
                return False
            
            logger.info(f"Loading save from: {self.level_sav_path}")
            
            # Read and decompress Level.sav
            with open(self.level_sav_path, "rb") as f:
                sav_data = f.read()
            
            # Decompress using palworld-save-tools
            # decompress_sav_to_gvas returns a tuple (gvas_data, extra_info)
            raw_gvas, _ = decompress_sav_to_gvas(sav_data)
            
            # Parse GVAS - GvasFile.read creates the FArchiveReader internally
            gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
            
            self.gvas_data = gvas_file.properties
            self.world_data = self.gvas_data.get("worldSaveData", {}).get("value", {})
            
            self.loaded = True
            self.last_load_time = datetime.now()
            
            # Build player UID mapping on load
            self._build_player_mapping()
            
            logger.info("✅ Save file loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load save file: {e}")
            self.loaded = False
            return False
    
    def reload(self) -> bool:
        """Reload the save file"""
        logger.info("🔄 Reloading save file...")
        return self.load()
    
    def _build_player_mapping(self):
        """Build mapping from PlayerUId to instance_id"""
        self.player_uid_to_instance = {}
        
        players_data = self._get_player_data()
        logger.info(f"_build_player_mapping: Found {len(players_data)} players")
        
        for instance_id, char_info in players_data.items():
            def get_val(key, default=None):
                val = char_info.get(key)
                if val is None:
                    return default
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                    if isinstance(val, dict) and "value" in val:
                        val = val["value"]
                return val if val is not None else default
            
            player_uid = get_val("PlayerUId")
            player_name = get_val("NickName", "Unknown")
            logger.info(f"Player {instance_id[:8]}: PlayerUId raw={char_info.get('PlayerUId')}, extracted={player_uid}, name={player_name}")
            if player_uid:
                self.player_uid_to_instance[str(player_uid)] = str(instance_id)
                self.player_names[str(player_uid)] = player_name
                logger.info(f"Mapped PlayerUId {player_uid} -> instance {instance_id}, name {player_name}")
        
        logger.info(f"Built player mapping: {len(self.player_uid_to_instance)} players, {len(self.player_names)} names")
    
    def get_save_info(self) -> SaveInfo:
        """Get basic save file information"""
        if not self.loaded:
            return SaveInfo(world_name="Not Loaded", loaded=False)
        
        world_name = "Unknown World"
        
        # Simplify - just count the data
        char_data = self._get_character_data()
        guild_data = self._get_guild_data()
        
        # Count players (characters with IsPlayer flag)
        player_count = sum(1 for char_info in char_data.values() 
                          if isinstance(char_info, dict) and char_info.get("IsPlayer", {}).get("value", False))
        
        # Pal count is total characters minus players
        pal_count = len(char_data) - player_count
        
        return SaveInfo(
            world_name=world_name,
            loaded=True,
            level_path=str(self.level_sav_path) if self.level_sav_path else None,
            player_count=player_count,
            guild_count=len(guild_data),
            pal_count=pal_count,
            last_updated=self.last_load_time.isoformat() if self.last_load_time else None
        )
    
    def _get_character_data(self) -> Dict[str, Dict]:
        """Get character save data"""
        if not self.world_data:
            return {}
        
        char_save_param = self.world_data.get("CharacterSaveParameterMap", {})
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
    
    def _get_player_data(self) -> Dict[str, Dict]:
        """Get player character data"""
        char_data = self._get_character_data()
        players = {}
        
        for instance_id, char_info in char_data.items():
            # Check if this is a player character
            is_player_data = char_info.get("IsPlayer", {})
            if isinstance(is_player_data, dict):
                is_player = is_player_data.get("value", False)
            else:
                is_player = bool(is_player_data)
                
            if is_player:
                # For players, use the instance_id as the UID since they are their own owner
                players[str(instance_id)] = char_info
        
        return players
    
    def _get_guild_data(self) -> Dict[str, Dict]:
        """Get guild data"""
        if not self.world_data:
            return {}
        
        guild_save_param = self.world_data.get("GroupSaveDataMap", {})
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
    
    def _get_base_data(self) -> Dict[str, Dict]:
        """Get base camp data"""
        if not self.world_data:
            return {}
        
        base_camp_param = self.world_data.get("BaseCampSaveData", {})
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
    
    def get_players(self) -> List[PlayerInfo]:
        """Get list of all players"""
        if not self.loaded:
            return []
        
        players_data = self._get_player_data()
        players = []
        
        for instance_id, char_info in players_data.items():
            # Helper to safely extract value from palworld data structure
            # Palworld data can be nested like: {'value': {'value': 34}} or {'value': 34}
            def get_val(key, default=None):
                val = char_info.get(key)
                if val is None:
                    return default
                    
                # Extract value if it's a dict
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                    # Sometimes it's double-nested
                    if isinstance(val, dict) and "value" in val:
                        val = val["value"]
                
                return val if val is not None else default
            
            player = PlayerInfo(
                uid=instance_id,
                player_name=get_val("NickName", "Unknown"),
                level=get_val("Level", 1),
                exp=get_val("Exp", 0),
                hp=get_val("HP", 100),
                max_hp=get_val("MaxHP", 100),
                mp=get_val("MP"),
                max_mp=get_val("MaxMP"),
                hunger=get_val("FullStomach", 100.0),
                sanity=get_val("SanityValue", 100.0),
                guild_id=self._get_player_guild(instance_id)
            )
            players.append(player)
        
        return players
    
    def _get_player_guild(self, player_uid: str) -> Optional[str]:
        """Get the guild ID for a player (by character instance ID)"""
        guilds = self._get_guild_data()
        for guild_id, guild_info in guilds.items():
            # Check if this is a player guild
            group_type = guild_info.get("group_type", "")
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
    
    def get_guilds(self) -> List[GuildInfo]:
        """Get list of all guilds"""
        if not self.loaded:
            return []
        
        guilds_data = self._get_guild_data()
        guilds = []
        
        for guild_id, guild_info in guilds_data.items():
            # Helper to safely extract value
            # Palworld data can be nested like: {'value': {'value': 34}} or {'value': 34}
            def get_val(key, default=None):
                val = guild_info.get(key)
                if val is None:
                    return default
                    
                # Extract value if it's a dict
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                    # Sometimes it's double-nested
                    if isinstance(val, dict) and "value" in val:
                        val = val["value"]
                
                return val if val is not None else default
            
            # Get guild type - only include actual player guilds
            group_type = get_val("group_type", "")
            if group_type != "EPalGroupType::Guild":
                continue
            
            # Get members from individual_character_handle_ids
            members_list = []
            members_data = guild_info.get("individual_character_handle_ids", [])
            if isinstance(members_data, list):
                for member in members_data:
                    if isinstance(member, dict):
                        # Extract instance_id which is the character/player ID
                        instance_id = member.get("instance_id")
                        if instance_id:
                            members_list.append(str(instance_id))
            
            # Only include guilds with members
            if not members_list:
                continue
            
            # Guild name extraction - use the helper function for proper nested access
            # Try guild_name first (this is what the original code uses)
            guild_name = get_val("guild_name", "")
            
            # Also try group_name field if guild_name is empty
            if not guild_name:
                guild_name = get_val("group_name", "")
            
            # Check if guild_name is actually a UUID string (32 hex chars)
            if guild_name and len(guild_name) == 32 and all(c in '0123456789ABCDEFabcdef' for c in guild_name):
                guild_name = ""
                
            # Better fallback names based on guild size and admin
            if not guild_name:
                admin_uid = get_val("admin_player_uid")
                member_count = len(members_list)
                if admin_uid:
                    guild_name = f"{str(admin_uid)[:8]}'s Guild ({member_count} members)"
                else:
                    guild_name = f"Guild {str(guild_id)[:8]} ({member_count} members)"
            
            admin_uid = get_val("admin_player_uid")
            
            guild = GuildInfo(
                guild_id=str(guild_id),
                guild_name=guild_name,
                admin_player_uid=str(admin_uid) if admin_uid else None,
                members=members_list
            )
            guilds.append(guild)
        
        return guilds
    
    def get_pals(self) -> List[PalInfo]:
        """Get list of all pals (non-player characters)"""
        if not self.loaded:
            return []
        
        char_data = self._get_character_data()
        pals = []
        
        for instance_id, char_info in char_data.items():
            # Helper to safely extract value from palworld data structure  
            # Palworld data can be nested like: {'value': {'value': 34}} or {'value': 34}
            def get_val(key, default=None):
                val = char_info.get(key)
                if val is None:
                    return default
                    
                # Extract value if it's a dict
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                    # Sometimes it's double-nested
                    if isinstance(val, dict) and "value" in val:
                        val = val["value"]
                
                return val if val is not None else default
            
            # Skip players
            is_player = get_val("IsPlayer", False)
            if is_player:
                continue
            
            char_id = get_val("CharacterID", "Unknown")
            
            # Get friendly name from mapping - handle BOSS_ prefix for localization
            lookup_id = char_id.replace("BOSS_", "") if char_id.startswith("BOSS_") else char_id
            pal_name = self.pal_names.get(lookup_id, char_id)
            
            # Get gender - can be nested as value.value
            gender_data = char_info.get("Gender", {})
            if isinstance(gender_data, dict):
                gender_val = gender_data.get("value", {})
                if isinstance(gender_val, dict):
                    gender = gender_val.get("value", "Unknown")
                else:
                    gender = str(gender_val) if gender_val else "Unknown"
            else:
                gender = str(gender_data) if gender_data else "Unknown"
            
            # Clean up gender display (remove EPalGenderType:: prefix)
            if gender.startswith("EPalGenderType::"):
                gender = gender.replace("EPalGenderType::", "")
            
            owner_uid = get_val("OwnerPlayerUId")
            # Get player name for owner_uid if available
            owner_name = None
            if owner_uid:
                # Try two approaches: 
                # 1. OwnerPlayerUId might be a PlayerUId that maps to instance_id
                player_instance_id = self.player_uid_to_instance.get(str(owner_uid))
                if player_instance_id:
                    # Get all players to find the one with this instance_id
                    players = self.get_players()
                    for player in players:
                        if player.uid == player_instance_id:
                            owner_name = player.player_name
                            break
                
                # 2. OwnerPlayerUId might directly be an instance_id
                if not owner_name:
                    players = self.get_players()
                    for player in players:
                        if player.uid == str(owner_uid):
                            owner_name = player.player_name
                            break
                
                if not owner_name:
                    owner_name = str(owner_uid)  # Fallback to UID if name not found
            
            # Get hunger and calculate percentage based on pal's max stomach
            hunger_raw = get_val("FullStomach", 150.0)
            if not isinstance(hunger_raw, (int, float)) or hunger_raw != hunger_raw:  # Check for NaN
                hunger_raw = 150.0
            
            # Get pal-specific max stomach, default to 150 if not found
            # Handle boss pals by removing BOSS_ prefix for lookup
            lookup_id = char_id
            if char_id.startswith("BOSS_"):
                lookup_id = char_id[5:]  # Remove "BOSS_" prefix
            max_stomach = self.pal_max_stomach.get(lookup_id, 150)
            # Calculate hunger as percentage: (current / max) * 100, capped at 100%
            hunger = min((hunger_raw / max_stomach) * 100, 100.0)
            
            # Get sanity - these are raw values typically 0-100
            sanity = get_val("SanityValue", 100.0)
            if not isinstance(sanity, (int, float)) or sanity != sanity:  # Check for NaN
                sanity = 100.0
            
            # Determine if this is a boss pal (either from save data or BOSS_ prefix)
            is_boss = get_val("IsBoss", False) or char_id.startswith("BOSS_")
            
            pal = PalInfo(
                instance_id=str(instance_id),
                character_id=str(char_id),
                name=str(pal_name),  # Use friendly name
                nickname=get_val("NickName"),
                level=get_val("Level", 1),
                exp=get_val("Exp", 0),
                owner_uid=owner_name,  # Use player name instead of UID
                gender=gender,
                hp=get_val("HP", 100),
                max_hp=get_val("MaxHP", 100),
                mp=get_val("MP"),
                max_mp=get_val("MaxMP"),
                hunger=hunger,
                sanity=sanity,
                rank=get_val("Rank", 1),
                rank_hp=get_val("Rank_HP", 0),
                rank_attack=get_val("Rank_Attack", 0),
                rank_defense=get_val("Rank_Defense", 0),
                rank_craftspeed=get_val("Rank_CraftSpeed", 0),
                is_lucky=get_val("IsRarePal", False),
                is_boss=is_boss
            )
            pals.append(pal)
        
        return pals
    
    def get_base_pals(self) -> List[GuildBasePalsInfo]:
        """Get pals at guild bases using WorkerDirector container IDs"""
        if not self.loaded:
            return []
        
        guilds = self.get_guilds()
        
        # Get base data and extract WorkerDirector container IDs
        base_camp_param = self.world_data.get("BaseCampSaveData", {})
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
                    # Get name and clean up Japanese template names
                    name = raw_val.get("name")
                    if isinstance(name, dict):
                        name = name.get("value")
                    
                    name_str = str(name) if name else ""
                    
                    # For now, just store the raw name - we'll assign sequential numbers later
                    if "新規生成拠点テンプレート名" in name_str:
                        # This is a template name, we'll replace it with sequential numbering
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
        
        # Now find all pals that belong to these containers
        char_save_param = self.world_data.get("CharacterSaveParameterMap", {})
        char_data = char_save_param.get("value", [])
        
        base_to_pals = {base_id: [] for base_id in base_to_container.keys()}
        
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
            
            # Get pal's container ID from SlotId
            slot_id = save_param.get("SlotId", {})
            if isinstance(slot_id, dict):
                # Path: SlotId.value.ContainerId.value.ID.value
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
                                            # Extract pal info
                                            char_id = save_param.get("CharacterID", {})
                                            if isinstance(char_id, dict):
                                                char_id = char_id.get("value", "Unknown")
                                            
                                            # Get instance_id from key
                                            key_data = entry.get("key", {})
                                            if isinstance(key_data, dict):
                                                instance_id = key_data.get("InstanceId", {}).get("value")
                                            else:
                                                instance_id = str(key_data)
                                            
                                            if not instance_id:
                                                continue
                                            
                                            # Helper function for extracting nested values
                                            def get_val(key, default=None):
                                                val = save_param.get(key)
                                                if val is None:
                                                    return default
                                                if isinstance(val, dict) and "value" in val:
                                                    val = val["value"]
                                                    if isinstance(val, dict) and "value" in val:
                                                        val = val["value"]
                                                return val if val is not None else default
                                            
                                            # Get pal name - handle BOSS_ prefix for localization
                                            lookup_id = char_id.replace("BOSS_", "") if char_id.startswith("BOSS_") else char_id
                                            pal_name = self.pal_names.get(lookup_id, char_id)
                                            
                                            # Get gender
                                            gender_data = save_param.get("Gender", {})
                                            if isinstance(gender_data, dict):
                                                gender_val = gender_data.get("value", {})
                                                if isinstance(gender_val, dict):
                                                    gender = gender_val.get("value", "Unknown")
                                                else:
                                                    gender = str(gender_val) if gender_val else "Unknown"
                                            else:
                                                gender = str(gender_data) if gender_data else "Unknown"
                                            
                                            # Clean up gender display (remove EPalGenderType:: prefix)
                                            if gender.startswith("EPalGenderType::"):
                                                gender = gender.replace("EPalGenderType::", "")
                                            
                                            # Get hunger and calculate percentage based on pal's max stomach
                                            hunger_raw = get_val("FullStomach", 150.0)
                                            if not isinstance(hunger_raw, (int, float)) or hunger_raw != hunger_raw:  # Check for NaN
                                                hunger_raw = 150.0
                                            
                                            # Get pal-specific max stomach, default to 150 if not found
                                            # Handle boss pals by removing BOSS_ prefix for lookup
                                            lookup_id = char_id
                                            if char_id.startswith("BOSS_"):
                                                lookup_id = char_id[5:]  # Remove "BOSS_" prefix
                                            max_stomach = self.pal_max_stomach.get(lookup_id, 150)
                                            # Calculate hunger as percentage: (current / max) * 100, capped at 100%
                                            hunger = min((hunger_raw / max_stomach) * 100, 100.0)
                                            
                                            # Get sanity - these are raw values typically 0-100
                                            sanity = get_val("SanityValue", 100.0)
                                            if not isinstance(sanity, (int, float)) or sanity != sanity:  # Check for NaN
                                                sanity = 100.0
                                            
                                            # Determine if this is a boss pal (either from save data or BOSS_ prefix)
                                            is_boss = get_val("IsBoss", False) or char_id.startswith("BOSS_")
                                            
                                            pal = PalInfo(
                                                instance_id=str(instance_id),
                                                character_id=str(char_id),
                                                name=str(pal_name),
                                                nickname=get_val("NickName"),
                                                level=get_val("Level", 1),
                                                exp=get_val("Exp", 0),
                                                owner_uid=None,  # Base pals don't have owners
                                                gender=gender,
                                                hp=get_val("HP", 100),
                                                max_hp=get_val("MaxHP", 100),
                                                mp=get_val("MP"),
                                                max_mp=get_val("MaxMP"),
                                                hunger=hunger,
                                                sanity=sanity,
                                                rank=get_val("Rank", 1),
                                                rank_hp=get_val("Rank_HP", 0),
                                                rank_attack=get_val("Rank_Attack", 0),
                                                rank_defense=get_val("Rank_Defense", 0),
                                                rank_craftspeed=get_val("Rank_CraftSpeed", 0),
                                                is_lucky=get_val("IsRarePal", False),
                                                is_boss=is_boss
                                            )
                                            base_to_pals[base_id].append(pal)
                                            break
        
        # Group bases by guild and assign sequential names
        guild_bases = {}
        for base_id, pals in base_to_pals.items():
            if not pals:
                continue
            
            guild_id = base_to_guild.get(base_id)
            if not guild_id:
                continue
            
            if guild_id not in guild_bases:
                guild_bases[guild_id] = []
            
            # Get original name
            original_name = base_to_name.get(base_id, f"Base {base_id[:8]}")
            
            guild_bases[guild_id].append({
                "base_id": base_id,
                "original_name": original_name,
                "pals": pals
            })
        
        # Assign sequential base names within each guild
        for guild_id, bases_data in guild_bases.items():
            for i, base_data in enumerate(bases_data):
                # If it's a template name or unnamed, use sequential numbering
                if base_data["original_name"] in ["template", "unnamed"] or base_data["original_name"].startswith("Base "):
                    base_data["base_name"] = f"Base {i + 1}"
                else:
                    base_data["base_name"] = base_data["original_name"]
        
        # Build final result with bases separated
        result = []
        guild_map = {str(g.guild_id): g for g in guilds}
        
        for guild_id, bases_data in guild_bases.items():
            guild = guild_map.get(guild_id)
            if not guild:
                continue
            
            # Create BaseInfo for each base
            base_infos = []
            for base_data in bases_data:
                if base_data["pals"]:
                    base_info = BaseInfo(
                        base_id=base_data["base_id"],
                        base_name=base_data["base_name"],
                        pals=base_data["pals"]
                    )
                    base_infos.append(base_info)
            
            if base_infos:
                guild_bases_info = GuildBasePalsInfo(
                    guild_id=guild.guild_id,
                    guild_name=guild.guild_name,
                    bases=base_infos
                )
                result.append(guild_bases_info)
        
        return result

# Global parser instance
parser = SaveFileParser()
