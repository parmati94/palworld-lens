"""Stat calculation utilities for Palworld
Based on community research by u/blahable and datamined mechanics
"""
import math
import logging
from typing import Dict, Optional, List, Tuple

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


def calculate_trust_level(friendship_points: int, trust_thresholds: List[Tuple[int, int]]) -> int:
    """Calculate Trust Level from FriendshipPoint value
    
    Args:
        friendship_points: Raw FriendshipPoint value from save data
        trust_thresholds: List of (required_points, trust_level) tuples from data_loader
        
    Returns:
        Trust Level (0-10)
    """
    if friendship_points is None or not trust_thresholds:
        return 0
    
    for threshold, level in reversed(trust_thresholds):
        if friendship_points >= threshold:
            return level
    return 0


def calculate_pal_stats(
    species_scaling: Dict[str, int],
    level: int,
    talent_hp: int,
    talent_melee: int,
    talent_shot: int,
    talent_defense: int,
    rank: int = 1,
    trust_level: int = 0,
    friendship_multipliers: Optional[Dict[str, float]] = None,
    is_alpha: bool = False
) -> Dict[str, int]:
    """Calculate actual pal stats using the mathematically precise Palworld formulas
    
    Based on community research by u/blahable with exact formulas:
    - HP: floor(500 + (Level × 5) + (Level × SpeciesScaling_HP × 0.5 × (1 + (Talent_HP × 0.3)/100)))
    - Attack/Defense: floor(Base + (Level × SpeciesScaling × 0.075 × (1 + (Talent × 0.3)/100)))
    - Alpha/Boss Multiplier: 1.2x HP (as of v0.2.4.0, applied before trust bonuses)
    - Trust Bonus: BaseStat × (TrustLevel × FriendshipValue / 100)
    - Final: floor(BaseLevelStat × (1 + TrustBonus + RankBonus))
    
    Args:
        species_scaling: Dict with 'hp', 'attack', 'defense' scaling values for the species
        level: Pal level
        talent_hp: HP Individual Value (0-100)
        talent_melee: Melee Individual Value (0-100) 
        talent_shot: Shot Individual Value (0-100)
        talent_defense: Defense Individual Value (0-100)
        rank: Pal rank/stars (1-4, default 1)
        trust_level: Trust/Friendship Level (0-10, default 0)
        friendship_multipliers: Dict with friendship_hp, friendship_shotattack, friendship_defense
        is_alpha: Whether this is an alpha/boss pal (applies 1.2x HP multiplier)
        
    Returns:
        Dict with calculated 'attack', 'defense', 'hp', 'work_speed' values
    """
    try:
        if not species_scaling:
            logger.warning("No species scaling data provided")
            return {"attack": 0, "defense": 0, "hp": 0, "work_speed": 70}
        
        # Base values (Level 0)
        BASE_HP = 500
        BASE_ATTACK = 100
        BASE_DEFENSE = 50
        
        # IV bonuses (0.3% per IV point) - exactly as the formula states
        hp_talent_multiplier = 1 + (talent_hp * 0.3) / 100
        attack_talent_multiplier = 1 + (max(talent_melee, talent_shot) * 0.3) / 100  # Use higher of melee/shot
        defense_talent_multiplier = 1 + (talent_defense * 0.3) / 100
        
        # Step 1: Calculate base level stats (the "naked" stat) and floor
        # HP Formula: 500 + (Level × 5) + (Level × SpeciesScaling_HP × 0.5 × TalentMultiplier)
        hp_raw_growth = BASE_HP + (level * 5) + (level * species_scaling["hp"] * 0.5 * hp_talent_multiplier)
        
        # Apply Alpha/Boss HP Multiplier (v0.2.4.0: 1.2x for all Alpha/Lucky Pals)
        # Applied BEFORE trust bonuses, immediately after raw growth calculation
        if is_alpha:
            hp_base = math.floor(hp_raw_growth * 1.2)
        else:
            hp_base = math.floor(hp_raw_growth)
        
        # Attack Formula: 100 + (Level × SpeciesScaling_Attack × 0.075 × TalentMultiplier)  
        attack_base = math.floor(BASE_ATTACK + (level * species_scaling["attack"] * 0.075 * attack_talent_multiplier))
        
        # Defense Formula: 50 + (Level × SpeciesScaling_Defense × 0.075 × TalentMultiplier)
        defense_base = math.floor(BASE_DEFENSE + (level * species_scaling["defense"] * 0.075 * defense_talent_multiplier))
        
        # Step 2: Calculate Trust bonus as separate additive amount, floor it, then add to base
        # Trust bonus is calculated as: floor(base_stat × (TrustLevel × FriendshipValue / 100))
        # This is ADDITIVE, not multiplicative
        if trust_level > 0 and friendship_multipliers:
            if "friendship_hp" in friendship_multipliers:
                trust_bonus_pct = trust_level * friendship_multipliers["friendship_hp"] / 100
                hp_trust_bonus = math.floor(hp_base * trust_bonus_pct)
                hp_base = hp_base + hp_trust_bonus
            if "friendship_shotattack" in friendship_multipliers:
                trust_bonus_pct = trust_level * friendship_multipliers["friendship_shotattack"] / 100
                attack_trust_bonus = math.floor(attack_base * trust_bonus_pct)
                attack_base = attack_base + attack_trust_bonus
            if "friendship_defense" in friendship_multipliers:
                trust_bonus_pct = trust_level * friendship_multipliers["friendship_defense"] / 100
                defense_trust_bonus = math.floor(defense_base * trust_bonus_pct)
                defense_base = defense_base + defense_trust_bonus
        
        # Step 3: Apply rank bonuses (5% per rank above 1) to effective base and floor final result
        rank_multiplier = 1 + ((rank - 1) * 0.05)  # rank 1 = 1.0, rank 4 = 1.15
        calculated_hp = math.floor(hp_base * rank_multiplier)
        calculated_attack = math.floor(attack_base * rank_multiplier)
        calculated_defense = math.floor(defense_base * rank_multiplier)
        
        # Work speed (not affected by level scaling in the same way)
        calculated_work_speed = 70  # Default work speed
        
        return {
            "attack": calculated_attack,
            "defense": calculated_defense,
            "hp": calculated_hp,
            "work_speed": calculated_work_speed
        }
    except Exception as e:
        logger.warning(f"Error calculating stats: {e}")
        return {"attack": 0, "defense": 0, "hp": 0, "work_speed": 70}