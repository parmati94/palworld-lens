#!/usr/bin/env python3
"""
Generate data/json/map_objects.json from a palworld-save-pal release.

map_objects.json drives the static markers on the world map (fast-travel points,
alpha pals, predators, dungeons). save-pal ships the source data; this script
replaces the hand-curated file the app started with.

Sources (all from save-pal's data/json):
  fast_travel_points.json + l10n/en/fast_travel_points.json -> type "fast_travel"
  bosses.json (spawn_type "alpha" or "boss")                -> type "alpha_pal"
  bosses.json (spawn_type "predator")                       -> type "predator_pal"
  dungeons.json                                             -> type "dungeon"

Every object is tagged with the map layer it belongs to (data/json/map_layers.json);
pal ids are resolved to pals.json keys with backend/common/pal_ids.py, the same
rule the app uses for save characters.

Usage:
  python3 scripts/datagen/generate_map_objects.py --tag v1.4.2
  python3 scripts/datagen/generate_map_objects.py --src /path/to/save-pal/data/json
"""

import argparse
import collections
import json
import sys
from pathlib import Path

from savepal import DATA_JSON, add_source_args, source_dir
from backend.common.pal_ids import SpeciesIndex
from backend.common.map_layers import load_map_layers, which_map

OUT_PATH = DATA_JSON / 'map_objects.json'


def load(src: Path, name: str):
    with open(src / name, encoding='utf-8') as f:
        d = json.load(f)
    return d.get('values') or d


def as_items(v):
    """save-pal files are sometimes dicts keyed by id, sometimes lists."""
    return list(v.items()) if isinstance(v, dict) else list(enumerate(v))


def build(src: Path, layers):
    objects = []

    # --- fast travel -----------------------------------------------------
    ftp = load(src, 'fast_travel_points.json')
    ftp_names = load(src / 'l10n' / 'en', 'fast_travel_points.json')
    for key, p in as_items(ftp):
        name = (ftp_names.get(key) or {}).get('localized_name') if isinstance(ftp_names, dict) else None
        objects.append({
            'x': p['x'], 'y': p['y'],
            'type': 'fast_travel',
            'localized_name': name or p.get('id') or str(key),
            'map': which_map(layers, p['x'], p['y']),
        })

    # --- bosses: alpha + predator ----------------------------------------
    species = SpeciesIndex(load(src, 'pals.json').keys())
    unresolved, skipped = [], 0
    for _, b in as_items(load(src, 'bosses.json')):
        kind = b.get('spawn_type')
        # Upstream splits what this app shows as "Alpha Pals" across two spawn
        # types: 'alpha' (field alphas) and 'boss' (notable named bosses -- Ronin,
        # PoseidonOrca, CaptainPenguin...). 'bounty' targets are not placed markers.
        if kind == 'boss':
            kind = 'alpha'
        if kind not in ('alpha', 'predator'):
            continue
        # Most entries carry the species in character_id, BOSS_-prefixed.
        # Predators leave character_id empty and put the species in "pal".
        cid = b.get('character_id') or b.get('pal') or ''
        if not cid or cid == 'None':
            skipped += 1          # human NPC spawns: no species, no marker
            continue
        pal_id = species.resolve(cid)
        if pal_id is None:
            unresolved.append(cid)
            pal_id = cid
        entry = {'type': f'{kind}_pal', 'pal': pal_id, 'x': b['x'], 'y': b['y'],
                 'map': which_map(layers, b['x'], b['y'])}
        if kind == 'alpha' and b.get('level') is not None:
            entry['level'] = b['level']
        objects.append(entry)

    # --- dungeons ---------------------------------------------------------
    for _, d in as_items(load(src, 'dungeons.json')):
        objects.append({'x': d['x'], 'y': d['y'], 'type': 'dungeon',
                        'map': which_map(layers, d['x'], d['y'])})

    return objects, unresolved, skipped


def main():
    ap = argparse.ArgumentParser()
    add_source_args(ap)
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = source_dir(args)
    layers = load_map_layers(DATA_JSON / 'map_layers.json')
    objects, unresolved, skipped = build(src, layers)

    new_counts = collections.Counter(o['type'] for o in objects)
    old_counts = collections.Counter()
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old_counts = collections.Counter(o['type'] for o in json.load(f))

    print(f'\n{"type":<16} {"current":>8} {"new":>8} {"delta":>8}')
    for t in sorted(set(old_counts) | set(new_counts)):
        o, n = old_counts.get(t, 0), new_counts.get(t, 0)
        print(f'{t:<16} {o:>8} {n:>8} {n - o:>+8}')
    print(f'{"TOTAL":<16} {sum(old_counts.values()):>8} {len(objects):>8} '
          f'{len(objects) - sum(old_counts.values()):>+8}')

    map_counts = collections.Counter(o['map'] for o in objects)
    print('\nby map layer: ' + ', '.join(f'{k}={v}' for k, v in sorted(map_counts.items())))
    if skipped:
        print(f'skipped {skipped} boss spawn(s) with no species (human NPCs)')
    if unresolved:
        print(f'\nWARNING: {len(unresolved)} boss character_id(s) not in pals.json: '
              f'{", ".join(sorted(set(unresolved)))}')
        print('  (kept with the raw id; the UI falls back to showing the id)')

    if args.dry_run:
        print('\n--dry-run: not written')
        return 0
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(objects, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'\nWrote {len(objects)} objects -> {OUT_PATH.relative_to(DATA_JSON.parents[1])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
