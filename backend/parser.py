"""Save file parser - wraps palworld-save-tools library"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.config import config
from backend.logging_config import get_logger
from backend.models import SaveInfo, PalInfo, PlayerInfo, GuildInfo, GuildBasePalsInfo, BaseInfo, SkillInfo

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
        self.world_name: Optional[str] = None  # Cached world name from LevelMeta.sav
        self.pal_names: Dict[str, str] = {}
        self.pal_max_stomach: Dict[str, int] = {}  # Maps pal character_id to max stomach
        self.player_uid_to_instance: Dict[str, str] = {}  # Maps PlayerUId to instance_id
        self.player_names: Dict[str, str] = {}  # Maps PlayerUId to player names
        self.pal_species_data: Dict[str, Dict] = {}  # Maps character_id to full species data
        self.active_skill_names: Dict[str, str] = {}  # Maps EPalWazaID to localized name
        self.passive_skill_names: Dict[str, str] = {}  # Maps passive skill ID to localized name
        self.work_suitability_names: Dict[str, str] = {}  # Maps work suitability ID to localized name
        self.active_skill_data: Dict[str, Dict] = {}  # Maps EPalWazaID to full skill data (name + description)
        self.passive_skill_data: Dict[str, Dict] = {}  # Maps passive skill ID to full skill data (name + description)
        self._load_pal_names()
        self._load_pal_data()
        self._load_skill_names()
    
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
                logger.debug(f"Loaded {len(self.pal_names)} pal names")
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
                    # Store full species data
                    self.pal_species_data = data
                    # Extract max_full_stomach for each pal
                    for pal_id, pal_info in data.items():
                        if isinstance(pal_info, dict) and "max_full_stomach" in pal_info:
                            self.pal_max_stomach[pal_id] = pal_info["max_full_stomach"]
                logger.debug(f"Loaded max stomach data for {len(self.pal_max_stomach)} pals")
            else:
                logger.warning(f"Pal data file not found: {pals_json}")
        except Exception as e:
            logger.warning(f"Could not load pal data: {e}")
    
    def _load_skill_names(self):
        """Load localized skill names and descriptions from JSON"""
        try:
            # Load active skill data
            active_skills_json = config.DATA_PATH / "json" / "l10n" / "en" / "active_skills.json"
            if active_skills_json.exists():
                with open(active_skills_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for skill_id, skill_data in data.items():
                        if isinstance(skill_data, dict):
                            # Store full data (name + description)
                            self.active_skill_data[skill_id] = {
                                "name": skill_data.get("localized_name", skill_id),
                                "description": skill_data.get("description", "")
                            }
                            # Keep backward compatibility with name-only dict
                            if "localized_name" in skill_data:
                                self.active_skill_names[skill_id] = skill_data["localized_name"]
                logger.debug(f"Loaded {len(self.active_skill_names)} active skill names")
            
            # Load passive skill data
            passive_skills_json = config.DATA_PATH / "json" / "l10n" / "en" / "passive_skills.json"
            if passive_skills_json.exists():
                with open(passive_skills_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for skill_id, skill_data in data.items():
                        if isinstance(skill_data, dict):
                            # Store full data (name + description)
                            self.passive_skill_data[skill_id] = {
                                "name": skill_data.get("localized_name", skill_id),
                                "description": skill_data.get("description", "")
                            }
                            # Keep backward compatibility with name-only dict
                            if "localized_name" in skill_data:
                                self.passive_skill_names[skill_id] = skill_data["localized_name"]
                logger.debug(f"Loaded {len(self.passive_skill_names)} passive skill names")

            # Load work suitability data
            work_suitability_json = config.DATA_PATH / "json" / "l10n" / "en" / "work_suitability.json"
            if work_suitability_json.exists():
                with open(work_suitability_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for work_id, work_data in data.items():
                        if isinstance(work_data, dict) and "localized_name" in work_data:
                            self.work_suitability_names[work_id] = work_data["localized_name"]
                logger.debug(f"Loaded {len(self.work_suitability_names)} work suitability names")
        except Exception as e:
            logger.warning(f"Could not load skill names: {e}")
    
    def _get_work_suitability_display(self, work_suitability: Dict[str, int]) -> List[Dict[str, Any]]:
        """Convert work suitability dict to rich display data with names, icons, and color-coded levels"""
        # Map work types to their icon numbers (based on research icons)
        work_icon_mapping = {
            "EmitFlame": "00",       # Kindling
            "Watering": "01",        # Watering  
            "Seeding": "02",         # Planting
            "GenerateElectricity": "03", # Generating Electricity
            "Handcraft": "04",       # Handiwork
            "Collection": "05",      # Gathering
            "Deforest": "06",        # Lumbering
            "Mining": "07",          # Mining
            "ProductMedicine": "08", # Medicine Production
            "Cool": "09",            # Cooling
            "Transport": "10",       # Transporting (box icon)
            "MonsterFarm": "11",     # Farming
        }
        
        # Level color mapping (1=common, 5=very rare)
        level_colors = {
            1: "#9ca3af",  # gray-400
            2: "#22c55e",  # green-500
            3: "#3b82f6",  # blue-500
            4: "#8b5cf6",  # violet-500
            5: "#f59e0b",  # amber-500
        }
        
        display_data = []
        for work_type, level in work_suitability.items():
            if level > 0:
                display_name = self.work_suitability_names.get(work_type, work_type)
                icon_num = work_icon_mapping.get(work_type, "00")
                color = level_colors.get(level, "#9ca3af")
                
                display_data.append({
                    "type": work_type,
                    "name": display_name,
                    "level": level,
                    "icon": f"t_icon_research_palwork_{icon_num}_0",
                    "color": color
                })
        
        return display_data
        
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
            
            # Read and cache world name from LevelMeta.sav (only once per load)
            try:
                level_meta_path = self.level_sav_path.parent / "LevelMeta.sav"
                if level_meta_path.exists():
                    with open(level_meta_path, "rb") as f:
                        meta_data = f.read()
                    raw_meta_gvas, _ = decompress_sav_to_gvas(meta_data)
                    meta_gvas_file = GvasFile.read(raw_meta_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
                    save_data = meta_gvas_file.properties.get("SaveData", {}).get("value", {})
                    world_name_data = save_data.get("WorldName", {})
                    if isinstance(world_name_data, dict) and "value" in world_name_data:
                        self.world_name = world_name_data["value"]
                        logger.debug(f"Cached world name from LevelMeta.sav: {self.world_name}")
            except Exception as e:
                logger.debug(f"Could not cache world name from LevelMeta.sav: {e}")
            
            self.loaded = True
            self.last_load_time = datetime.now()
            
            # Build player UID mapping and pal ownership on load
            self._build_player_mapping()
            self._build_pal_ownership()
            
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
        """Build mapping from PlayerUId to player names and their containers"""
        self.player_uid_to_containers = {}  # Maps PlayerUId -> {name, containers: []}
        
        # Get players from Level.sav first - this has the names
        players_data = self._get_player_data()
        logger.info(f"_build_player_mapping: Found {len(players_data)} players in Level.sav")
        
        # Build temporary mapping of instance_id -> player name
        instance_to_name = {}
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
            
            player_name = get_val("NickName", "Unknown")
            instance_to_name[str(instance_id)] = player_name
            logger.info(f"Player from Level.sav: {player_name} (instance_id: {instance_id[:16]}...)")
        
        # Now read Players/*.sav files to get their PlayerUId and container IDs
        if self.players_dir and self.players_dir.exists():
            for player_sav in self.players_dir.glob("*.sav"):
                try:
                    filename_uid = player_sav.stem
                    if len(filename_uid) == 32:
                        # Format as UUID
                        formatted_uid = f"{filename_uid[0:8]}-{filename_uid[8:12]}-{filename_uid[12:16]}-{filename_uid[16:20]}-{filename_uid[20:32]}"
                        formatted_uid = formatted_uid.lower()
                        
                        # Read the .sav file
                        with open(player_sav, "rb") as f:
                            sav_data = f.read()
                        
                        raw_gvas, _ = decompress_sav_to_gvas(sav_data)
                        gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
                        
                        save_data = gvas_file.properties.get("SaveData", {})
                        if isinstance(save_data, dict):
                            save_val = save_data.get("value", {})
                            if isinstance(save_val, dict):
                                # Get PlayerUId
                                player_uid = formatted_uid  # Default to filename
                                player_uid_data = save_val.get("PlayerUId", {})
                                if isinstance(player_uid_data, dict) and "value" in player_uid_data:
                                    player_uid = str(player_uid_data["value"])
                                
                                # Get IndividualId to match with Level.sav
                                individual_id = None
                                ind_id_data = save_val.get("IndividualId", {})
                                if isinstance(ind_id_data, dict) and "value" in ind_id_data:
                                    ind_val = ind_id_data["value"]
                                    if isinstance(ind_val, dict) and "InstanceId" in ind_val:
                                        inst_id_data = ind_val["InstanceId"]
                                        if isinstance(inst_id_data, dict) and "value" in inst_id_data:
                                            individual_id = str(inst_id_data["value"])
                                
                                # Get player name from instance_to_name mapping
                                player_name = instance_to_name.get(individual_id, f"Player_{filename_uid[:8].upper()}")
                                
                                # Get container IDs
                                container_ids = []
                                for field in ["OtomoCharacterContainerId", "PalStorageContainerId"]:
                                    if field in save_val:
                                        cont_data = save_val[field]
                                        if isinstance(cont_data, dict) and "value" in cont_data:
                                            cont_val = cont_data["value"]
                                            if isinstance(cont_val, dict) and "ID" in cont_val:
                                                id_data = cont_val["ID"]
                                                if isinstance(id_data, dict) and "value" in id_data:
                                                    container_ids.append(str(id_data["value"]))
                                
                                # Store in mapping
                                self.player_uid_to_containers[player_uid] = {"name": player_name, "containers": container_ids, "instance_id": individual_id}
                                self.player_names[player_uid] = player_name
                                logger.debug(f"  -> {player_name}: PlayerUId={player_uid[:16]}..., {len(container_ids)} containers")
                except Exception as e:
                    logger.warning(f"Failed to read player .sav {player_sav.name}: {e}")
        
        # Now add base worker containers to player mappings
        # First, build a mapping of guild_id -> player_uids
        guild_to_players = {}  # Maps guild_id -> list of PlayerUIDs
        guild_data = self.world_data.get("GroupSaveDataMap", {})
        if isinstance(guild_data, dict):
            guilds = guild_data.get("value", [])
            for guild in guilds:
                if isinstance(guild, dict):
                    guild_id = guild.get("key")
                    value = guild.get("value", {})
                    if isinstance(value, dict):
                        raw_data = value.get("RawData", {})
                        if isinstance(raw_data, dict):
                            raw_val = raw_data.get("value", {})
                            if isinstance(raw_val, dict):
                                players = raw_val.get("players", [])
                                if players and guild_id:
                                    player_uids = []
                                    for player in players:
                                        if isinstance(player, dict):
                                            player_uid = player.get("player_uid")
                                            if player_uid:
                                                player_uids.append(str(player_uid))
                                    if player_uids:
                                        guild_to_players[str(guild_id)] = player_uids
        
        logger.info(f"Found {len(guild_to_players)} guilds with players")
        
        # Now process base camps and link to players through guilds
        base_camp_data = self.world_data.get("BaseCampSaveData", {})
        if isinstance(base_camp_data, dict):
            base_camps = base_camp_data.get("value", [])
            logger.info(f"Checking {len(base_camps)} base camps for worker containers")
            
            for base in base_camps:
                if isinstance(base, dict):
                    value = base.get("value", {})
                    if isinstance(value, dict):
                        # Get base guild_id
                        raw_data = value.get("RawData", {})
                        if isinstance(raw_data, dict):
                            raw_val = raw_data.get("value", {})
                            if isinstance(raw_val, dict):
                                guild_id = raw_val.get("group_id_belong_to")
                                if guild_id:
                                    guild_id_str = str(guild_id)
                                    
                                    # Get worker container ID
                                    worker_dir = value.get("WorkerDirector", {})
                                    if isinstance(worker_dir, dict):
                                        wd_val = worker_dir.get("value", {})
                                        if isinstance(wd_val, dict):
                                            wd_raw = wd_val.get("RawData", {})
                                            if isinstance(wd_raw, dict):
                                                wd_raw_val = wd_raw.get("value", {})
                                                if isinstance(wd_raw_val, dict):
                                                    container_id = wd_raw_val.get("container_id")
                                                    if container_id:
                                                        container_id_str = str(container_id)
                                                        
                                                        # Find players in this guild and add container
                                                        player_uids = guild_to_players.get(guild_id_str, [])
                                                        for player_uid in player_uids:
                                                            if player_uid in self.player_uid_to_containers:
                                                                self.player_uid_to_containers[player_uid]["containers"].append(container_id_str)
                                                                player_name = self.player_uid_to_containers[player_uid]["name"]
                                                                logger.debug(f"  -> Added base worker container for {player_name}")
        
        logger.info(f"Mapped {len(self.player_names)} players with containers")
    
    def _build_pal_ownership(self):
        """Build mapping from pal instance_id to owner by reading player .sav files and their containers"""
        self.pal_to_owner = {}  # Maps pal instance_id -> player name
        
        if not self.players_dir or not self.players_dir.exists():
            logger.warning("Players directory not found, cannot build pal ownership")
            return
        
        # Get character containers from Level.sav
        char_container_data = self.world_data.get("CharacterContainerSaveData", {})
        if not isinstance(char_container_data, dict):
            logger.warning("CharacterContainerSaveData not found")
            return
        
        containers = char_container_data.get("value", [])
        container_map = {}  # Maps container ID -> list of pal instance_ids
        
        # Build container ID to pal instance IDs mapping
        for container in containers:
            if not isinstance(container, dict):
                continue
            
            key_data = container.get("key", {})
            if isinstance(key_data, dict) and "ID" in key_data:
                container_id_data = key_data["ID"]
                if isinstance(container_id_data, dict) and "value" in container_id_data:
                    container_id = str(container_id_data["value"])
                    
                    # Get slots
                    value_data = container.get("value", {})
                    if isinstance(value_data, dict):
                        slots_data = value_data.get("Slots", {})
                        if isinstance(slots_data, dict):
                            slots_value = slots_data.get("value", {})
                            if isinstance(slots_value, dict):
                                slots = slots_value.get("values", [])
                                pal_ids = []
                                for slot in slots:
                                    if isinstance(slot, dict) and "RawData" in slot:
                                        slot_raw = slot["RawData"]
                                        if isinstance(slot_raw, dict) and "value" in slot_raw:
                                            slot_val = slot_raw["value"]
                                            if isinstance(slot_val, dict) and "instance_id" in slot_val:
                                                # instance_id is directly in the value dict
                                                pal_instance_id = str(slot_val["instance_id"])
                                                if pal_instance_id and '00000000-0000-0000-0000-000000000000' not in pal_instance_id:
                                                    pal_ids.append(pal_instance_id)
                                if pal_ids:
                                    container_map[container_id] = pal_ids
        
        logger.debug(f"Found {len(container_map)} containers with pals")
        
        # Map pals to players using the container lists we already built
        for player_uid, player_data in self.player_uid_to_containers.items():
            player_name = player_data["name"]
            player_containers = player_data["containers"]
            pal_count = 0
            
            for container_id in player_containers:
                if container_id in container_map:
                    for pal_id in container_map[container_id]:
                        self.pal_to_owner[pal_id] = player_name
                        pal_count += 1
            
            logger.debug(f"Player {player_name}: {pal_count} pals in {len(player_containers)} containers")
        
        logger.info(f"Loaded {len(self.pal_to_owner)} pals across all players")
    
    def get_save_info(self) -> SaveInfo:
        """Get basic save file information"""
        if not self.loaded:
            return SaveInfo(world_name="Not Loaded", loaded=False)
        
        # Use cached world name if available, otherwise default
        world_name = self.world_name or "My World"
        
        # Simplify - just count the data
        char_data = self._get_character_data()
        guild_data = self._get_guild_data()
        
        # Count players (characters with IsPlayer flag)
        player_count = sum(1 for char_info in char_data.values() 
                          if isinstance(char_info, dict) and char_info.get("IsPlayer", {}).get("value", False))
        
        # Pal count is total characters minus players
        pal_count = len(char_data) - player_count
        
        # Count actual player guilds (not all guild-like groups)
        actual_guilds = self.get_guilds()
        
        return SaveInfo(
            world_name=world_name,
            loaded=True,
            level_path=str(self.level_sav_path) if self.level_sav_path else None,
            player_count=player_count,
            guild_count=len(actual_guilds),
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
            
            # Get owner name from pal_to_owner mapping (built from player .sav files)
            owner_name = self.pal_to_owner.get(str(instance_id))
            
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
            
            # DEBUG: Log all fields for ChickiPi to understand data structure
            if "ChickiPi" in char_id:
                logger.info(f"=== DEBUG ChickiPi Data ===")
                logger.info(f"CharacterID: {char_id}")
                logger.info(f"IsBoss field: {get_val('IsBoss', 'NOT_FOUND')}")
                logger.info(f"IsRarePal field: {get_val('IsRarePal', 'NOT_FOUND')}")
                logger.info(f"Rank: {get_val('Rank', 'NOT_FOUND')}")
                logger.info(f"Level: {get_val('Level', 'NOT_FOUND')}")
                # Log other potential alpha indicators
                for field in ['IsAlpha', 'AlphaPal', 'IsSpecial', 'SpecialPal', 'BossType', 'PalType', 'PalVariant']:
                    logger.info(f"{field}: {get_val(field, 'NOT_FOUND')}")
                # Log all available keys to see what we're working with
                logger.info(f"Available keys: {list(char_info.keys())[:20]}...")  # First 20 keys
                logger.info(f"=== END ChickiPi Data ===")
            
            
            # Extract active skills from EquipWaza
            active_skills = []
            equip_waza = char_info.get("EquipWaza", {})
            if isinstance(equip_waza, dict) and "value" in equip_waza:
                waza_values = equip_waza["value"]
                if isinstance(waza_values, dict) and "values" in waza_values:
                    for skill in waza_values["values"]:
                        skill_id = str(skill)
                        # Look up full skill data
                        skill_data = self.active_skill_data.get(skill_id, {})
                        if skill_data:
                            active_skills.append(SkillInfo(
                                name=skill_data["name"],
                                description=skill_data["description"]
                            ))
                        else:
                            # Fallback for unknown skills
                            skill_name = skill_id.replace("EPalWazaID::", "")
                            active_skills.append(SkillInfo(
                                name=skill_name,
                                description=""
                            ))
            
            # Extract passive skills from PassiveSkillList
            passive_skills = []
            passive_list = char_info.get("PassiveSkillList", {})
            if isinstance(passive_list, dict) and "value" in passive_list:
                passive_values = passive_list["value"]
                if isinstance(passive_values, dict) and "values" in passive_values:
                    for skill in passive_values["values"]:
                        skill_id = str(skill)
                        # Look up full skill data
                        skill_data = self.passive_skill_data.get(skill_id, {})
                        if skill_data:
                            passive_skills.append(SkillInfo(
                                name=skill_data["name"],
                                description=skill_data["description"]
                            ))
                        else:
                            # Fallback for unknown skills
                            passive_skills.append(SkillInfo(
                                name=skill_id,
                                description=""
                            ))
            
            # Get element types and work suitability from species data
            element_types = []
            work_suitability = {}
            species_data = self.pal_species_data.get(lookup_id, {})
            if species_data:
                element_types = species_data.get("element_types", [])
                work_suitability = species_data.get("work_suitability", {})
            
            # Create rich work suitability display data
            work_suitability_display = self._get_work_suitability_display(work_suitability)
            
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
                talent_hp=get_val("Talent_HP", 0),
                talent_melee=get_val("Talent_Melee", 0),
                talent_shot=get_val("Talent_Shot", 0),
                talent_defense=get_val("Talent_Defense", 0),
                active_skills=active_skills,
                passive_skills=passive_skills,
                element_types=element_types,
                work_suitability=work_suitability,
                work_suitability_display=work_suitability_display,
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
                                            
                                            # Extract active skills from EquipWaza
                                            active_skills = []
                                            equip_waza = save_param.get("EquipWaza", {})
                                            if isinstance(equip_waza, dict) and "value" in equip_waza:
                                                waza_values = equip_waza["value"]
                                                if isinstance(waza_values, dict) and "values" in waza_values:
                                                    for skill in waza_values["values"]:
                                                        skill_id = str(skill)
                                                        # Look up full skill data
                                                        skill_data = self.active_skill_data.get(skill_id, {})
                                                        if skill_data:
                                                            active_skills.append(SkillInfo(
                                                                name=skill_data["name"],
                                                                description=skill_data["description"]
                                                            ))
                                                        else:
                                                            # Fallback for unknown skills
                                                            skill_name = skill_id.replace("EPalWazaID::", "")
                                                            active_skills.append(SkillInfo(
                                                                name=skill_name,
                                                                description=""
                                                            ))
                                            
                                            # Extract passive skills from PassiveSkillList
                                            passive_skills = []
                                            passive_list = save_param.get("PassiveSkillList", {})
                                            if isinstance(passive_list, dict) and "value" in passive_list:
                                                passive_values = passive_list["value"]
                                                if isinstance(passive_values, dict) and "values" in passive_values:
                                                    for skill in passive_values["values"]:
                                                        skill_id = str(skill)
                                                        # Look up full skill data
                                                        skill_data = self.passive_skill_data.get(skill_id, {})
                                                        if skill_data:
                                                            passive_skills.append(SkillInfo(
                                                                name=skill_data["name"],
                                                                description=skill_data["description"]
                                                            ))
                                                        else:
                                                            # Fallback for unknown skills
                                                            passive_skills.append(SkillInfo(
                                                                name=skill_id,
                                                                description=""
                                                            ))
                                            
                                            # Get element types and work suitability from species data
                                            element_types = []
                                            work_suitability = {}
                                            lookup_id = char_id.replace("BOSS_", "") if char_id.startswith("BOSS_") else char_id
                                            species_data = self.pal_species_data.get(lookup_id, {})
                                            if species_data:
                                                element_types = species_data.get("element_types", [])
                                                work_suitability = species_data.get("work_suitability", {})
                                            
                                            # Create rich work suitability display data
                                            work_suitability_display = self._get_work_suitability_display(work_suitability)
                                            
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
                                                talent_hp=get_val("Talent_HP", 0),
                                                talent_melee=get_val("Talent_Melee", 0),
                                                talent_shot=get_val("Talent_Shot", 0),
                                                talent_defense=get_val("Talent_Defense", 0),
                                                active_skills=active_skills,
                                                passive_skills=passive_skills,
                                                element_types=element_types,
                                                work_suitability=work_suitability,
                                                work_suitability_display=work_suitability_display,
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
