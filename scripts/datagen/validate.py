#!/usr/bin/env python3
"""
Coverage checks for the shipped game-data assets.

Exists because the 1.0 ingest shipped several silent breakages: pals with no
icon (the app derives icon names differently from what the extractor pulled),
a work type with no icon slot (fell through to the Kindling icon), map objects
on a layer with no tiles, and a map texture that was never re-extracted.

Every check here uses the SAME module the app uses for the same derivation
(backend/common/{game_tables,pal_ids,pal_icons,map_layers,constants}.py), so
the validator cannot drift from the app.

Run after any ingest, and in CI (--skip-tiles there: tiles are built in the
Docker image). Non-zero exit on a real problem.
"""

import argparse
import json
import sys

from savepal import ROOT, DATA_JSON, IMG_DIR
from backend.common import pal_icons
from backend.common.constants import WORK_ICON_MAPPING
from backend.common.game_tables import TABLES, expected_files
from backend.common.map_layers import load_map_layers
from backend.common.breeding import BreedingIndex
from backend.common.pal_ids import SpeciesIndex
from backend.common.spawns import MIN_SPAWN_SPECIES, plain_without_zones
from backend.common.partner_skills import LEVELS, MIN_PARTNER_SKILL_SPECIES, has_foreign_markup

# Pals that genuinely have no icon texture in the pak. One id per line; '#' comments.
KNOWN_MISSING = ROOT / 'scripts' / 'datagen' / 'icons_known_missing.txt'

problems, notes = [], []


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _has_icon(cid):
    return any((IMG_DIR / f't_{c}_icon_normal.webp').exists() or (IMG_DIR / f'{c}.webp').exists()
               for c in pal_icons.icon_candidates(cid))


def check_tables():
    """Every registered table exists; nothing unregistered is lying around."""
    for table in TABLES.values():
        for p in table.paths(DATA_JSON):
            if not p.exists():
                (problems if table.required else notes).append(f'{table.name}: missing {p.relative_to(ROOT)}')
    stray = sorted(p.relative_to(DATA_JSON) for p in DATA_JSON.rglob('*.json') if p not in expected_files(DATA_JSON))
    if stray:
        notes.append('unregistered file(s) in data/json (add to game_tables.py or delete): ' + ', '.join(map(str, stray)))


def check_work_types(pals):
    """Every work type any pal has must have an icon slot, a name and an icon on disk."""
    used = {w for row in pals.values() if isinstance(row, dict) for w in (row.get('work_suitability') or {})}
    names = _json(DATA_JSON / 'l10n' / 'en' / 'work_suitability.json')
    for w in sorted(used):
        slot = WORK_ICON_MAPPING.get(w)
        if slot is None:
            problems.append(f'work type {w!r} has no slot in WORK_ICON_MAPPING (constants.py) -- it would show the Kindling icon')
            continue
        if not (IMG_DIR / f't_icon_research_palwork_{slot}_0.webp').exists():
            problems.append(f'work type {w!r}: icon t_icon_research_palwork_{slot}_0.webp missing')
        if w not in names:
            problems.append(f'work type {w!r} has no localized name')
    notes.append(f'{len(used)} work types checked')


def check_elements(pals):
    elements = _json(DATA_JSON / 'elements.json')
    used = {e for row in pals.values() if isinstance(row, dict) for e in (row.get('element_types') or [])}
    for e in sorted(used):
        row = elements.get(e)
        if not row:
            problems.append(f'element {e!r} used by pals but not in elements.json')
            continue
        for key in ('icon', 'white_icon'):
            stem = (row.get(key) or '').lower()
            if not stem or not (IMG_DIR / f'{stem}.webp').exists():
                problems.append(f'element {e!r}: {key} {stem!r} has no webp')
    notes.append(f'{len(used)} elements checked')


def check_map_objects(layers, species):
    p = DATA_JSON / 'map_objects.json'
    if not p.exists():
        problems.append('map_objects.json missing -- run generate_map_objects.py')
        return []
    objs = _json(p)
    if not objs:
        problems.append('map_objects.json is empty')
    for o in objs:
        if o.get('map') and o['map'] not in layers:
            problems.append(f"map_objects: unknown layer {o['map']!r}")
            break
    untagged = [o for o in objs if 'map' not in o]
    if untagged:
        notes.append(f'{len(untagged)} map object(s) have no "map" field (treated as the first layer)')

    unresolved = sorted({o['pal'] for o in objs if o.get('pal') and species.resolve(o['pal']) is None})
    if unresolved:
        problems.append(f'{len(unresolved)} map marker(s) name a pal not in pals.json: ' + ', '.join(unresolved[:8]))
    missing = sorted({o['pal'] for o in objs if o.get('pal') and not _has_icon(o['pal'])})
    if missing:
        problems.append(f'{len(missing)} map marker(s) have no icon on disk: ' + ', '.join(missing[:8]))
    return objs


def check_spawns(layers, species, pals):
    """spawns.json (optional): every group names known layers and resolvable species,
    and the ordinary species with no zone at all are listed (breeding-only / event pals
    are expected there; anything else means the extraction lost something)."""
    p = DATA_JSON / 'spawns.json'
    if not p.exists():
        notes.append('spawns.json missing -- run generate_spawns.py (needs the pak); map spawn search will be hidden')
        return
    groups = (_json(p).get('groups') or {})
    if not groups:
        problems.append('spawns.json has no groups')
        return
    bad_layers = sorted({m for g in groups.values() for m in g.get('points', {}) if m not in layers})
    if bad_layers:
        problems.append('spawns: unknown map layer(s): ' + ', '.join(bad_layers))
    empty = [n for n, g in groups.items() if not g.get('pals') or not any(g.get('points', {}).values())]
    if empty:
        problems.append(f'{len(empty)} spawner group(s) have no pals or no points: ' + ', '.join(empty[:6]))
    ids = sorted({sid for g in groups.values() for sid in g.get('pals', {})})
    unresolved = [sid for sid in ids if species.resolve(sid) is None]
    if unresolved:
        problems.append(f'{len(unresolved)} spawner species not in pals.json: ' + ', '.join(unresolved[:8]))
    no_icon = [sid for sid in ids if not _has_icon(sid)]
    if no_icon:
        notes.append(f'{len(no_icon)} spawner species have no icon on disk: ' + ', '.join(no_icon[:8]))
    n_points = sum(len(v) for g in groups.values() for v in g.get('points', {}).values())
    notes.append(f'spawns: {len(groups)} groups, {n_points} points, {len(ids)} species')
    if len(ids) < MIN_SPAWN_SPECIES:
        problems.append(f'spawns: only {len(ids)} species have zones (expected >= {MIN_SPAWN_SPECIES}) -- partial extraction?')
    gap = sorted(plain_without_zones(pals, groups))
    if gap:
        notes.append(f'{len(gap)} ordinary species have no wild spawn zone (breeding-only / event pals expected): '
                     + ', '.join(gap))


def check_partner_skills(pals):
    """partner_skills.json (optional): every ordinary species should have a named skill with
    five rendered levels and no leftover game markup or placeholders."""
    p = DATA_JSON / 'partner_skills.json'
    if not p.exists():
        notes.append('partner_skills.json missing -- run generate_partner_skills.py (needs the pak); modal hides the block')
        return
    table = _json(p).get('species') or {}
    if len(table) < MIN_PARTNER_SKILL_SPECIES:
        problems.append(f'partner skills: only {len(table)} species (expected >= {MIN_PARTNER_SKILL_SPECIES}) -- partial extraction?')
    bad = [sid for sid, e in table.items()
           if not e.get('name') or len(e.get('levels') or []) != LEVELS
           or any(not lv.get('text') or has_foreign_markup(lv['text']) or '{' in lv['text'] for lv in e['levels'])]
    if bad:
        problems.append(f'{len(bad)} partner skill(s) malformed (no name / not {LEVELS} levels / leftover markup): ' + ', '.join(bad[:8]))
    unknown = [sid for sid in table if sid not in pals]
    if unknown:
        problems.append(f'{len(unknown)} partner skill species not in pals.json: ' + ', '.join(unknown[:8]))
    ordinary = [sid for sid, row in pals.items() if row.get('is_pal') and not sid.startswith(('BOSS_', 'GYM_', 'RAID_', 'PREDATOR_', 'SUMMON_', 'POLICE_'))
                and not any(t in sid for t in ('_Oilrig', '_Tower', '_Quest'))]
    gap = sorted(sid for sid in ordinary if sid not in table)
    if gap:
        notes.append(f'{len(gap)} ordinary species have no partner skill text: ' + ', '.join(gap))
    notes.append(f'partner skills: {len(table)} species')


def check_breeding(pals, species):
    """breeding.json indexes against pals.json; every pair resolves; the special combos survive."""
    p = DATA_JSON / 'breeding.json'
    if not p.exists():
        problems.append('breeding.json missing -- run sync_game_data.py')
        return
    idx = BreedingIndex(_json(p), species)
    if idx.pair_count() < 30000 or len(idx.species) < 250:
        problems.append(f'breeding.json looks truncated: {len(idx.species)} species, {idx.pair_count()} pairs')
    if idx.unresolved:
        notes.append(f'breeding: {len(idx.unresolved)} upstream id(s) not in pals.json, dropped: ' + ', '.join(sorted(idx.unresolved)))
    for sid in idx.species:
        if not idx.child_of(sid, sid):
            problems.append(f'breeding: {sid} + {sid} has no outcome')
            break
    if not any(c.unique for c in idx.child_of('LazyDragon', 'ElecCat')):
        problems.append('breeding: unique combos missing (Relaxaurus + Sparkit should be Relaxaurus Lux)')
    notes.append(f'{len(idx.species)} breedable species, {idx.pair_count()} pairs, {len(idx.ignore_combi)} self-only')


def check_pal_icons(pals):
    """Every pal in pals.json must resolve to an icon via pal_icons.icon_candidates()."""
    allow = set()
    if KNOWN_MISSING.exists():
        allow = {l.strip() for l in KNOWN_MISSING.read_text().splitlines() if l.strip() and not l.startswith('#')}
    missing = sorted(cid for cid, row in pals.items()
                     if isinstance(row, dict) and row.get('is_pal') and not row.get('disabled')
                     and cid not in allow and not _has_icon(cid))
    stale = sorted(cid for cid in allow if cid in pals and _has_icon(cid))
    if missing:
        problems.append(f'{len(missing)} pal(s) have no icon on disk (run generate_icons.py --extract, '
                        f'or add to {KNOWN_MISSING.name} if the pak has none): '
                        + ', '.join(missing[:8]) + ('...' if len(missing) > 8 else ''))
    if stale:
        notes.append(f'{len(stale)} entr(y/ies) in {KNOWN_MISSING.name} now have an icon: ' + ', '.join(stale))
    notes.append(f'{len(pals)} pals checked for a derived icon, {len(allow)} allow-listed')


def check_referenced_icons():
    """Every `icon` field in data/json should resolve to a shipped webp (note only: upstream placeholders exist)."""
    needed = set()
    for jf in DATA_JSON.glob('*.json'):
        data = _json(jf)
        for e in (data.values() if isinstance(data, dict) else data):
            if isinstance(e, dict) and isinstance(e.get('icon'), str) and e['icon'].strip():
                needed.add(e['icon'].strip().lower())
    missing = {i for i in needed if not (IMG_DIR / f'{i}.webp').exists()}
    if missing:
        notes.append(f'{len(missing)} `icon` value(s) have no webp (upstream placeholders): ' + ', '.join(sorted(missing)[:6]))


def check_layers(layers, objs, skip_tiles):
    used = {o.get('map', next(iter(layers))) for o in objs}
    for name, m in layers.items():
        if not (IMG_DIR / m['source']).exists():
            problems.append(f"{name}: source image {m['source']} missing")
        if skip_tiles:
            continue
        td = IMG_DIR / m['tiles']
        n = len(list(td.rglob('*.webp'))) if td.exists() else 0
        if n == 0:
            (problems if name in used else notes).append(f"{name}: no tiles in {m['tiles']}/ -- run scripts/slice_map.py")
        else:
            notes.append(f"{name}: {n} tiles, source {m['source']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-tiles', action='store_true', help='do not require sliced tiles (CI)')
    args = ap.parse_args()

    check_tables()
    if problems:
        for p in problems:
            print(f'  - {p}')
        return 1
    pals = _json(DATA_JSON / 'pals.json')
    layers = load_map_layers(DATA_JSON / 'map_layers.json')
    species = SpeciesIndex(pals.keys())

    check_work_types(pals)
    check_elements(pals)
    objs = check_map_objects(layers, species)
    check_pal_icons(pals)
    check_spawns(layers, species, pals)
    check_partner_skills(pals)
    check_breeding(pals, species)
    check_referenced_icons()
    check_layers(layers, objs, args.skip_tiles)

    for n in notes:
        print(f'  note: {n}')
    if problems:
        print('\nFAILED:')
        for p in problems:
            print(f'  - {p}')
        return 1
    print('\nAll checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
