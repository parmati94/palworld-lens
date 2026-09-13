"""Breeding index over the shipped data/json/breeding.json."""
import json
from pathlib import Path

import pytest

from backend.common.breeding import BreedingIndex, Combo
from backend.common.pal_ids import SpeciesIndex

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'json'


@pytest.fixture(scope='module')
def pals():
    return json.loads((DATA / 'pals.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def index(pals):
    table = json.loads((DATA / 'breeding.json').read_text(encoding='utf-8'))
    return BreedingIndex(table, SpeciesIndex(pals.keys()))


def test_species_are_pals_json_ids_and_placeholders_are_dropped(index, pals):
    assert index.species and all(s in pals for s in index.species)
    assert 'Sheepball' in index.species            # table spells it SheepBall
    # unreleased "Unidentified Pal" rows exist upstream but not in pals.json
    assert index.unresolved <= {'CandleWitch', 'StrawHatCat', 'VolcanicTurtle'}
    assert len(index.species) > 290


def test_same_species_breeds_itself(index):
    for sid in index.species:
        kids = index.child_of(sid, sid)
        assert [k.child for k in kids] == [sid], sid


def test_ignore_combi_species_only_breed_with_themselves(index):
    assert 'JetDragon' in index.ignore_combi
    assert index.child_of('JetDragon', 'Sheepball') == []
    assert index.parents_of('JetDragon') == [Combo('JetDragon', 'JetDragon', 'JetDragon')]


def test_unique_combo_beats_formula_and_is_symmetric(index):
    a = index.child_of('LazyDragon', 'ElecCat')
    b = index.child_of('ElecCat', 'LazyDragon')
    assert [c.child for c in a] == ['LazyDragon_Electric'] and a[0].unique
    assert [c.child for c in b] == ['LazyDragon_Electric']
    assert b[0].parent_a == 'ElecCat', 'oriented to the caller'
    # the overridden formula pair is not offered as a way to make its formula child
    assert all(not (set((c.parent_a, c.parent_b)) == {'LazyDragon', 'ElecCat'})
               for c in index.parents_of('GrassPanda'))


def test_gender_gated_pair_depends_on_parent_gender(index):
    both = index.child_of('CatMage', 'FoxMage')
    assert sorted(c.child for c in both) == ['CatMage_Fire', 'FoxMage_Dark']
    assert [c.child for c in index.child_of('CatMage', 'FoxMage', 'Male', 'Female')] == ['FoxMage_Dark']
    assert [c.child for c in index.child_of('CatMage', 'FoxMage', 'Female', 'Male')] == ['CatMage_Fire']
    # mirrored call keeps the gate attached to the right species
    assert [c.child for c in index.child_of('FoxMage', 'CatMage', 'Female', 'Male')] == ['FoxMage_Dark']
    assert [c.child for c in index.child_of('FoxMage', 'CatMage', 'Male', 'Female')] == ['CatMage_Fire']


def test_every_pair_of_breedable_species_has_an_outcome(index):
    plain = [s for s in index.species if s not in index.ignore_combi]
    for a in plain[::7]:
        for b in plain[::11]:
            assert index.child_of(a, b), (a, b)


def test_parents_partners_and_raw_ids(index):
    parents = index.parents_of('Anubis')
    assert parents and all(c.child == 'Anubis' for c in parents)
    assert parents[0].unique or not any(c.unique for c in parents), 'unique combos sort first'
    partners = index.partners_for('Sheepball', 'Anubis')
    assert all(c.parent_a == 'Sheepball' for c in partners)
    # raw save ids resolve like everywhere else
    assert index.child_of('BOSS_SheepBall', 'sheepball')[0].child == 'Sheepball'
    assert index.is_breedable('BOSS_Anubis') and not index.is_breedable('Nope')


def test_data_loader_exposes_breeding():
    from backend.parser.loaders.data_loader import DataLoader
    dl = DataLoader(DATA)
    assert dl.breeding.pair_count() > 30000
    assert dl.breeding.is_breedable('Anubis')
