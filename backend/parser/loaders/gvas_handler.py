"""GVAS file operations for Palworld save files"""
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES

from backend.common.config import config
from backend.common.logging_config import get_logger

logger = get_logger(__name__)


class GvasHandler:
    """Handles GVAS file loading and decompression"""
    
    def __init__(self):
        self.level_sav_path: Optional[Path] = None
        self.players_dir: Optional[Path] = None
        self.gvas_data: Optional[Dict] = None
        self.world_data: Optional[Dict] = None
        self.world_name: Optional[str] = None
        self.loaded = False
        self.last_load_time: Optional[datetime] = None
    
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
            
            raw_gvas, _ = decompress_sav_to_gvas(sav_data)
            gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
            
            self.gvas_data = gvas_file.properties
            self.world_data = self.gvas_data.get("worldSaveData", {}).get("value", {})
            
            # Load world name from LevelMeta.sav
            self._load_world_name()
            
            self.loaded = True
            self.last_load_time = datetime.now()
            
            logger.info("✅ Save file loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load save file: {e}")
            self.loaded = False
            return False
    
    def _load_world_name(self):
        """Load world name from LevelMeta.sav"""
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
    
    def reload(self) -> bool:
        """Reload the save file"""
        logger.info("🔄 Reloading save file...")
        return self.load()
