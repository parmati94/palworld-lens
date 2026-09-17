#!/usr/bin/env python3
"""
Generate data/json/spawns.json -- where each wild pal species can spawn.

Wild pals are never written to a save (the game respawns them), so this comes
from the game's own spawner tables in the client pak, read with the CUE4Parse
extractor (scripts/datagen/extractor):

  DT_PalSpawnerPlacement  8k+ spawner points: world X/Y, spawner name, radius,
                          placement type (field / dungeon / boss room)
  DT_PalWildSpawner       what each spawner name rolls: weighted rows of up to
                          three pals with level ranges, night-only flag

Every placement with the same spawner name rolls the same table, so the output
is grouped by spawner name: one entry with all its points (pre-partitioned by
map layer, like map_objects.json) and the pals it can produce with their share
of the group's total weight, level range and time-of-day restriction. The map
tab lights up every group that contains the searched species.

Pal ids are resolved to pals.json keys with backend/common/pal_ids.py (BOSS_
prefix stripped, variants trimmed), the same rule as save characters; boss
spawns keep a `boss` flag so the UI can tell an alpha room from a field herd.

Usage:
  python3 scripts/datagen/generate_spawns.py            # extract from the pak
  python3 scripts/datagen/generate_spawns.py --src DIR  # DIR has placement.json + wildspawner.json
  python3 scripts/datagen/generate_spawns.py --dry-run
"""

import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.pal_ids import SpeciesIndex, is_boss_id
from backend.common.map_layers import load_map_layers, which_map

OUT_PATH = DATA_JSON / 'spawns.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'spawns'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')

TABLES = {'placement.json': 'DT_PalSpawnerPlacement', 'wildspawner.json': 'DT_PalWildSpawner'}

KIND = {
    'EPalSpawnerPlacementType::Field': 'field',
    'EPalSpawnerPlacementType::Dungeon': 'dungeon',
    'EPalSpawnerPlacementType::DungeonBoss': 'dungeon_boss',
    'EPalSpawnerPlacementType::FieldBoss': 'field_boss',
    'EPalSpawnerPlacementType::ImprisonmentBoss': 'prison_boss',
}
NONE = 'None'


def enum_suffix(v: str) -> str:
    """`EPalOneDayTimeType::Night` -> `night`; Undefined -> ''."""
    s = (v or '').split('::')[-1]
    return '' if s in ('', 'Undefined') else s.lower()


def extract(src: Path) -> None:
    """Dump both tables from the pak into src/ via the extractor."""
    if not EXTRACTOR.exists():
        raise SystemExit(f'error: extractor not built: {EXTRACTOR} (see scripts/datagen/README.md)')
    if not PAK_DIR.is_dir() or not USMAP or not Path(USMAP).exists():
        raise SystemExit('error: PALWORLD_PAK_DIR / PALWORLD_USMAP missing -- required to read the spawner tables')
    src.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PALWORLD_PAK_DIR': str(PAK_DIR), 'PALWORLD_USMAP': USMAP}
    for fname, table in TABLES.items():
        print(f'extracting {table} ...')
        r = subprocess.run([str(EXTRACTOR), 'dt', table, str(src / fname)], env=env)
        if r.returncode != 0:
            raise SystemExit(f'error: extractor failed on {table}')


def load_rows(src: Path, fname: str) -> dict:
    with open(src / fname, encoding='utf-8') as f:
        data = json.load(f)
    rows = data.get('Rows') if isinstance(data, dict) else None
    if not rows:
        raise SystemExit(f'error: {src / fname} has no Rows')
    return rows


def build(src: Path, layers, species: SpeciesIndex):
    placements = load_rows(src, 'placement.json')
    wild = load_rows(src, 'wildspawner.json')

    rows_by_name = collections.defaultdict(list)
    for r in wild.values():
        rows_by_name[r['SpawnerName']].append(r)

    groups, unresolved, dropped = {}, set(), collections.Counter()
    for p in placements.values():
        name = p.get('SpawnerName') or NONE
        kind = KIND.get(p.get('PlacementType'))
        rows = rows_by_name.get(name)
        if name == NONE or kind is None or not rows:
            dropped[name] += 1
            continue
        g = groups.get(name)
        if g is None:
            g = groups[name] = {'kind': kind, 'radius': int(p.get('StaticRadius') or 0),
                                'points': collections.defaultdict(list), 'pals': None}
        loc = p['Location']
        x, y = float(loc['X']), float(loc['Y'])
        g['points'][which_map(layers, x, y)].append([round(x), round(y)])

    # What each group rolls. A row is one "sheet": all its pals spawn together,
    # so a pal's share is the weight of the rows that include it over the
    # group's total weight (NPC-only rows count toward the total).
    for name, g in groups.items():
        rows = rows_by_name[name]
        total = sum(float(r.get('Weight') or 0) for r in rows) or 1.0
        pals = {}
        for r in rows:
            w = float(r.get('Weight') or 0)
            seen = set()   # a row can list the same species twice (a pack); count its weight once
            for i in (1, 2, 3):
                raw = r.get(f'Pal_{i}') or NONE
                if raw in (NONE, 'RowName'):   # 'RowName' = the table's template row
                    continue
                pid = species.resolve(raw)
                if pid is None:
                    unresolved.add(raw)
                    pid = raw
                e = pals.get(pid)
                if e is None:
                    e = pals[pid] = {'weight': 0.0, 'lv': [10 ** 6, 0], 'times': set(), 'boss': False}
                if pid not in seen:
                    seen.add(pid)
                    e['weight'] += w
                # A few rows ship LvMin > LvMax; treat them as the range either way round.
                lo, hi = sorted((int(r.get(f'LvMin_{i}') or 0), int(r.get(f'LvMax_{i}') or 0)))
                e['lv'][0] = min(e['lv'][0], lo)
                e['lv'][1] = max(e['lv'][1], hi)
                e['times'].add(enum_suffix(r.get('OnlyTime')))
                e['boss'] = e['boss'] or is_boss_id(raw)
        out = {}
        for pid, e in sorted(pals.items()):
            if e['weight'] <= 0:
                continue          # weight 0 = listed but never rolled
            entry = {'share': max(0.001, round(e['weight'] / total, 3)), 'level': e['lv']}
            if len(e['times']) == 1 and next(iter(e['times'])):
                entry['time'] = next(iter(e['times']))   # every row with this pal is night-only
            if e['boss']:
                entry['boss'] = True
            out[pid] = entry
        g['pals'] = out
        g['points'] = {k: v for k, v in g['points'].items()}

    # Groups that only roll humans (hunter camps, dungeon guards) have nothing
    # to search for; drop them rather than ship empty entries.
    npc_only = [n for n, g in groups.items() if not g['pals']]
    for n in npc_only:
        dropped[f'{n} (NPC only)'] += sum(len(v) for v in groups.pop(n)['points'].values())

    return dict(sorted(groups.items())), sorted(unresolved), dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with placement.json + wildspawner.json (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = args.src or CACHE
    if not args.src:
        extract(src)

    layers = load_map_layers(DATA_JSON / 'map_layers.json')
    with open(DATA_JSON / 'pals.json', encoding='utf-8') as f:
        species = SpeciesIndex(json.load(f).keys())
    groups, unresolved, dropped = build(src, layers, species)

    n_points = sum(len(v) for g in groups.values() for v in g['points'].values())
    pal_ids = {p for g in groups.values() for p in g['pals']}
    kinds = collections.Counter(g['kind'] for g in groups.values())
    print(f'\n{len(groups)} spawner groups, {n_points} points, {len(pal_ids)} species')
    print('by kind: ' + ', '.join(f'{k}={v}' for k, v in sorted(kinds.items())))
    if dropped:
        print(f'dropped {sum(dropped.values())} placement(s) with no spawner definition: '
              + ', '.join(f'{k}×{v}' for k, v in dropped.most_common(6)))
    if unresolved:
        print(f'\nWARNING: {len(unresolved)} spawner pal id(s) not in pals.json: ' + ', '.join(unresolved[:12]))
        print('  (kept with the raw id; the UI shows the id)')

    if args.dry_run:
        print('\n--dry-run: not written')
        return 0
    doc = {
        '_comment': 'Generated by scripts/datagen/generate_spawns.py from the game\'s DT_PalSpawnerPlacement '
                    'and DT_PalWildSpawner tables. groups[name] = one spawner definition: its points per map '
                    'layer (world coords), spawn radius, and the pals it rolls with their share of the group '
                    'weight, level range and night-only flag. Do not edit by hand.',
        'groups': groups,
    }
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')
    print(f'\nWrote {len(groups)} groups -> {OUT_PATH.relative_to(REPO)} ({OUT_PATH.stat().st_size // 1024} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
