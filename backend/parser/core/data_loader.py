"""Data loading from JSON files"""
import json
import logging
from typing import Dict
from pathlib import Path

from backend.config import config
from backend.logging_config import get_logger

logger = get_logger(__name__)


class DataLoader:
    """Handles loading of localization and game data from JSON files"""
    
    def __init__(self):
        self.pal_names: Dict[str, str] = {}
        self.pal_max_stomach: Dict[str, int] = {}
        self.pal_species_data: Dict[str, Dict] = {}
        self.active_skill_names: Dict[str, str] = {}
        self.passive_skill_names: Dict[str, str] = {}
        self.work_suitability_names: Dict[str, str] = {}
        self.active_skill_data: Dict[str, Dict] = {}
        self.passive_skill_data: Dict[str, Dict] = {}
        
        self._load_pal_names()
        self._load_pal_data()
        self._load_skill_names()
    
    def _load_pal_names(self):
        """Load pal name mappings from JSON"""
        try:
            pals_json = config.DATA_PATH / "json" / "l10n" / "en" / "pals.json"
            if pals_json.exists():
                with open(pals_json, 'r') as f:
                    data = json.load(f)
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
            pals_json = config.DATA_PATH / "json" / "pals.json"
            if pals_json.exists():
                with open(pals_json, 'r') as f:
                    data = json.load(f)
                    self.pal_species_data = data
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
                            self.active_skill_data[skill_id] = {
                                "name": skill_data.get("localized_name", skill_id),
                                "description": skill_data.get("description", "")
                            }
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
                            self.passive_skill_data[skill_id] = {
                                "name": skill_data.get("localized_name", skill_id),
                                "description": skill_data.get("description", "")
                            }
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
