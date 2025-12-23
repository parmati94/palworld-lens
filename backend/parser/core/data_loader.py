"""Data loading from JSON files"""
import json
import logging
from typing import Dict, Optional
from pathlib import Path

from backend.core.config import config
from backend.core.logging_config import get_logger

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
        self.active_skill_data: Dict[str, Dict] = {}  # l10n data (name, description)
        self.passive_skill_data: Dict[str, Dict] = {}  # l10n data (name, description)
        self.active_skill_full_data: Dict[str, Dict] = {}  # Full data (element, power, etc.)
        self.passive_skill_full_data: Dict[str, Dict] = {}  # Full data (rank, effects, etc.)
        self.element_display_names: Dict[str, str] = {}
        self.trust_thresholds: list = []  # List of (required_points, trust_level) tuples
        
        self._load_pal_names()
        self._load_pal_data()
        self._load_skill_names()
        self._load_full_skill_data()
        self._load_element_names()
        self._load_trust_thresholds()
    
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
    
    def _load_full_skill_data(self):
        """Load full skill data from game data JSON (element, power, rank, etc.)"""
        try:
            # Load full active skill data (element, power, cooldown, etc.)
            active_skills_json = config.DATA_PATH / "json" / "active_skills.json"
            if active_skills_json.exists():
                with open(active_skills_json, 'r', encoding='utf-8') as f:
                    self.active_skill_full_data = json.load(f)
                logger.debug(f"Loaded full data for {len(self.active_skill_full_data)} active skills")
            else:
                logger.warning(f"Active skills data file not found: {active_skills_json}")
            
            # Load full passive skill data (rank, effects, etc.)
            passive_skills_json = config.DATA_PATH / "json" / "passive_skills.json"
            if passive_skills_json.exists():
                with open(passive_skills_json, 'r', encoding='utf-8') as f:
                    self.passive_skill_full_data = json.load(f)
                logger.debug(f"Loaded full data for {len(self.passive_skill_full_data)} passive skills")
            else:
                logger.warning(f"Passive skills data file not found: {passive_skills_json}")
        except Exception as e:
            logger.warning(f"Could not load full skill data: {e}")
    
    def _load_element_names(self):
        """Load element display name mappings from JSON"""
        try:
            elements_json = config.DATA_PATH / "json" / "l10n" / "en" / "elements.json"
            if elements_json.exists():
                with open(elements_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for element_id, element_data in data.items():
                        if isinstance(element_data, dict) and "localized_name" in element_data:
                            self.element_display_names[element_id] = element_data["localized_name"]
                logger.debug(f"Loaded {len(self.element_display_names)} element display names")
            else:
                logger.warning(f"Element names file not found: {elements_json}")
        except Exception as e:
            logger.warning(f"Could not load element names: {e}")
    
    def _load_trust_thresholds(self):
        """Load Trust Level thresholds from friendship.json"""
        try:
            friendship_json = config.DATA_PATH / "json" / "friendship.json"
            if friendship_json.exists():
                with open(friendship_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert to sorted list of (threshold, level) tuples
                thresholds = []
                for key, value in data.items():
                    if key.startswith("Friendship_Rank_") and not key.endswith("Minus1") and not key.endswith("Minus2"):
                        rank = value.get("rank", 0)
                        required = value.get("required_point", 0)
                        if rank >= 0 and required >= 0:
                            thresholds.append((required, rank))
                
                # Sort by threshold ascending
                thresholds.sort(key=lambda x: x[0])
                self.trust_thresholds = thresholds
                logger.debug(f"Loaded {len(thresholds)} trust level thresholds")
            else:
                logger.warning(f"Trust thresholds file not found: {friendship_json}")
        except Exception as e:
            logger.warning(f"Could not load trust thresholds: {e}")
    
    def get_species_scaling(self, character_id: str) -> Optional[Dict[str, int]]:
        """Get species scaling values from pals.json"""
        try:
            species_data = self.pal_species_data.get(character_id)
            if species_data and "scaling" in species_data:
                scaling = species_data["scaling"]
                return scaling
            else:
                logger.warning(f"No scaling data found for character_id: {character_id}")
        except Exception as e:
            logger.warning(f"Error getting species scaling for {character_id}: {e}")
        return None
