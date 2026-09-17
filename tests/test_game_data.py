"""The shipped data/json is complete and internally consistent.

These run against the real files, so a bad sync or a forgotten mapping fails
here (and in CI) instead of in production.
"""
import json
from pathlib import Path

import pytest

from backend.common.constants import WORK_ICON_MAPPING
from backend.common.game_tables import TABLES, expected_files
from backend.common.map_layers import load_map_layers, which_map
from backend.common.pal_ids import SpeciesIndex
from backend.common.spawns import MIN_SPAWN_SPECIES, plain_without_zones

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'json'
IMG = ROOT / 'frontend' / 'public' / 'img'


def _json(p):
    return json.loads(p.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def pals():
    return _json(DATA / 'pals.json')


def test_every_registered_table_exists():
    missing = [str(p.relative_to(ROOT)) for t in TABLES.values() if t.required for p in t.paths(DATA) if not p.exists()]
    assert not missing


def test_no_unregistered_tables():
    stray = sorted(str(p.relative_to(DATA)) for p in DATA.rglob('*.json') if p not in expected_files(DATA))
    assert stray == [], 'register in backend/common/game_tables.py or delete'


def test_every_work_type_has_icon_slot_name_and_file(pals):
    used = {w for row in pals.values() for w in (row.get('work_suitability') or {})}
    names = _json(DATA / 'l10n' / 'en' / 'work_suitability.json')
    assert used <= set(WORK_ICON_MAPPING), 'add the new work type to WORK_ICON_MAPPING'
    assert used <= set(names)
    for w in used:
        assert (IMG / f't_icon_research_palwork_{WORK_ICON_MAPPING[w]}_0.webp').exists(), w
    # each slot maps to one work type
    assert len(set(WORK_ICON_MAPPING.values())) == len(WORK_ICON_MAPPING)


def test_every_element_has_name_and_icons(pals):
    used = {e for row in pals.values() for e in (row.get('element_types') or [])}
    elements = _json(DATA / 'elements.json')
    l10n = _json(DATA / 'l10n' / 'en' / 'elements.json')
    assert used <= set(elements) and used <= set(l10n)
    for e in used:
        for key in ('icon', 'white_icon'):
            assert (IMG / f"{elements[e][key].lower()}.webp").exists(), (e, key)


def test_map_objects_resolve_and_are_tagged(pals):
    layers = load_map_layers(DATA / 'map_layers.json')
    species = SpeciesIndex(pals.keys())
    objs = _json(DATA / 'map_objects.json')
    assert objs
    for o in objs:
        assert o['map'] in layers, o
        assert o['map'] == which_map(layers, o['x'], o['y']), o
        if o.get('pal'):
            assert species.resolve(o['pal']) is not None, o


def test_map_layers_have_sources_and_square_bounds():
    layers = load_map_layers(DATA / 'map_layers.json')
    assert list(layers) == ['MainMap', 'Tree'], 'first layer is the default'
    for name, m in layers.items():
        assert (IMG / m['source']).exists(), name
        (x0, x1), (y0, y1) = m['x'], m['y']
        assert abs((x1 - x0) - (y1 - y0)) < 1e-6, f'{name}: bounds must be square (square texture)'


def test_spawns_resolve_to_known_species_and_layers(pals):
    """spawns.json (generate_spawns.py) is optional, but when shipped every group must be usable."""
    p = DATA / 'spawns.json'
    if not p.exists():
        pytest.skip('spawns.json not generated')
    groups = _json(p)['groups']
    layers = load_map_layers(DATA / 'map_layers.json')
    species = SpeciesIndex(pals.keys())
    assert groups
    for name, g in groups.items():
        assert g['kind'] in ('field', 'dungeon', 'dungeon_boss', 'field_boss', 'prison_boss'), name
        assert g['pals'], f'{name}: no pals'
        assert any(g['points'].values()), f'{name}: no points'
        for layer, pts in g['points'].items():
            assert layer in layers, name
            (x0, x1), (y0, y1) = layers[layer]['x'], layers[layer]['y']
            for x, y in pts:
                assert x0 <= x <= x1 and y0 <= y <= y1, f'{name}: point off its layer'
        for sid, e in g['pals'].items():
            assert species.resolve(sid) is not None, f'{name}: {sid}'
            assert 0 < e['share'] <= 1, f'{name}: {sid} share'
            assert e['level'][0] <= e['level'][1], f'{name}: {sid} level'
    # the pals the map search is for actually appear somewhere
    ids = {sid.lower() for g in groups.values() for sid in g['pals']}
    assert {'pinkcat', 'sheepball', 'anubis'} <= ids
    # A partial extraction (bad usmap, truncated table) must not ship a half-empty search.
    assert len(ids) >= MIN_SPAWN_SPECIES, f'only {len(ids)} species have spawn zones'
    # The only ordinary species without zones are scripted variants, breeding-only or event pals.
    gap = plain_without_zones(pals, groups)
    assert len(gap) <= 20, f'{len(gap)} ordinary species have no wild spawn zone: {sorted(gap)}'


def test_data_loader_builds_and_reference_is_complete(pals):
    from backend.parser.loaders.data_loader import DataLoader
    dl = DataLoader(DATA)
    assert len(dl.pals) == len(pals)
    ref = dl.reference()
    assert set(ref) == {'elements', 'work_types', 'conditions', 'map_layers'}
    assert ref['elements']['Leaf']['name'] == 'Grass'
    assert ref['work_types']['OilExtraction']['icon'] == 't_icon_research_palwork_13_0'
    assert all(v['icon'] for v in ref['work_types'].values())
    assert list(ref['map_layers']) == ['MainMap', 'Tree']
    assert dl.item('pal_crystal_s') == dl.item('Pal_crystal_S')
    assert dl.trust_thresholds[0] == (0, 0) and dl.trust_thresholds == sorted(dl.trust_thresholds)


def test_data_loader_fails_fast_on_missing_table(tmp_path):
    from backend.parser.loaders.data_loader import DataLoader, GameDataError
    with pytest.raises(GameDataError):
        DataLoader(tmp_path)
