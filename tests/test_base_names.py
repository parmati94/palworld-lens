"""backend/common/base_names.py -- nearest landmark and the custom-name store."""
import json
import os
import stat

import pytest

from backend.common.base_names import BaseNameStore, clean_name, nearest_landmark

LAYERS = {'MainMap': {'x': [-1000, 1000], 'y': [-1000, 1000]}, 'Tree': {'x': [5000, 6000], 'y': [5000, 6000]}}
LANDMARKS = [
    {'type': 'fast_travel', 'localized_name': 'Kelpsea Hill', 'x': 0, 'y': 0, 'map': 'MainMap'},
    {'type': 'fast_travel', 'localized_name': 'Anubis Dunes', 'x': 500, 'y': 500, 'map': 'MainMap'},
    {'type': 'fast_travel', 'localized_name': 'Root', 'x': 5500, 'y': 5500, 'map': 'Tree'},
    {'type': 'alpha_pal', 'localized_name': 'Chillet', 'x': 10, 'y': 10, 'map': 'MainMap'},   # not a landmark
]


def test_nearest_landmark_is_a_fast_travel_on_the_same_layer():
    assert nearest_landmark(20, 20, LAYERS, LANDMARKS) == 'Kelpsea Hill'
    assert nearest_landmark(400, 400, LAYERS, LANDMARKS) == 'Anubis Dunes'
    assert nearest_landmark(5900, 5900, LAYERS, LANDMARKS) == 'Root'      # Tree layer, even though MainMap points are closer in raw distance? no: they are far; still layer-gated
    assert nearest_landmark(None, 5, LAYERS, LANDMARKS) is None
    assert nearest_landmark(5, 5, LAYERS, []) is None


def test_clean_name():
    assert clean_name('  Kelpsea   Hill \n') == 'Kelpsea Hill'
    assert clean_name(None) == '' and clean_name('   ') == ''
    assert len(clean_name('x' * 100)) == 40


def test_store_round_trips_and_clears(tmp_path):
    store = BaseNameStore(str(tmp_path / 'state'))
    assert store.writable and store.load() == {}
    assert store.set('b1', '  Home base ') == 'Home base'
    assert store.set('b2', 'Ranch') == 'Ranch'
    assert json.loads((tmp_path / 'state' / 'base_names.json').read_text()) == {'b1': 'Home base', 'b2': 'Ranch'}
    assert store.set('b1', '') is None
    fresh = BaseNameStore(str(tmp_path / 'state'))
    assert fresh.load() == {'b2': 'Ranch'}
    assert not list((tmp_path / 'state').glob('.base_names.*'))   # no temp files left behind


def test_store_ignores_a_corrupt_file(tmp_path):
    (tmp_path / 'base_names.json').write_text('{not json')
    assert BaseNameStore(str(tmp_path)).load() == {}


def test_store_without_a_directory_is_read_only(tmp_path):
    assert not BaseNameStore(None).writable
    if os.geteuid() == 0:
        pytest.skip('root can write anywhere')
    ro = tmp_path / 'ro'
    ro.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        store = BaseNameStore(str(ro))
        assert not store.writable
        with pytest.raises(PermissionError):
            store.set('b1', 'x')
    finally:
        ro.chmod(stat.S_IRWXU)


def test_set_drops_names_of_bases_that_no_longer_exist(tmp_path):
    store = BaseNameStore(str(tmp_path))
    store.set('old', 'Torn down')
    store.set('b1', 'Home')
    assert store.set('b2', 'Ranch', keep=['b1', 'b2']) == 'Ranch'
    assert BaseNameStore(str(tmp_path)).load() == {'b1': 'Home', 'b2': 'Ranch'}
    assert store.set('b1', '', keep=['b2']) is None
    assert store.names == {'b2': 'Ranch'}
