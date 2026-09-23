"""Breeding index over the shipped data/json/breeding.json."""
import json
from pathlib import Path

import pytest

from backend.common.breeding import BreedingIndex, Combo, pair_feasible, plan_route, shortcuts
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


# ----------------------------------------------------------------------
# Route planning
# ----------------------------------------------------------------------
def test_admits_passes_explicit_genders_on_ungated_pairs():
    plain = Combo('A', 'B', 'C')
    assert plain.admits('Male', 'Female') and plain.admits(None, None)
    gated = Combo('A', 'B', 'C', True, 'Male', 'Female')
    assert gated.admits('Male', 'Female') and not gated.admits('Female', 'Male')


def test_pair_feasible_needs_opposite_genders_and_honours_the_gate(index):
    combo = index.child_of('BirdDragon', 'ThunderBird')[0]
    assert pair_feasible(combo, {'BirdDragon': {'Male'}, 'ThunderBird': {'Female'}}, set())
    assert not pair_feasible(combo, {'BirdDragon': {'Male'}, 'ThunderBird': {'Male'}}, set())
    # a bred parent can be hatched in either gender
    assert pair_feasible(combo, {'BirdDragon': {'Male'}}, {'ThunderBird'})
    # same species needs both genders
    same = index.child_of('Alpaca', 'Alpaca')[0]
    assert not pair_feasible(same, {'Alpaca': {'Male'}}, set())
    assert pair_feasible(same, {'Alpaca': {'Male', 'Female'}}, set())
    # gender-gated unique combo: owned genders must match the gate
    gated = [c for c in index.child_of('CatMage', 'FoxMage') if c.child == 'FoxMage_Dark'][0]
    assert pair_feasible(gated, {'CatMage': {gated.parent_a_gender}, 'FoxMage': {gated.parent_b_gender}}, set())
    assert not pair_feasible(gated, {'CatMage': {gated.parent_b_gender}, 'FoxMage': {gated.parent_a_gender}}, set())


def test_route_statuses(index):
    assert plan_route(index, {'Anubis': {'Male'}}, 'Anubis').status == 'owned'
    one = plan_route(index, {'BirdDragon': {'Male'}, 'ThunderBird': {'Female'}}, 'AmaterasuWolf')
    assert one.status == 'breedable' and one.exact and one.breeds == 1
    assert one.steps[0].from_a == one.steps[0].from_b == 'owned'
    # same genders only: that pair is out, and nothing else is owned
    assert plan_route(index, {'BirdDragon': {'Male'}, 'ThunderBird': {'Male'}}, 'AmaterasuWolf').status == 'unreachable'
    # legendaries only breed with themselves
    assert plan_route(index, {'Alpaca': {'Male', 'Female'}}, 'JetDragon').status == 'unreachable'
    assert plan_route(index, {}, 'Anubis').status == 'unreachable'
    assert plan_route(index, {'Alpaca': {'Male'}}, 'NotAPal').status == 'unreachable'


def _check_plan(index, owned, plan, target):
    """Every step is a real pair, feasible in order, each species bred once, target last."""
    assert plan.steps[-1].child == target
    bred = set()
    for step in plan.steps:
        c = step.combo
        assert step.child == c.child
        assert any(x.child == c.child for x in index.child_of(c.parent_a, c.parent_b)), step
        for parent, src in ((c.parent_a, step.from_a), (c.parent_b, step.from_b)):
            assert src in ('owned', 'bred')
            assert parent in (bred if src == 'bred' else owned), step
        assert pair_feasible(c, owned, bred), step
        assert step.child not in bred, 'each species is bred once'
        bred.add(step.child)
    assert plan.breeds == len(plan.steps)
    assert plan.generations == max(s.depth for s in plan.steps)


def test_route_is_a_valid_dependency_ordered_plan(index):
    owned = {'BirdDragon': {'Male'}, 'ThunderBird': {'Female'}, 'SakuraSaurus': {'Female'},
             'DrillGame': {'Male'}, 'SkyDragon': {'Male'}, 'CatBat': {'Male'}}
    route = plan_route(index, owned, 'Anubis')
    assert route.status == 'route' and route.breeds > 1
    assert route.breeds >= route.min_generations
    for plan in route.plans:
        _check_plan(index, owned, plan, 'Anubis')
        assert plan.breeds >= route.breeds, 'plans are sorted, shortest first'


def test_route_exact_search_finds_the_proven_minimum(index):
    # Small owned set with a short answer: the exact search must finish and
    # agree with the depth lower bound where they coincide.
    owned = {'SakuraSaurus': {'Female'}, 'VolcanoDragon': {'Male'}, 'IceFox': {'Male'}}
    route = plan_route(index, owned, 'Anubis', time_budget=5)
    assert route.status == 'route' and route.exact
    _check_plan(index, owned, route.plan, 'Anubis')
    assert route.breeds <= 6


def test_route_gender_needs_follow_the_owned_genders(index):
    # VolcanoDragon owned male only -> whatever it pairs with must be female
    owned = {'SakuraSaurus': {'Female'}, 'VolcanoDragon': {'Male'}, 'IceFox': {'Male'}}
    route = plan_route(index, owned, 'Anubis', time_budget=5)
    for step in route.steps:
        c = step.combo
        if c.parent_a == 'VolcanoDragon' and step.from_b == 'bred':
            assert step.need_b == 'Female'
        if c.parent_b == 'VolcanoDragon' and step.from_a == 'bred':
            assert step.need_a == 'Female'
    hatch = route.plan.hatch()
    assert set(hatch) == {s.child for s in route.steps}


def test_route_timeout_falls_back_to_a_valid_heuristic_plan(index):
    owned = {'Sheepball': {'Female'}, 'LeafMomonga': {'Male'}, 'CloverFairy': {'Female'}, 'CuteFox': {'Male'}}
    route = plan_route(index, owned, 'Anubis', time_budget=0.05)
    assert route.status == 'route' and not route.exact and route.min_generations >= 1
    for plan in route.plans:
        _check_plan(index, owned, plan, 'Anubis')


def test_shortcuts_rank_catchable_intermediates_partners_and_pairs(index):
    owned = {'SakuraSaurus': {'Female'}, 'VolcanoDragon': {'Male'}, 'IceFox': {'Male'}}
    route = plan_route(index, owned, 'Anubis', time_budget=5)
    assert route.status == 'route' and route.breeds > 1
    bred = [s.child for s in route.steps if s.child != 'Anubis']
    # every intermediate catchable: each saves exactly its subtree
    cuts = shortcuts(index, owned, route, {b: 10 for b in bred}, limit=50)
    by = {c.species: c for c in cuts}
    assert set(by) == set(bred)
    for c in cuts:
        assert c.kind == 'intermediate' and c.catches == 1 and c.saves >= 1 and c.breeds_after + c.saves == route.breeds
    assert cuts[0].breeds_after == min(c.breeds_after for c in cuts)
    # a wild partner that finishes it in one breed with an owned pal
    partner = next(c.parent_b for c in index.partners_for('VolcanoDragon', 'Anubis')
                   if c.parent_b not in owned and c.parent_b != 'Anubis')
    cuts = shortcuts(index, owned, route, {partner: 30})
    assert len(cuts) == 1 and cuts[0].kind == 'partner' and cuts[0].partner == 'VolcanoDragon'
    assert cuts[0].breeds_after == 1 and cuts[0].saves == route.breeds - 1 and cuts[0].level == 30
    assert cuts[0].need == 'Female', 'VolcanoDragon is owned male only'
    # both parents wild: catch two, breed once; the easier one leads and pairs are capped
    combos = [c for c in index.parents_of('Anubis') if 'Anubis' not in (c.parent_a, c.parent_b)][:3]
    levels = {}
    for i, c in enumerate(combos):
        levels[c.parent_a] = 40 + i
        levels[c.parent_b] = 20 + i
    cuts = shortcuts(index, owned, route, levels, max_pairs=2)
    pairs = [c for c in cuts if c.kind == 'pair']
    assert 1 <= len(pairs) <= 2
    for c in pairs:
        assert c.catches == 2 and c.breeds_after == 1 and c.level <= c.partner_level
    # single catches with the same breeds left rank before double catches
    cuts = shortcuts(index, owned, route, {**levels, partner: 30})
    assert cuts[0].species == partner and cuts[0].catches == 1
    # nothing catchable, or nothing to shorten -> no shortcuts
    assert shortcuts(index, owned, route, {}) == []
    assert shortcuts(index, owned, plan_route(index, {'Anubis': {'Male'}}, 'Anubis'), {'Anubis': 1}) == []


def test_catchable_levels_use_field_zones_only():
    from backend.common.spawns import catchable_levels, catchable_species
    groups = {'a': {'kind': 'field', 'pals': {'X': {'level': [12, 20]}}}, 'b': {'kind': 'dungeon', 'pals': {'Y': {'level': [1, 5]}}},
              'c': {'kind': 'field_boss', 'pals': {'Z': {'level': [45, 45]}, 'X': {'level': [30, 40]}}}}
    assert catchable_levels(groups) == {'X': 12, 'Z': 45}
    assert catchable_species(groups) == {'X', 'Z'}


def test_owned_genders_and_generations_from(index):
    from types import SimpleNamespace
    from backend.common.breeding import generations_from, owned_genders
    a, b = index.species[0], index.species[1]
    pals = [SimpleNamespace(species_id=a, gender="Male", owner_uid="Envy"),
            SimpleNamespace(species_id=a, gender="Female", owner_uid="Ricky"),
            SimpleNamespace(species_id=b, gender="Male", owner_uid="Envy"),
            SimpleNamespace(species_id=None, gender="Male", owner_uid="Envy"),
            SimpleNamespace(species_id=b, gender="Unknown", owner_uid="Envy")]
    assert owned_genders(pals) == {a: {"Male", "Female"}, b: {"Male"}}
    assert owned_genders(pals, "Envy") == {a: {"Male"}, b: {"Male"}}
    gens = generations_from(index, owned_genders(pals))
    assert gens[a] == 0 and gens[b] == 0
    child = index.child_of(a, b)[0].child
    assert gens.get(child, 0) == (0 if child in (a, b) else 1)
    # Envy alone owns only males, so nothing can be bred
    assert set(generations_from(index, owned_genders(pals, "Envy"))) == {a, b}
