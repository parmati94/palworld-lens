"""Palworld save file parser - Main orchestrator

This module provides the main SaveFileParser class that coordinates
all parsing operations across the different submodules.
"""
import logging
from typing import List, Dict, Optional

from backend.models.models import SaveInfo, PalInfo, PlayerInfo, GuildInfo, BaseContainerInfo
from backend.parser.loaders.gvas_handler import GvasHandler
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.extractors.characters import get_character_data
from backend.parser.extractors.relationships import build_player_mapping, build_pal_ownership
from backend.parser.builders.pals import build_pals
from backend.parser.builders.players import build_players
from backend.parser.builders.guilds import build_guilds
from backend.parser.builders.base_containers import build_base_containers
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Preload all schemas
SchemaManager.preload_all()


class SaveFileParser:
    """Parser for Palworld save files - coordinates all parsing operations"""
    
    def __init__(self):
        self.gvas = GvasHandler()
        self.data = DataLoader()
        self.player_uid_to_containers: Dict = {}
        self.player_names: Dict[str, str] = {}
        self.pal_to_owner: Dict[str, str] = {}
    
    def load(self) -> bool:
        """Load save files from mounted directory"""
        if not self.gvas.load():
            return False
        
        # Build relationship mappings
        self.player_uid_to_containers, self.player_names = build_player_mapping(
            self.gvas.world_data,
            self.gvas.players_dir
        )
        self.pal_to_owner = build_pal_ownership(
            self.gvas.world_data,
            self.player_uid_to_containers
        )
        
        return True
    
    def reload(self) -> bool:
        """Reload the save file"""
        logger.info("🔄 Reloading save file...")
        return self.load()
    
    @property
    def loaded(self) -> bool:
        """Check if save file is loaded"""
        return self.gvas.loaded
    
    @property
    def last_load_time(self):
        """Get last load time"""
        return self.gvas.last_load_time
    
    def get_save_info(self) -> SaveInfo:
        """Get basic save file information"""
        if not self.gvas.loaded:
            return SaveInfo(world_name="Not Loaded", loaded=False)
        
        world_name = self.gvas.world_name or "My World"
        
        # Get counts
        char_data = get_character_data(self.gvas.world_data)
        player_count = sum(1 for char_info in char_data.values() 
                          if isinstance(char_info, dict) and char_info.get("IsPlayer", {}).get("value", False))
        pal_count = len(char_data) - player_count
        
        # Get guilds
        actual_guilds = self.get_guilds()
        
        # Get file sizes
        file_size = None
        level_meta_path = None
        level_meta_size = None
        
        if self.gvas.level_sav_path and self.gvas.level_sav_path.exists():
            try:
                file_size = self.gvas.level_sav_path.stat().st_size
            except Exception as e:
                logger.debug(f"Could not get Level.sav size: {e}")
            
            level_meta_file = self.gvas.level_sav_path.parent / "LevelMeta.sav"
            if level_meta_file.exists():
                level_meta_path = str(level_meta_file)
                try:
                    level_meta_size = level_meta_file.stat().st_size
                except Exception as e:
                    logger.debug(f"Could not get LevelMeta.sav size: {e}")
        
        return SaveInfo(
            world_name=world_name,
            loaded=True,
            level_path=str(self.gvas.level_sav_path) if self.gvas.level_sav_path else None,
            level_meta_path=level_meta_path,
            player_count=player_count,
            guild_count=len(actual_guilds),
            pal_count=pal_count,
            last_updated=self.gvas.last_load_time.isoformat() if self.gvas.last_load_time else None,
            file_size=file_size,
            level_meta_size=level_meta_size
        )
    
    def get_players(self) -> List[PlayerInfo]:
        """Get list of all players"""
        if not self.gvas.loaded:
            return []
        return build_players(self.gvas.world_data, self.player_uid_to_containers)
    
    def get_guilds(self) -> List[GuildInfo]:
        """Get list of all guilds"""
        if not self.gvas.loaded:
            return []
        return build_guilds(self.gvas.world_data)
    
    def get_pals(self) -> List[PalInfo]:
        """Get list of all pals (non-player characters)"""
        if not self.gvas.loaded:
            return []
        return build_pals(self.gvas.world_data, self.data, self.pal_to_owner)
    
    def get_base_containers(self) -> Dict[str, List[BaseContainerInfo]]:
        """Get base containers grouped by base ID"""
        if not self.gvas.loaded:
            return {}
        return build_base_containers(self.gvas.world_data, self.data)


# Global parser instance
parser = SaveFileParser()
