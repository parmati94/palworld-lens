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
    assert get_base_assignments(chars, meta) == {'pal1': {'base_id': 'b1', 'guild_id': 'g1', 'base_name': 'Base 1'}}
