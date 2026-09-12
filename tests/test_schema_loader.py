"""YAML field extraction (backend/parser/loaders/schema_loader.py)."""
import pytest

from backend.parser.loaders.schema_loader import SchemaManager

pytestmark = pytest.mark.filterwarnings('ignore')


def test_pal_fields_drill_and_strip():
    pals = SchemaManager.get('pals.yaml')
    char = {
        'CharacterID': {'value': 'BOSS_CatBat'},
        'Level': {'value': 12},
        'Hp': {'value': {'Value': {'value': 1234000}}},
        'Gender': {'value': {'value': 'EPalGenderType::Female'}},
        'EquipWaza': {'value': {'values': ['EPalWazaID::AirCanon']}},
        'GotWorkSuitabilityAddRankList': {'value': {'values': [
            {'WorkSuitability': {'value': {'value': 'EPalWorkSuitability::Mining'}}, 'Rank': {'value': 1}}]}},
    }
    assert pals.extract_field(char, 'CharacterID') == 'BOSS_CatBat'
    assert pals.extract_field(char, 'Level') == 12
    assert pals.extract_field(char, 'Hp') == 1234
    assert pals.extract_field(char, 'Gender') == 'Female'
    assert pals.extract_field(char, 'Rank') == 1          # default
    assert pals.extract_field(char, 'NickName') is None   # default null
    assert pals.extract_list(char, 'EquipWaza') == ['EPalWazaID::AirCanon']
    assert pals.extract_list(char, 'GotWorkSuitabilityAddRankList') == [{'work_type': 'Mining', 'rank_bonus': 1}]
    assert pals.extract_field(char, 'NotAField') is None


def test_every_schema_field_has_root_key():
    for name in ('pals.yaml', 'players.yaml', 'guilds.yaml', 'bases.yaml', 'containers.yaml', 'structures.yaml'):
        loader = SchemaManager.get(name)
        for field, spec in loader.fields.items():
            assert 'root_key' in spec, f'{name}: {field}'


def test_collection_extraction():
    coll = SchemaManager.get('collections.yaml')
    world = {'CharacterSaveParameterMap': {'value': [
        {'key': {'InstanceId': {'value': 'abc'}}, 'value': {'RawData': {'value': {'object': {'SaveParameter': {'value': {'Level': {'value': 3}}}}}}}},
        {'key': 'raw-uuid', 'value': {'RawData': {'value': {'object': {'SaveParameter': {'value': {'Level': {'value': 4}}}}}}}},
    ]}}
    out = coll.extract_collection(world, 'characters')
    assert set(out) == {'abc', 'raw-uuid'}
    assert out['raw-uuid']['Level']['value'] == 4
