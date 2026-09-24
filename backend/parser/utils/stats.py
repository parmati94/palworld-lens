"""Stat calculation utilities for Palworld
Based on community research by u/blahable and datamined mechanics
"""
import math
import logging
from typing import Dict, Optional, List, Tuple, Any

from backend.common.logging_config import get_logger

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
        # strictly more than the threshold: a pal at exactly 13000 (rank 2's line) shows Trust 1 in game
        if friendship_points > threshold or (threshold == 0 and friendship_points >= 0):
            return level
    return 0


STAR_STEP = 0.05          # each condensing star: +5% to every stat
SOUL_STEP = 0.03          # each Pal Soul point: +3% to its stat
TALENT_STEP = 0.003       # each talent (IV) point: +0.3% of the level growth
HP_PER_LEVEL, ATTACK_PER_LEVEL = 0.5, 0.075
BASE_HP, BASE_ATTACK, BASE_DEFENSE = 500, 100, 50
DEFAULT_WORK_SPEED = 70   # every species' work speed at 0 stars (the craft scale is 100 for all 753 rows and unused here)
WORK_STAR_STEP = 0.10     # condensing: +10% work speed per star (4 stars = 98 on two live pals), vs +5% on the fighting stats
FOOD_STAT = {'WorkSpeed': 'work_speed', 'Attack': 'attack', 'Defense': 'defense'}   # a dish's percent buffs that are stats


def calculate_pal_stats(
    row: Optional[Dict],
    level: int,
    talent_hp: int,
    talent_melee: int,
    talent_shot: int,
    talent_defense: int,
    rank: int = 1,
    trust_level: int = 0,
    passive_skills: Optional[List] = None,
    soul_hp: int = 0,
    soul_attack: int = 0,
    soul_defense: int = 0,
    soul_work_speed: int = 0,
    food_effects: Optional[List[Dict]] = None,
) -> Dict:
    """A pal's stats the way the status screen shows them, with the breakdown behind the hover.

    `row` is the pal's own pak row (DataLoader.stat_row: hp / shot / melee / defense / craft scaling
    and the friendship values). Boss and lucky pals have their own row (Hp x1.2, a lower
    Friendship_HP), so there is no alpha multiplier here -- the row carries it.

    One shape for every stat, fitted 2026-09-24 against 1,894 saved pals (HP exact on all but a
    handful) and two live tooltips (Attack 1006 >> 1651 with trust +6; Defense 897 >> 1502 with
    trust +24 at rank 2):

      pre   = floor( base + k L (1 + 0.3 IV/100) (scale + f * trust_rank) )     k = 0.5 HP, 0.075 attack/defense
      shown = floor( floor( floor(pre * stars) * souls ) * passives )            stars 1 + 0.05/star, souls 1 + 0.03/point

    Trust is the friendship value added to the scale once per rank; the tooltip's "base" is the
    same without trust and "Bonus from Trust" the difference after the stars. Work speed starts at
    70 for every species and condensing gives it +10% per star (98 at four stars, confirmed on two
    pals), then souls and passives. A dish the pal ate (`food_effects`, [{type, value}] from the
    loadout food table) multiplies last: Frosty's 98 >> 127 with Pizza's +30%.
    """
    if not row or not row.get('hp'):
        return {"attack": 0, "defense": 0, "hp": 0, "work_speed": DEFAULT_WORK_SPEED, "breakdown": {}}
    stars = max(0, min(MAX_CONDENSE_STARS, int(rank or 1) - 1))
    star_mult = 1 + STAR_STEP * stars
    trust = max(0, int(trust_level or 0))
    L = int(level or 1)

    passives = {'hp': 0.0, 'attack': 0.0, 'defense': 0.0, 'work_speed': 0.0}
    for skill in passive_skills or []:
        effects = getattr(skill, 'effects', None) or (skill.get('effects') if isinstance(skill, dict) else None) or []
        for e in effects:
            if str(e.get('target') or 'ToSelf') != 'ToSelf':
                continue
            t, v = str(e.get('type') or ''), float(e.get('value') or 0)
            if t == 'MaxHP':
                passives['hp'] += v
            elif t in ('Attack', 'ShotAttack'):
                passives['attack'] += v
            elif t in ('Defense', 'Defence'):
                passives['defense'] += v
            elif t in ('CraftSpeed', 'WorkSpeed'):
                passives['work_speed'] += v

    food = {'hp': 0.0, 'attack': 0.0, 'defense': 0.0, 'work_speed': 0.0}
    for e in food_effects or []:
        name = FOOD_STAT.get(str(e.get('type') or ''))
        if name:
            food[name] += float(e.get('value') or 0)

    def finish(name: str, with_trust: int, without: int, souls: int) -> Dict[str, int]:
        soul_pct, pass_pct, food_pct = SOUL_STEP * souls * 100, passives[name], food[name]
        total = math.floor(math.floor(math.floor(with_trust * (1 + soul_pct / 100)) * (1 + pass_pct / 100)) * (1 + food_pct / 100))
        return {'base': int(without), 'trust': int(with_trust - without), 'souls_pct': int(round(soul_pct)),
                'passives_pct': int(round(pass_pct)), 'food_pct': int(round(food_pct)), 'total': int(total)}

    def stat(name: str, base: float, k: float, talent: int, scale: float, f: float, souls: int) -> Dict[str, int]:
        iv = 1 + TALENT_STEP * talent
        with_trust = math.floor(math.floor(base + k * L * iv * (scale + f * trust)) * star_mult)
        without = math.floor(math.floor(base + k * L * iv * scale) * star_mult)
        return finish(name, with_trust, without, souls)

    hp = stat('hp', BASE_HP + 5 * L, HP_PER_LEVEL, talent_hp, row['hp'], row.get('f_hp', 0), soul_hp)
    atk = stat('attack', BASE_ATTACK, ATTACK_PER_LEVEL, max(talent_melee, talent_shot), row.get('shot', 0), row.get('f_shot', 0), soul_attack)
    dfn = stat('defense', BASE_DEFENSE, ATTACK_PER_LEVEL, talent_defense, row.get('defense', 0), row.get('f_defense', 0), soul_defense)
    work_base = math.floor(DEFAULT_WORK_SPEED * (1 + WORK_STAR_STEP * stars))
    work = finish('work_speed', work_base, work_base, soul_work_speed)
    return {"attack": atk['total'], "defense": dfn['total'], "hp": hp['total'], "work_speed": work['total'],
            "breakdown": {'hp': hp, 'attack': atk, 'defense': dfn, 'work_speed': work}}


WORK_RANK_EFFECT = 'WorkSuitabilityAddRank_'
MAX_CONDENSE_STARS = 4
MAX_WORK_LEVEL = 10       # the game shows at most Lv 10 per job (a 4-star Frostallion is Cooling 7 + 4 = 10, not 11)


def passive_work_bonuses(passive_skills: Optional[list]) -> Dict[str, int]:
    """{work type: +levels} from a pal's own passives (Farmhand, Ranch Master, ...).

    passive_skills.json carries each passive's effects; the work ones are typed
    `WorkSuitabilityAddRank_<WorkType>` with the pal itself as target. Effects
    aimed at other pals (a base-wide bonus) are not the pal's own level.
    """
    out: Dict[str, int] = {}
    for skill in passive_skills or []:
        effects = getattr(skill, 'effects', None) or (skill.get('effects') if isinstance(skill, dict) else None) or []
        for e in effects:
            t = str(e.get('type') or '')
            if not t.startswith(WORK_RANK_EFFECT) or str(e.get('target') or 'ToSelf') != 'ToSelf':
                continue
            work_type = t[len(WORK_RANK_EFFECT):]
            out[work_type] = out.get(work_type, 0) + int(e.get('value') or 0)
    return out


def condensing_work_bonus(base_work_suitability: Dict[str, int], stars: int, best: Optional[str] = None) -> Dict[str, int]:
    """{work type: +levels} from condensing stars (1.0 rule).

    Star 1 raises the species' designated best job (DT_PalMonsterParameter
    BestWorkSuitability, shipped as pals.json best_work_suitability -- a
    designer pick, often Ranch even when another job is higher). Star 2 and 3
    raise the next jobs, highest species level first, ties in the game's job
    order. A pal with fewer jobs than stars cycles back to the best: a
    Ranch-only Mozzarina puts three stars into Ranch, a two-job Chikipi ends
    Ranch 3 / Gathering 2 (both confirmed in game). Star 4 raises every job.

    Without a best (species missing from pal_parameters.json) the best is the
    highest-level job in game order.
    """
    jobs = [t for t, lv in base_work_suitability.items() if lv > 0]
    if not jobs or stars <= 0:
        return {}
    order = {t: i for i, t in enumerate(base_work_suitability)}
    jobs.sort(key=lambda t: (-base_work_suitability[t], order[t]))
    if best in jobs:
        jobs.remove(best)
        jobs.insert(0, best)
    bonus = {t: 0 for t in jobs}
    for star in range(min(stars, MAX_CONDENSE_STARS - 1)):
        bonus[jobs[star % len(jobs)]] += 1
    if stars >= MAX_CONDENSE_STARS:
        for t in jobs:
            bonus[t] += 1
    return {t: b for t, b in bonus.items() if b}


def calculate_work_suitabilities(
    base_work_suitability: Dict[str, int],
    condensor_rank: Optional[int] = None,
    manual_upgrades: Optional[Dict[str, int]] = None,
    passive_skills: Optional[list] = None,
    best_work_suitability: Optional[str] = None,
) -> Dict[str, int]:
    """Actual work suitability levels: species base + condensing + books + passives.

    Condensing (rank is the save value 1-5, so stars = rank - 1) follows the
    1.0 rule in condensing_work_bonus: one job per star for the first three,
    every job at four. Books (GotWorkSuitabilityAddRankList) add on top and
    can grant a type the species lacks. Work passives such as Farmhand add
    on top too, but only to a type the species already has: a Farmhand
    Direhowl gets no Ranch (confirmed in game). Before 1.0 the condenser
    gave +1 to everything only at 4 stars. Nothing goes past MAX_WORK_LEVEL:
    a 4-star Frostallion (Cooling 7, its only job) shows 10 in game, not 11.

    Args:
        base_work_suitability: species levels from pals.json
        condensor_rank: save Rank value (1 = no stars ... 5 = 4 stars), or None
        manual_upgrades: {work type: +levels} from books, or None
        passive_skills: the pal's SkillInfo passives (effects read), or None
        best_work_suitability: species' designated best job, or None

    Returns:
        {work type id: level}
    """
    if not base_work_suitability:
        return {}

    calculated_suitabilities = base_work_suitability.copy()

    stars = max(0, min(MAX_CONDENSE_STARS, int(condensor_rank or 1) - 1))
    for work_type, bonus in condensing_work_bonus(base_work_suitability, stars, best_work_suitability).items():
        calculated_suitabilities[work_type] += bonus

    for work_type, bonus in (manual_upgrades or {}).items():
        calculated_suitabilities[work_type] = calculated_suitabilities.get(work_type, 0) + bonus
    for work_type, bonus in passive_work_bonuses(passive_skills).items():
        if base_work_suitability.get(work_type, 0) > 0:
            calculated_suitabilities[work_type] += bonus

    return {t: min(lv, MAX_WORK_LEVEL) for t, lv in calculated_suitabilities.items()}
