"""Base metadata is derived once and named consistently (extractors/bases.py)."""
from backend.parser.extractors.bases import get_base_metadata, get_base_assignments


def _base(guild, name, container, x=1.0):
    return {
        'RawData': {'value': {'name': name, 'group_id_belong_to': guild}},
        'WorkerDirector': {'value': {'RawData': {'value': {'container_id': container,
                                                            'spawn_transform': {'translation': {'x': x, 'y': 2.0, 'z': 3.0}}}}}},
    }


def test_naming_and_numbering_per_guild():
    meta = get_base_metadata({
        'b1': _base('g1', '新規生成拠点テンプレート名', 'c1'),
        'b2': _base('g1', '', 'c2'),
        'b3': _base('g2', 'Home', 'c3'),
        'b4': _base('g2', None, None),   # no worker container: not a real base
    })
    assert set(meta) == {'b1', 'b2', 'b3'}
    assert meta['b1'].name == 'Base 1' and meta['b2'].name == 'Base 2'
    assert meta['b3'].name == 'Home'
    assert (meta['b1'].x, meta['b1'].y, meta['b1'].z) == (1.0, 2.0, 3.0)


def test_assignments_follow_the_worker_container():
    meta = get_base_metadata({'b1': _base('g1', '', 'c1')})
    chars = {
        'p1': {'IsPlayer': {'value': True}, 'SlotId': {'value': {'ContainerId': {'value': {'ID': {'value': 'c1'}}}}}},
        'pal1': {'SlotId': {'value': {'ContainerId': {'value': {'ID': {'value': 'c1'}}}}}},
        'pal2': {'SlotId': {'value': {'ContainerId': {'value': {'ID': {'value': 'elsewhere'}}}}}},
    }
    assert get_base_assignments(chars, meta) == {'pal1': {'base_id': 'b1', 'guild_id': 'g1', 'base_name': 'Base 1', 'base_place': None}}


LAYERS = {'MainMap': {'x': [-10, 10], 'y': [-10, 10]}}
LANDMARKS = [{'type': 'fast_travel', 'localized_name': 'Kelpsea Hill', 'x': 1, 'y': 2, 'map': 'MainMap'},
             {'type': 'fast_travel', 'localized_name': 'Far Away', 'x': 9, 'y': 9, 'map': 'MainMap'}]


def test_place_number_and_custom_name():
    meta = get_base_metadata({
        'b1': _base('g1', '', 'c1'),
        'b2': _base('g1', '', 'c2', x=8.5),
    }, landmarks=LANDMARKS, layers=LAYERS, custom_names={'b2': 'The Ranch', 'gone': 'x'})
    assert (meta['b1'].name, meta['b1'].number, meta['b1'].place, meta['b1'].custom_name) == ('Base 1', 1, 'Kelpsea Hill', None)
    assert (meta['b2'].name, meta['b2'].number, meta['b2'].place, meta['b2'].custom_name) == ('The Ranch', 2, 'Far Away', 'The Ranch')
    # the custom name follows the base into pal assignments
    chars = {'pal1': {'SlotId': {'value': {'ContainerId': {'value': {'ID': {'value': 'c2'}}}}}}}
    assert get_base_assignments(chars, meta)['pal1'] == {'base_id': 'b2', 'guild_id': 'g1', 'base_name': 'The Ranch', 'base_place': 'Far Away'}


def test_no_landmarks_means_no_place():
    meta = get_base_metadata({'b1': _base('g1', '', 'c1')})
    assert meta['b1'].place is None and meta['b1'].number == 1
