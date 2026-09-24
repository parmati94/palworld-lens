"""Stat formulas (backend/parser/utils/stats.py) pinned against known values."""
from types import SimpleNamespace

from backend.parser.utils.stats import calculate_pal_stats, calculate_trust_level, calculate_work_suitabilities, condensing_work_bonus, passive_work_bonuses

ALPACA = {'hp': 90, 'shot': 75, 'melee': 70, 'defense': 90, 'craft': 100, 'f_hp': 4.5, 'f_shot': 2.0, 'f_defense': 2.0, 'f_craft': 0.0}
# BOSS_IceHorse's own pak row: Hp 168 (the base species' 140 x 1.2), Friendship_HP 0.6 (the base's 2.0 is not used)
FROSTALLION_BOSS = {'hp': 168, 'shot': 140, 'melee': 100, 'defense': 120, 'craft': 100, 'f_hp': 0.6, 'f_shot': 1.0, 'f_defense': 1.7, 'f_craft': 0.0}


class _Skill:
    def __init__(self, effects):
        self.effects = effects


LEGEND = _Skill([{'type': 'ShotAttack', 'value': 20.0, 'target': 'ToSelf'}, {'type': 'Defense', 'value': 20.0, 'target': 'ToSelf'},
                 {'type': 'MoveSpeed', 'value': 20.0, 'target': 'ToSelf'}])


def test_level_1_no_talents():
    s = calculate_pal_stats(ALPACA, level=1, talent_hp=0, talent_melee=0, talent_shot=0, talent_defense=0)
    assert (s['hp'], s['attack'], s['defense'], s['work_speed']) == (550, 105, 56, 70)


def test_frosty_wosty_status_screen():
    # Level 60, 4 stars, souls 8/12/12, talents HP 63 / shot 58 / defense 98, Legend. Two live screens:
    # at trust 1: Attack 1006 >> 1651 (trust +6, souls +36%, passives +20%), Defense 1483, HP 10137
    # at trust 2: Defense tooltip 897 >> 1502 (trust +24), HP 10170 (= the saved Hp)
    kw = dict(rank=5, passive_skills=[LEGEND], soul_hp=8, soul_attack=12, soul_defense=12)
    t1 = calculate_pal_stats(FROSTALLION_BOSS, 60, 63, 0, 58, 98, trust_level=1, **kw)
    assert t1['breakdown']['attack'] == {'base': 1006, 'trust': 6, 'souls_pct': 36, 'passives_pct': 20, 'food_pct': 0, 'total': 1651}
    assert (t1['attack'], t1['defense'], t1['hp']) == (1651, 1483, 10137)
    t2 = calculate_pal_stats(FROSTALLION_BOSS, 60, 63, 0, 58, 98, trust_level=2, **kw)
    assert t2['breakdown']['defense'] == {'base': 897, 'trust': 24, 'souls_pct': 36, 'passives_pct': 20, 'food_pct': 0, 'total': 1502}
    assert t2['hp'] == 10170
    assert t2['work_speed'] == 98         # 70 x 1.4 at four stars (Eidrolon Ignis, also 4 stars, reads 98 too)
    fed = calculate_pal_stats(FROSTALLION_BOSS, 60, 63, 0, 58, 98, trust_level=2, food_effects=[{'type': 'WorkSpeed', 'value': 30.0}, {'type': 'HungerResist', 'value': 25.0}], **kw)
    assert fed['work_speed'] == 127 and fed['breakdown']['work_speed'] == {'base': 98, 'trust': 0, 'souls_pct': 0, 'passives_pct': 0, 'food_pct': 30, 'total': 127}
    assert fed['attack'] == t2['attack']  # pizza does not touch attack


def test_trust_raises_hp_as_extra_scale_per_rank():
    # NegativeOctopus L26 iv39 f_hp 6.0 trust 1 on the live save: +87 HP over the untrusted base
    row = {'hp': 60, 'shot': 70, 'melee': 70, 'defense': 70, 'craft': 100, 'f_hp': 6.0, 'f_shot': 3.0, 'f_defense': 3.0, 'f_craft': 0.0}
    plain = calculate_pal_stats(row, 26, 39, 0, 0, 0)['hp']
    trusted = calculate_pal_stats(row, 26, 39, 0, 0, 0, trust_level=1)['hp']
    assert trusted - plain == 87
    assert calculate_pal_stats(row, 26, 39, 0, 0, 0, trust_level=7)['hp'] - plain == 610   # 7 ranks


def test_talents_stars_and_the_row_scale_up():
    base = calculate_pal_stats(ALPACA, 50, 0, 0, 0, 0)
    ivs = calculate_pal_stats(ALPACA, 50, 100, 100, 100, 100)
    stars = calculate_pal_stats(ALPACA, 50, 0, 0, 0, 0, rank=5)
    assert ivs['hp'] > base['hp'] and ivs['attack'] > base['attack'] and ivs['defense'] > base['defense']
    assert abs(stars['hp'] - base['hp'] * 1.2) <= 1 and abs(stars['attack'] - base['attack'] * 1.2) <= 1


def test_unknown_row_returns_zeros():
    assert calculate_pal_stats(None, 10, 0, 0, 0, 0)['hp'] == 0 and calculate_pal_stats(None, 10, 0, 0, 0, 0)['work_speed'] == 70
    assert calculate_pal_stats({}, 10, 0, 0, 0, 0)['attack'] == 0


def test_passive_and_soul_multipliers():
    base = calculate_pal_stats(ALPACA, 30, 0, 0, 0, 0)
    boosted = calculate_pal_stats(ALPACA, 30, 0, 0, 0, 0, passive_skills=[_Skill([{'type': 'Attack', 'value': 20, 'target': 'ToSelf'}])], soul_hp=10)
    assert boosted['attack'] == int(base['attack'] * 1.2)
    assert boosted['hp'] == int(base['hp'] * 1.3)
    assert boosted['breakdown']['attack']['passives_pct'] == 20 and boosted['breakdown']['hp']['souls_pct'] == 30
    assert calculate_pal_stats(ALPACA, 30, 0, 0, 0, 0, rank=3)['work_speed'] == 84       # two stars: 70 x 1.2


def test_trust_level():
    thresholds = [(0, 0), (100, 1), (500, 2)]
    assert calculate_trust_level(None, thresholds) == 0
    assert calculate_trust_level(100, thresholds) == 0        # exactly on the line is not there yet (Trust 1 at 13000 in game)
    assert calculate_trust_level(101, thresholds) == 1
    assert calculate_trust_level(10_000, thresholds) == 2


def test_work_suitability_bonuses():
    base = {'EmitFlame': 2, 'Mining': 0}
    assert calculate_work_suitabilities(base) == base
    assert calculate_work_suitabilities(base, condensor_rank=1) == base
    assert calculate_work_suitabilities(base, manual_upgrades={'Mining': 1, 'EmitFlame': 1}) == {'EmitFlame': 3, 'Mining': 1}


def test_work_level_never_passes_ten():
    # 4-star Frostallion: Cooling 7 is its only job, so every star lands on it (+4); the game shows 10
    assert calculate_work_suitabilities({'Cool': 7}, condensor_rank=5, best_work_suitability='Cool') == {'Cool': 10}
    assert calculate_work_suitabilities({'Cool': 7}, condensor_rank=4, best_work_suitability='Cool') == {'Cool': 10}
    assert calculate_work_suitabilities({'Cool': 7}, condensor_rank=3, best_work_suitability='Cool') == {'Cool': 9}
    assert calculate_work_suitabilities({'Mining': 8}, manual_upgrades={'Mining': 3}) == {'Mining': 10}


def test_condensing_best_job_first_then_by_level_then_all_at_four():
    # Wumpo: Handiwork 3, Lumbering 5, Cooling 5, Transporting 6; designated best Transporting
    base = {'Handcraft': 3, 'Deforest': 5, 'Cool': 5, 'Transport': 6}
    assert condensing_work_bonus(base, 0, 'Transport') == {}
    assert condensing_work_bonus(base, 1, 'Transport') == {'Transport': 1}
    assert condensing_work_bonus(base, 2, 'Transport') == {'Transport': 1, 'Deforest': 1}        # 5/5 tie -> game order
    assert condensing_work_bonus(base, 3, 'Transport') == {'Transport': 1, 'Deforest': 1, 'Cool': 1}
    assert condensing_work_bonus(base, 4, 'Transport') == {'Transport': 2, 'Deforest': 2, 'Cool': 2, 'Handcraft': 1}
    # the designated best need not be the highest job: Serpent (Watering 3, Ranch 2) starts with Ranch
    assert condensing_work_bonus({'Watering': 3, 'MonsterFarm': 2}, 1, 'MonsterFarm') == {'MonsterFarm': 1}
    # no designated best: highest level, game order
    assert condensing_work_bonus({'Watering': 3, 'MonsterFarm': 2}, 1) == {'Watering': 1}
    assert condensing_work_bonus({'Collection': 1, 'MonsterFarm': 1}, 1, 'Nope') == {'Collection': 1}


def test_condensing_cycles_when_a_pal_has_fewer_jobs_than_stars():
    # Paul's 3-star Mozzarina (Ranch only): 2 -> 5; 3-star Chikipi (Gathering 1, Ranch 1, best Ranch): Ranch 3 / Gathering 2
    assert calculate_work_suitabilities({'MonsterFarm': 2, 'Mining': 0}, 4, best_work_suitability='MonsterFarm') == {'MonsterFarm': 5, 'Mining': 0}
    assert calculate_work_suitabilities({'Collection': 1, 'MonsterFarm': 1}, 4, best_work_suitability='MonsterFarm') == {'Collection': 2, 'MonsterFarm': 3}
    assert calculate_work_suitabilities({'Collection': 1, 'MonsterFarm': 1}, 5, best_work_suitability='MonsterFarm') == {'Collection': 3, 'MonsterFarm': 4}
    assert calculate_work_suitabilities({'MonsterFarm': 2}, 9, best_work_suitability='MonsterFarm') == {'MonsterFarm': 6}   # clamped to 4 stars


def test_work_suitability_counts_the_pals_own_work_passives():
    farmhand = SimpleNamespace(effects=[{'type': 'WorkSuitabilityAddRank_MonsterFarm', 'value': 1.0, 'target': 'ToSelf'}])
    base_wide = SimpleNamespace(effects=[{'type': 'WorkSuitabilityAddRank_MonsterFarm', 'value': 1.0, 'target': 'ToBaseCampPal'}])
    stat_only = SimpleNamespace(effects=[{'type': 'CraftSpeed', 'value': 50.0, 'target': 'ToSelf'}])
    # Paul's 3-star Mozzarina: Ranch 2 + 3 stars (all into its only job) + Farmhand = 6
    assert calculate_work_suitabilities({'MonsterFarm': 2, 'Mining': 0}, 4, None, [farmhand, stat_only]) == {'MonsterFarm': 6, 'Mining': 0}
    assert calculate_work_suitabilities({'MonsterFarm': 2}, 1, None, [base_wide]) == {'MonsterFarm': 2}
    # a work passive on a species without that type does nothing (a book still grants one)
    assert calculate_work_suitabilities({'Mining': 1, 'MonsterFarm': 0}, 1, {'Mining': 1}, [farmhand]) == {'Mining': 2, 'MonsterFarm': 0}
    assert calculate_work_suitabilities({'Mining': 1}, 1, {'Handcraft': 1}, [farmhand]) == {'Mining': 1, 'Handcraft': 1}
    assert passive_work_bonuses([farmhand, {'effects': [{'type': 'WorkSuitabilityAddRank_Mining', 'value': 2}]}]) == {'MonsterFarm': 1, 'Mining': 2}
