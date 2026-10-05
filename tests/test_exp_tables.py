"""backend/common/exp_tables.py -- the capture bonus chain and the level ladder."""
from backend.common.exp_tables import (bonus_exp_at, build_exp_tables, catches_to_next_level, character_max_level,
                                       exp_to_next_level,
                                       level_progress)

BONUS = {"0": {"BonusExp": 3}, "1": {"BonusExp": 22}, "2": {"BonusExp": 24}, "3": {"BonusExp": 27}}
LEVELS = {"1": {"TotalEXP": 0, "NextEXP": 0}, "2": {"TotalEXP": 50, "NextEXP": 50},
          "3": {"TotalEXP": 200, "NextEXP": 150}, "4": {"TotalEXP": 400, "NextEXP": 200}}
TABLE = build_exp_tables(BONUS, LEVELS)


def test_build_orders_the_chain_numerically_and_keeps_the_ladder():
    assert TABLE["capture_bonus"] == [3, 22, 24, 27]
    assert TABLE["levels"]["3"] == {"total": 200, "next": 150}
    # string keys sort numerically, not lexically ("10" after "9")
    rows = {str(i): {"BonusExp": i} for i in range(12)}
    assert build_exp_tables(rows, LEVELS)["capture_bonus"] == list(range(12))


def test_next_bonus_catch_pays_the_row_at_the_running_index():
    assert bonus_exp_at(TABLE, 0) == 3
    assert bonus_exp_at(TABLE, 1) == 22
    assert bonus_exp_at(TABLE, 99) == 27       # past the end: the last row keeps paying
    assert bonus_exp_at({}, 5) == 0


def test_exp_to_next_level_reads_the_cumulative_column():
    assert exp_to_next_level(TABLE, 2, 120) == 80      # level 3 needs 200 total
    assert exp_to_next_level(TABLE, 2, 250) == 0       # already past it (the save updates level first)
    assert exp_to_next_level(TABLE, 4, 999) is None    # no row 5: the cap


def test_level_progress_is_the_status_screen_bar():
    assert level_progress(TABLE, 2, 120) == {"into": 70, "span": 150, "to_next": 80}
    assert level_progress(TABLE, 1, 0) == {"into": 0, "span": 50, "to_next": 50}
    assert level_progress(TABLE, 4, 500) is None
    assert level_progress({}, 2, 120) is None


def test_catches_to_next_level_walks_the_chain_from_the_index():
    # from index 1: 22 + 24 = 46 < 50, + 27 = 73 -> three catches
    assert catches_to_next_level(TABLE, 1, 50) == 3
    assert catches_to_next_level(TABLE, 1, 50, rate=2.0) == 2      # 44, then 92
    assert catches_to_next_level(TABLE, 1, 0) == 0
    assert catches_to_next_level(TABLE, 1, None) is None
    assert catches_to_next_level({}, 1, 50) is None


def test_the_cap_comes_from_max_level_not_the_end_of_the_ladder():
    # the pak's ladder runs past the cap (100 rows, cap 80 on 1.0)
    capped = build_exp_tables(BONUS, LEVELS, max_level=3)
    assert capped["max_level"] == 3
    assert level_progress(capped, 2, 120) == {"into": 70, "span": 150, "to_next": 80}
    assert level_progress(capped, 3, 300) is None
    assert exp_to_next_level(capped, 3, 300) is None
    assert "max_level" not in TABLE


def test_character_max_level_reads_the_settings_default_object():
    exports = [{"Type": "BlueprintGeneratedClass", "Properties": {}},
               {"Type": "BP_PalGameSetting_C", "Properties": {"CharacterMaxLevel": 80, "GuildCharacterMaxLevel": 80}}]
    assert character_max_level(exports) == 80
    assert character_max_level([]) is None
