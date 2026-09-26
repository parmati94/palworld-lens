"""The item popup's payload (backend/common/item_detail.py) against the shipped tables."""
import pytest

from backend.common.item_detail import category_label, clean_description, describe_item
from backend.parser.loaders.data_loader import DataLoader


@pytest.fixture(scope='module')
def data():
    return DataLoader()


def test_plain_material_has_a_description(data):
    info = describe_item('AIcore', data)
    assert info['name'] == 'AI Core'
    assert info['description'].startswith('A core component')
    assert info['category'] == 'Material'
    assert info['rarity_name'] == 'Common'
    assert info['weight'] == 10.0 and info['max_stack'] == 9999
    assert info['gear'] == {} and info['passives'] == [] and info['food'] is None


def test_gear_carries_stats_and_named_passives(data):
    info = describe_item('AncientArmor', data)
    assert info['category'] == 'Armor · Body'
    assert info['gear'] == {'defense': 800, 'hp': 2400}
    assert [p['name'] for p in info['passives']] == ['Cold Resistance Lv. 2', 'Heat Resistance Lv. 2']
    assert all(p['description'] is None for p in info['passives'])   # raw effect ids are not shown
    pendant = describe_item('Accessory_AT_1', data)
    assert pendant['passives'][0]['description'] == 'Attack +15.0%'


def test_food_and_schematic(data):
    assert describe_item('Pizza', data)['food'] == '+30% work speed · +25% slower hunger'
    bp = describe_item('Blueprint_Accessory_AT_1_2', data)
    assert bp['category'] == 'Schematic'
    assert bp['schematic']['product_name'] == 'Attack Pendant'


def test_save_casing_and_unknown(data):
    assert describe_item('pizza', data)['food'] == describe_item('Pizza', data)['food']
    assert describe_item('NoSuchItem', data) is None


def test_crafted_at_uses_the_workbench_name(data):
    assert describe_item('AIcore', data)['description'].endswith('Can be crafted at Advanced Workshop.')
    assert describe_item('Cement', data)['description'].endswith('Can be produced in a High-Quality Workbench.')
    assert clean_description('Made of stuff. Can be crafted at Nowhere Special 09.', {}) == 'Made of stuff. Can be crafted at Nowhere Special 09.'
    assert clean_description('Raises COMMON_STATUS_RANGE_Attack by 20%.', {}) == 'Raises Attack by 20%.'
    # every crafted-at tail in the shipped text resolves to a building name
    for k in data.items:
        d = describe_item(k, data)['description'] or ''
        assert not any(w in d for w in ('Factory Hard', 'WeaponFactory', 'Dirty 0')), (k, d)


def test_category_label():
    assert category_label({'type_a': 'Weapon', 'type_b': 'WeaponBow'}) == 'Weapon · Bow'
    assert category_label({'type_a': 'Armor', 'type_b': 'Shield'}) == 'Armor · Shield'
    assert category_label({'type_a': 'Consume', 'type_b': 'ConsumeOther'}) == 'Consumable'
    assert category_label({'type_a': 'None', 'type_b': ''}) is None


def test_every_slot_item_describes(data):
    """Nearly every item row has a description; the blanks are cosmetic Head/Hair rows that never sit in a slot."""
    blank = [k for k in data.items if not describe_item(k, data)['description']]
    odd = [k for k in blank if not k.startswith(('Head', 'Hair', 'TEST_', 'PV_', 'Blueprint_', 'Otomo_', 'Yakushima', 'Salvage_'))
           and k != 'MonsterEquipWeapon_Dummy']
    assert odd == [], odd[:10]
    assert len(blank) < 110
