"""character_id -> icon candidates (backend/common/pal_icons.py)."""
from backend.common import pal_icons


def test_plain_and_boss():
    assert pal_icons.icon_candidates('Anubis') == ['anubis']
    assert pal_icons.icon_candidates('BOSS_Anubis') == ['anubis']
    assert pal_icons.image_id('BOSS_BlueDragon') == 'bluedragon'


def test_variants_fall_back_token_by_token():
    assert pal_icons.icon_candidates('PREDATOR_Anubis_Oilrig') == ['predator_anubis_oilrig', 'predator_anubis', 'anubis_oilrig', 'anubis']
    # Gym bosses ship their own icon, so the prefixed stem comes first
    assert pal_icons.icon_candidates('GYM_ThunderDragonMan')[0] == 'gym_thunderdragonman'
    assert 'thunderdragonman' in pal_icons.icon_candidates('GYM_ThunderDragonMan')


def test_quest_variants_use_base_pal():
    assert pal_icons.icon_candidates('Quest_Farmer03_PinkCat') == ['pinkcat']


def test_empty():
    assert pal_icons.icon_candidates('') == ['unknown']
