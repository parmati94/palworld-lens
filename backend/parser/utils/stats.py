"""Stat calculation utilities for Palworld
Based on community research by u/blahable and datamined mechanics
"""
import math
import logging
from typing import Dict, Optional, List, Tuple, Any

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
    is_alpha: bool = False,
    passive_skills: Optional[List] = None
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
        
        # === HP CALCULATION (CORRECTED) ===
        # Step 1: Calculate static HP (500 base) - NEVER affected by trust/alpha/IV
        static_hp = BASE_HP
        
        # Step 2: Calculate level-based growth components
        level_growth = level * 5  # Flat HP per level
        species_growth = level * species_scaling["hp"] * 0.5  # Species-specific scaling
        
        # Step 3: Calculate IV (Talent) bonus - applies to species growth only
        # Talent bonus is SEPARATE from trust bonus
        iv_bonus_hp = species_growth * (talent_hp * 0.3 / 100)
        
        # Step 4: Calculate Trust bonus - applies to (species_growth + level_growth)
        # Trust bonus uses the combined growth, NOT including static base or IV
        trust_bonus_hp = 0
        if trust_level > 0 and friendship_multipliers and "friendship_hp" in friendship_multipliers:
            hp_mult = friendship_multipliers["friendship_hp"] / 100
            # CRITICAL: Trust applies to BOTH species scaling AND level growth
            trust_bonus_hp = math.floor((species_growth + level_growth) * (trust_level * hp_mult))
        
        # Step 5: Apply Alpha/Boss HP Multiplier (v0.2.4.0: 1.2x for all Alpha/Lucky Pals)
        # Applied to species growth before assembly
        applied_growth = species_growth
        if is_alpha:
            applied_growth = applied_growth * 1.2
        
        # Step 6: Assemble final HP base: static + level_growth + (species_growth + IV) + trust
        # Floor the species_growth+IV together, then add everything
        hp_effective_base = static_hp + level_growth + math.floor(applied_growth + iv_bonus_hp) + trust_bonus_hp
        
        # Step 7: Apply rank multiplier to assembled HP
        rank_multiplier = 1 + ((rank - 1) * 0.05)  # rank 1 = 1.0, rank 4 = 1.15
        calculated_hp = math.floor(hp_effective_base * rank_multiplier)
        
        # === ATTACK CALCULATION ===
        # Step 1: Static Attack (100) - NEVER affected by trust/IV
        static_attack = BASE_ATTACK
        
        # Step 2: Species Growth
        attack_growth = level * species_scaling["attack"] * 0.075
        
        # Step 3: IV Bonus - applies to species growth
        attack_iv_bonus = attack_growth * (max(talent_melee, talent_shot) * 0.3 / 100)
        
        # Step 4: Trust Bonus - applies to (SPECIES GROWTH + IV)
        attack_trust_bonus = 0
        if trust_level > 0 and friendship_multipliers and "friendship_shotattack" in friendship_multipliers:
            attack_mult = friendship_multipliers["friendship_shotattack"] / 100
            # Trust applies to the combined growth (species + IV), not just species
            attack_trust_bonus = math.floor((attack_growth + attack_iv_bonus) * (trust_level * attack_mult))
            
        # Step 5: Assemble
        attack_effective_base = static_attack + math.floor(attack_growth + attack_iv_bonus) + attack_trust_bonus
        
        # === DEFENSE CALCULATION ===
        # Step 1: Static Defense (50) - NEVER affected by trust/IV
        static_defense = BASE_DEFENSE
        
        # Step 2: Species Growth
        defense_growth = level * species_scaling["defense"] * 0.075
        
        # Step 3: IV Bonus - applies to species growth
        defense_iv_bonus = defense_growth * (talent_defense * 0.3 / 100)
        
        # Step 4: Trust Bonus - applies to (SPECIES GROWTH + IV)
        defense_trust_bonus = 0
        if trust_level > 0 and friendship_multipliers and "friendship_defense" in friendship_multipliers:
            defense_mult = friendship_multipliers["friendship_defense"] / 100
            # Trust applies to the combined growth (species + IV), not just species
            defense_trust_bonus = math.floor((defense_growth + defense_iv_bonus) * (trust_level * defense_mult))
            
        # Step 5: Assemble
        defense_effective_base = static_defense + math.floor(defense_growth + defense_iv_bonus) + defense_trust_bonus
        
        # Apply rank multipliers
        calculated_attack = math.floor(attack_effective_base * rank_multiplier)
        calculated_defense = math.floor(defense_effective_base * rank_multiplier)
        
        # Work speed (not affected by level scaling in the same way)
        calculated_work_speed = 70  # Default work speed
        
        # Apply passive skill multipliers (effects are now stored in SkillInfo)
        if passive_skills:
            hp_multiplier = 1.0
            attack_multiplier = 1.0
            defense_multiplier = 1.0
            work_speed_multiplier = 1.0
            
            for skill in passive_skills:
                # Access effects directly from SkillInfo object
                effects = getattr(skill, 'effects', None)
                if not effects:
                    continue
                    
                for effect in effects:
                    effect_type = effect.get('type')
                    value = effect.get('value', 0) / 100  # Convert percentage to decimal
                    target = effect.get('target')
                    
                    # Only apply if target is ToSelf
                    if target == 'ToSelf':
                        if effect_type == 'MaxHP':
                            hp_multiplier += value
                        elif effect_type == 'Attack':
                            attack_multiplier += value
                        elif effect_type in ['Defense', 'Defence']:  # Handle both spellings
                            defense_multiplier += value
                        elif effect_type in ['WorkSpeed', 'CraftSpeed']:
                            work_speed_multiplier += value
            
            # Apply multipliers
            if hp_multiplier != 1.0:
                old_hp = calculated_hp
                calculated_hp = math.floor(calculated_hp * hp_multiplier)
            if attack_multiplier != 1.0:
                old_attack = calculated_attack
                calculated_attack = math.floor(calculated_attack * attack_multiplier)
            if defense_multiplier != 1.0:
                old_defense = calculated_defense
                calculated_defense = math.floor(calculated_defense * defense_multiplier)
            if work_speed_multiplier != 1.0:
                old_ws = calculated_work_speed
                calculated_work_speed = math.floor(calculated_work_speed * work_speed_multiplier)
        
        return {
            "attack": calculated_attack,
            "defense": calculated_defense,
            "hp": calculated_hp,
            "work_speed": calculated_work_speed
        }
    except Exception as e:
        logger.warning(f"Error calculating stats: {e}", exc_info=True)
        return {"attack": 0, "defense": 0, "hp": 0, "work_speed": 70}


def calculate_work_suitabilities(
    base_work_suitability: Dict[str, int],
    condensor_rank: Optional[int] = None,
    manual_upgrades: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """Calculate actual work suitability levels including bonuses
    
    The calculation is:
    Final Level = Base Level + Pal Condensor Bonus + Manual Upgrades
    
    - Base Level: From species JSON data
    - Pal Condensor Bonus: +1 to ALL work types if condensor_rank == 5 (4 star pal)
    - Manual Upgrades: Individual upgrades dict {work_type: bonus_amount}
    
    Args:
        base_work_suitability: Base work suitability levels from species data
        condensor_rank: The Pal Condensor rank value (5 = 4 star pal), or None
        manual_upgrades: Dict mapping work type to bonus amount, or None
        
    Returns:
        Dict mapping work type ID to calculated level (0-4)
    """
    if not base_work_suitability:
        return {}
    
    # Start with base levels
    calculated_suitabilities = base_work_suitability.copy()
    
    # Apply Pal Condensor bonus (4 star pal = rank 5)
    if condensor_rank == 5:
        for work_type in calculated_suitabilities:
            calculated_suitabilities[work_type] += 1
    
    # Apply manual upgrades
    if manual_upgrades:
        for work_type, bonus in manual_upgrades.items():
            if work_type in calculated_suitabilities:
                calculated_suitabilities[work_type] += bonus
            else:
                # If work type wasn't in base (level 0), set it to the bonus
                calculated_suitabilities[work_type] = bonus
    
    return calculated_suitabilities
