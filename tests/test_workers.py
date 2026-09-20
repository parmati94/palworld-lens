"""backend/common/workers.py -- best owned / catchable for a work type."""
from types import SimpleNamespace

from backend.common.workers import best_owned, catchable_workers, max_work_level, owned_species_counts, work_types

SPECIES = {
    "Kitsunebi": {"work_suitability": {"EmitFlame": 1}},
    "Ragnahawk": {"work_suitability": {"EmitFlame": 3, "Transport": 3}},
    "Jormuntide_Ignis": {"work_suitability": {"EmitFlame": 4}},
    "Blazehowl": {"work_suitability": {"EmitFlame": 3}},
    "BOSS_Ragnahawk": {"work_suitability": {"EmitFlame": 3}},
    "Lamball": {"work_suitability": {"Handcraft": 1, "EmitFlame": 0}},
}
CATCHABLE = {"Kitsunebi": 3, "Ragnahawk": 28, "Blazehowl": 22, "BOSS_Ragnahawk": 30}


def _pal(iid, sid, level, work, owner="Envy", nickname=None):
    return SimpleNamespace(instance_id=iid, species_id=sid, name=sid, nickname=nickname,
                           owner_uid=owner, level=level, work_suitability=work, base_name=None)


def test_work_types_lists_only_used_types():
    assert work_types(SPECIES) == ["EmitFlame", "Handcraft", "Transport"]


def test_best_owned_ranks_work_level_then_pal_level_and_uses_nickname():
    pals = [
        _pal("a", "Kitsunebi", 40, {"EmitFlame": 1}),
        _pal("b", "Ragnahawk", 20, {"EmitFlame": 3}, owner="Ricky"),
        _pal("c", "Ragnahawk", 35, {"EmitFlame": 4}, nickname="Hotwing"),   # condensed to 4
        _pal("d", "Lamball", 50, {"Handcraft": 1}),                           # not a kindler
        _pal("e", "Blazehowl", 30, {"EmitFlame": 3}, owner=None),
    ]
    got = best_owned(pals, "EmitFlame", limit=3)
    assert [(o.instance_id, o.work_level) for o in got] == [("c", 4), ("e", 3), ("b", 3)]
    assert got[0].name == "Hotwing" and got[2].owner == "Ricky"


def test_best_owned_folds_same_species_owner_and_level():
    pals = [
        _pal("a", "Ragnahawk", 20, {"EmitFlame": 3}),
        _pal("b", "Ragnahawk", 31, {"EmitFlame": 3}),
        _pal("c", "Ragnahawk", 25, {"EmitFlame": 3}, owner="Ricky"),
        _pal("d", "Ragnahawk", 10, {"EmitFlame": 4}),
    ]
    got = best_owned(pals, "EmitFlame")
    assert [(o.instance_id, o.count) for o in got] == [("d", 1), ("b", 2), ("c", 1)]


def test_max_work_level():
    assert max_work_level(SPECIES, "EmitFlame") == 4
    assert max_work_level(SPECIES, "Cool") == 0


def test_catchable_workers_skips_bosses_and_uncatchable_and_ranks_by_spawn_level():
    got = catchable_workers(SPECIES, CATCHABLE, "EmitFlame", owned_counts={"Ragnahawk": 2})
    ids = [(c.species_id, c.work_level, c.spawn_level, c.owned) for c in got]
    # Jormuntide_Ignis has no field spawn; BOSS_ variant dropped; level 3s ordered by lowest spawn level
    assert ids == [("Blazehowl", 3, 22, 0), ("Ragnahawk", 3, 28, 2), ("Kitsunebi", 1, 3, 0)]


def test_owned_species_counts():
    pals = [_pal("a", "Kitsunebi", 1, {}), _pal("b", "Kitsunebi", 1, {}), _pal("c", None, 1, {})]
    assert owned_species_counts(pals) == {"Kitsunebi": 2}
