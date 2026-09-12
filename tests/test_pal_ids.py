"""character_id -> species resolution (backend/common/pal_ids.py)."""
from backend.common.pal_ids import SpeciesIndex, is_boss_id, strip_boss

IDS = ['CatBat', 'Ninja', 'BOSS_Ninja', 'LazyCatfish', 'HerculesBeetle', 'FlowerDoll', 'FlowerDoll_Fire']


def test_boss_helpers():
    assert is_boss_id('BOSS_CatBat') and is_boss_id('Boss_CatBat') and not is_boss_id('CatBat')
    assert strip_boss('BOSS_CatBat') == 'CatBat'
    assert strip_boss('CatBat') == 'CatBat'
    assert strip_boss('') == ''


def test_exact_and_prefixed_entries_win():
    idx = SpeciesIndex(IDS)
    assert idx.resolve('CatBat') == 'CatBat'
    # Humanoid bosses keep their own prefixed entry
    assert idx.resolve('BOSS_Ninja') == 'BOSS_Ninja'
    # Alpha pals lose the prefix
    assert idx.resolve('BOSS_CatBat') == 'CatBat'


def test_case_insensitive():
    idx = SpeciesIndex(IDS)
    assert idx.resolve('Boss_LazyCatFish') == 'LazyCatfish'
    assert idx.resolve('lazycatfish') == 'LazyCatfish'


def test_variant_trimming_prefers_exact_variant():
    idx = SpeciesIndex(IDS)
    assert idx.resolve('FlowerDoll_Fire') == 'FlowerDoll_Fire'
    assert idx.resolve('BOSS_HerculesBeetle_Ground') == 'HerculesBeetle'
    assert idx.resolve('BOSS_HerculesBeetle_Ground', trim_variants=False) is None


def test_unknown():
    idx = SpeciesIndex(IDS)
    assert idx.resolve('Nope') is None
    assert idx.resolve('') is None
    assert idx.resolve_or_raw('BOSS_Nope') == 'Nope'
