"""Stat formulas (backend/parser/utils/stats.py) pinned against known values."""
from types import SimpleNamespace

from backend.parser.utils.stats import calculate_pal_stats, calculate_trust_level, calculate_work_suitabilities, passive_work_bonuses

ALPACA = {'hp': 90, 'attack': 75, 'defense': 90}


def test_level_1_no_talents():
    s = calculate_pal_stats(ALPACA, level=1, talent_hp=0, talent_melee=0, talent_shot=0, talent_defense=0)
    assert s == {'hp': 550, 'attack': 105, 'defense': 56, 'work_speed': 70}


def test_talents_rank_and_alpha_scale_up():
    base = calculate_pal_stats(ALPACA, 50, 0, 0, 0, 0)
    ivs = calculate_pal_stats(ALPACA, 50, 100, 100, 100, 100)
    rank = calculate_pal_stats(ALPACA, 50, 0, 0, 0, 0, rank=5)
    alpha = calculate_pal_stats(ALPACA, 50, 0, 0, 0, 0, is_alpha=True)
    assert ivs['hp'] > base['hp'] and ivs['attack'] > base['attack'] and ivs['defense'] > base['defense']
    assert rank['hp'] == int(base['hp'] * 1.2) or abs(rank['hp'] - base['hp'] * 1.2) <= 1
    assert alpha['hp'] > base['hp'] and alpha['attack'] == base['attack']


def test_unknown_species_returns_zeros():
    assert calculate_pal_stats(None, 10, 0, 0, 0, 0) == {'attack': 0, 'defense': 0, 'hp': 0, 'work_speed': 70}


def test_passive_and_soul_multipliers():
    class Skill:
        effects = [{'type': 'Attack', 'value': 20, 'target': 'ToSelf'}]
    base = calculate_pal_stats(ALPACA, 30, 0, 0, 0, 0)
    boosted = calculate_pal_stats(ALPACA, 30, 0, 0, 0, 0, passive_skills=[Skill()], soul_hp=10)
    assert boosted['attack'] == int(base['attack'] * 1.2)
    assert boosted['hp'] == int(base['hp'] * 1.3)


def test_trust_level():
    thresholds = [(0, 0), (100, 1), (500, 2)]
    assert calculate_trust_level(None, thresholds) == 0
    assert calculate_trust_level(99, thresholds) == 0
    assert calculate_trust_level(100, thresholds) == 1
    assert calculate_trust_level(10_000, thresholds) == 2


def test_work_suitability_bonuses():
    base = {'EmitFlame': 2, 'Mining': 0}
    assert calculate_work_suitabilities(base) == base
    assert calculate_work_suitabilities(base, condensor_rank=1) == base
    # 1.0: every star adds one to the types the species has (rank 5 = 4 stars)
    assert calculate_work_suitabilities(base, condensor_rank=2) == {'EmitFlame': 3, 'Mining': 0}
    assert calculate_work_suitabilities(base, condensor_rank=5) == {'EmitFlame': 6, 'Mining': 0}
    assert calculate_work_suitabilities(base, condensor_rank=9) == {'EmitFlame': 6, 'Mining': 0}   # clamped
    assert calculate_work_suitabilities(base, manual_upgrades={'Mining': 1, 'EmitFlame': 1}) == {'EmitFlame': 3, 'Mining': 1}


def test_work_suitability_counts_the_pals_own_work_passives():
    farmhand = SimpleNamespace(effects=[{'type': 'WorkSuitabilityAddRank_MonsterFarm', 'value': 1.0, 'target': 'ToSelf'}])
    base_wide = SimpleNamespace(effects=[{'type': 'WorkSuitabilityAddRank_MonsterFarm', 'value': 1.0, 'target': 'ToBaseCampPal'}])
    stat_only = SimpleNamespace(effects=[{'type': 'CraftSpeed', 'value': 50.0, 'target': 'ToSelf'}])
    # Paul's 3-star Mozzarina: Ranch 2 + 3 stars + Farmhand = 6
    assert calculate_work_suitabilities({'MonsterFarm': 2, 'Mining': 0}, 4, None, [farmhand, stat_only]) == {'MonsterFarm': 6, 'Mining': 0}
    assert calculate_work_suitabilities({'MonsterFarm': 2}, 1, None, [base_wide]) == {'MonsterFarm': 2}
    # a work passive on a species without that type grants it, like a book does
    assert calculate_work_suitabilities({'Mining': 1}, 1, {'Mining': 1}, [farmhand]) == {'Mining': 2, 'MonsterFarm': 1}
    assert passive_work_bonuses([farmhand, {'effects': [{'type': 'WorkSuitabilityAddRank_Mining', 'value': 2}]}]) == {'MonsterFarm': 1, 'Mining': 2}
