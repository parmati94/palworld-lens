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
DEFAULT_WORK_SPEED = 70


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
) -> Dict:
    """A pal's stats the way the status screen shows them, with the breakdown behind the hover.

    `row` is the pal's own pak row (DataLoader.stat_row: hp / shot / melee / defense scaling and the
    friendship values). Boss and lucky pals have their own row (Hp x1.2, a lower Friendship_HP), so
    there is no alpha multiplier here -- the row carries it.

    Fitted 2026-09-24 against 1,894 saved pals (HP, exact to the point) and a live status screen
    (attack 1006 >> 1651 = (1006 + 6 trust) x 1.36 souls x 1.20 passives):

      HP      = floor( floor(500 + 5L + 0.5 L (1 + 0.3 IV/100) (hp_scale + f_hp * trust)) * stars )
      attack  = floor( floor(100 + 0.075 L (1 + 0.3 IV/100) shot) * stars ) + trust_bonus
      defense = floor( floor( 50 + 0.075 L (1 + 0.3 IV/100) def ) * stars ) + trust_bonus
      then    x (1 + 0.03 souls) x (1 + passives%)   [souls and passives multiply, floored at the end]

    Trust raises HP as if the species' scale were f_hp higher per rank (0.5 L (1+IV) f rank, exact on
    the save). For attack the screen adds 0.1 L f rank after the stars (+6 for f 1.0 at L60); defense
    is assumed to follow attack until a defense tooltip says otherwise.
    """
    if not row or not row.get('hp'):
        return {"attack": 0, "defense": 0, "hp": 0, "work_speed": DEFAULT_WORK_SPEED, "breakdown": {}}
    stars = max(0, min(MAX_CONDENSE_STARS, int(rank or 1) - 1))
    star_mult = 1 + STAR_STEP * stars
    trust = max(0, int(trust_level or 0))
    iv_hp, iv_atk, iv_def = 1 + TALENT_STEP * talent_hp, 1 + TALENT_STEP * max(talent_melee, talent_shot), 1 + TALENT_STEP * talent_defense
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

    def finish(stat: str, pre: float, trust_bonus: float, souls: int) -> Dict[str, int]:
        soul_pct, pass_pct = SOUL_STEP * souls * 100, passives[stat]
        total = math.floor((pre + trust_bonus) * (1 + soul_pct / 100) * (1 + pass_pct / 100))
        return {'base': int(pre), 'trust': int(round(trust_bonus)), 'souls_pct': int(round(soul_pct)),
                'passives_pct': int(round(pass_pct)), 'total': int(total)}

    # HP: trust rides inside the growth (extra scale per rank), then stars, then souls / passives
    hp_pre = math.floor(math.floor(BASE_HP + 5 * L + HP_PER_LEVEL * L * iv_hp * (row['hp'] + row.get('f_hp', 0) * trust)) * star_mult)
    hp_base_only = math.floor(math.floor(BASE_HP + 5 * L + HP_PER_LEVEL * L * iv_hp * row['hp']) * star_mult)
    hp = finish('hp', hp_base_only, hp_pre - hp_base_only, soul_hp)
    # attack / defense: stars on the base, the trust bonus added after (0.1 L f rank), then the multipliers
    atk_base = math.floor(math.floor(BASE_ATTACK + ATTACK_PER_LEVEL * L * iv_atk * row.get('shot', 0)) * star_mult)
    atk = finish('attack', atk_base, math.floor(0.1 * L * row.get('f_shot', 0) * trust), soul_attack)
    def_base = math.floor(math.floor(BASE_DEFENSE + ATTACK_PER_LEVEL * L * iv_def * row.get('defense', 0)) * star_mult)
    dfn = finish('defense', def_base, math.floor(0.1 * L * row.get('f_defense', 0) * trust), soul_defense)
    work = finish('work_speed', DEFAULT_WORK_SPEED, 0, soul_work_speed)
    return {"attack": atk['total'], "defense": dfn['total'], "hp": hp['total'], "work_speed": work['total'],
            "breakdown": {'hp': hp, 'attack': atk, 'defense': dfn}}


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
