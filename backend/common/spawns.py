"""Coverage helpers for data/json/spawns.json (wild spawner groups).

Pure python, shared by scripts/datagen/generate_spawns.py (delta report),
scripts/datagen/validate.py (coverage note) and tests/. The question they all
ask: which ordinary, catchable species have no wild spawn zone at all?

A species is "plain" when pals.json flags it as a pal and not a boss of any
kind, and its id is not a scripted variant (quest, oil-rig, PIDF, gym or
summon copies of an ordinary species). Plain species without zones are not
an error -- breeding-only and event pals (raids, meteor drops) exist -- but
they are the list to read after a game patch.
"""

from __future__ import annotations

from typing import Dict, Iterable, Set

# Tokens that mark a scripted copy of a species rather than a wild one.
VARIANT_TOKENS = ('quest', 'oilrig', 'police', 'gym', 'summon', 'predator')

# Fewer species than this means the extraction is partial (bad usmap, truncated
# table), not a smaller game. 1.0 ships ~286; paldb lists 273 with spawn areas.
MIN_SPAWN_SPECIES = 270


def is_variant_id(species_id: str) -> bool:
    parts = species_id.lower().split('_')
    return any(t in parts for t in VARIANT_TOKENS)


def plain_species(pals: Dict[str, Dict]) -> Set[str]:
    """Ordinary catchable species ids: is_pal, no boss/raid/tower/predator flag, no variant token."""
    out = set()
    for sid, row in pals.items():
        if not isinstance(row, dict) or not row.get('is_pal') or row.get('disabled'):
            continue
        if row.get('is_boss') or row.get('is_tower_boss') or row.get('is_raid_boss') or row.get('predator'):
            continue
        if is_variant_id(sid):
            continue
        out.add(sid)
    return out


def catchable_levels(groups: Dict[str, Dict]) -> Dict[str, int]:
    """Species with a wild field spawn (field or field-boss zone) -> the lowest level it spawns at.

    "Can I go catch one, and how early": dungeon-only spawns are left out
    (rooms are instanced and the map hides them by default), and the level
    is the floor of every zone's range, i.e. the easiest place to find it.
    """
    out: Dict[str, int] = {}
    for g in groups.values():
        if g.get('kind') not in ('field', 'field_boss'):
            continue
        for sid, e in (g.get('pals') or {}).items():
            lv = int((e.get('level') or [0, 0])[0])
            out[sid] = min(out.get(sid, 10 ** 6), lv)
    return out


def catchable_species(groups: Dict[str, Dict]) -> Set[str]:
    return set(catchable_levels(groups))


def species_with_zones(groups: Dict[str, Dict]) -> Set[str]:
    """Every species id that appears in at least one spawner group."""
    return {sid for g in groups.values() for sid in (g.get('pals') or {})}


def plain_without_zones(pals: Dict[str, Dict], groups: Dict[str, Dict]) -> Set[str]:
    have = {s.lower() for s in species_with_zones(groups)}
    return {sid for sid in plain_species(pals) if sid.lower() not in have}


def delta(old_groups: Dict[str, Dict], new_groups: Dict[str, Dict]) -> Dict[str, Iterable[str]]:
    """Species gained / lost between two spawn files (case-insensitive ids)."""
    old = {s.lower(): s for s in species_with_zones(old_groups)}
    new = {s.lower(): s for s in species_with_zones(new_groups)}
    return {
        'gained': sorted(new[k] for k in new.keys() - old.keys()),
        'lost': sorted(old[k] for k in old.keys() - new.keys()),
    }
