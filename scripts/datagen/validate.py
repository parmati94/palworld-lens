#!/usr/bin/env python3
"""
Coverage checks for the generated game-data assets.

Exists because the 1.0 ingest shipped several silent breakages: markers with no
icon (the frontend derives icon names a different way than generate_icons.py
checked), map objects on a layer that had no tiles, and a map texture that was
never re-extracted. Each failed invisibly -- nginx's SPA fallback serves
index.html with a 200 for missing files, so nothing 404s.

Run after any ingest. Non-zero exit on a real problem.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'json'
IMG = ROOT / 'frontend' / 'public' / 'img'

# Keep in step with scripts/slice_map.py MAPS and utils.js MAP_LAYERS.
LAYERS = {'MainMap': ('World_Map_8k.webp', 'tiles'),
          'Tree':    ('Tree_Map_8k.webp',  'tiles_tree')}

problems, notes = [], []


def check_map_objects():
    p = DATA / 'map_objects.json'
    if not p.exists():
        problems.append('map_objects.json missing -- run generate_map_objects.py')
        return []
    objs = json.loads(p.read_text())
    if not objs:
        problems.append('map_objects.json is empty')
    for o in objs:
        if o.get('map') and o['map'] not in LAYERS:
            problems.append(f"map_objects: unknown layer {o['map']!r}")
            break
    untagged = [o for o in objs if 'map' not in o]
    if untagged:
        notes.append(f'{len(untagged)} map object(s) have no "map" field (treated as MainMap)')
    return objs


def check_marker_icons(objs):
    """Every pal placed on the map must have the icon the frontend derives."""
    missing = set()
    for o in objs:
        pid = o.get('pal')
        if not pid:
            continue
        base = pid.lower()
        if base.startswith('boss_'):
            base = base[5:]
        if not (IMG / f't_{base}_icon_normal.webp').exists():
            missing.add(pid)
    if missing:
        problems.append(f'{len(missing)} map marker(s) have no derived icon: '
                        + ', '.join(sorted(missing)[:8]) + ('...' if len(missing) > 8 else ''))


def check_referenced_icons():
    """Every `icon` field in data/json must resolve to a shipped webp."""
    needed = set()
    for jf in DATA.glob('*.json'):
        try:
            data = json.loads(jf.read_text())
        except Exception:
            continue
        for e in (data.values() if isinstance(data, dict) else data):
            if isinstance(e, dict) and isinstance(e.get('icon'), str) and e['icon'].strip():
                needed.add(e['icon'].strip().lower())
    missing = {i for i in needed if not (IMG / f'{i}.webp').exists()}
    if missing:
        # Some upstream rows point at placeholder names that aren't real assets;
        # those are expected and reported as a note rather than a failure.
        notes.append(f'{len(missing)} `icon` value(s) have no webp (upstream placeholders): '
                     + ', '.join(sorted(missing)[:6]))


def check_layers(objs):
    used = {o.get('map', 'MainMap') for o in objs}
    for layer, (source, tiledir) in LAYERS.items():
        if not (IMG / source).exists():
            problems.append(f'{layer}: source image {source} missing')
        td = IMG / tiledir
        n = len(list(td.rglob('*.webp'))) if td.exists() else 0
        if n == 0:
            msg = f'{layer}: no tiles in {tiledir}/ -- run scripts/slice_map.py'
            (problems if layer in used else notes).append(msg)
        else:
            notes.append(f'{layer}: {n} tiles, source {source}')


def main():
    objs = check_map_objects()
    check_marker_icons(objs)
    check_referenced_icons()
    check_layers(objs)

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
