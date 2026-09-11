#!/usr/bin/env python3
"""
Generate data/json/map_objects.json from a palworld-save-pal release.

map_objects.json drives the static markers on the world map (fast-travel points,
alpha pals, predators, dungeons). It was originally hand-assembled -- see the
git history, e.g. "Add Whalaska to alpha pal location data" -- because upstream
didn't publish this data at the time. save-pal now ships it, so this script
replaces the manual curation.

Sources (all from save-pal's data/json):
  fast_travel_points.json + l10n/en/fast_travel_points.json -> type "fast_travel"
  bosses.json (spawn_type "alpha")                          -> type "alpha_pal"
  bosses.json (spawn_type "predator")                       -> type "predator_pal"
  dungeons.json                                             -> type "dungeon"

Usage:
  python3 scripts/datagen/generate_map_objects.py --tag v1.4.2
  python3 scripts/datagen/generate_map_objects.py --src /path/to/save-pal/data/json
"""

import argparse
import collections
import io
import re
import json
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = 'oMaN-Rod/palworld-save-pal'

# World rectangles each map texture covers, from the game's own DT_WorldMapUIData.
# Palworld 1.0 added the World Tree as a SECOND map layer with its own texture and
# its own bounds, so an object's coordinates alone don't say which map it belongs
# on -- we tag it here and let the frontend render per layer. Without this, Tree
# objects project outside the main texture and pile up past its top-left corner.
MAPS = {
    'MainMap': {'x': (-1099400.0, 349400.0), 'y': (-724400.0, 724400.0)},
    'Tree':    {'x': (347351.5, 689148.5),   'y': (-818197.0, -476400.0)},
}


def which_map(x, y):
    """Return the map layer an object belongs to (MainMap wins on overlap)."""
    for name in ('MainMap', 'Tree'):
        (x0, x1), (y0, y1) = MAPS[name]['x'], MAPS[name]['y']
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return 'MainMap'   # out of both: keep it addressable rather than dropping it
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = PROJECT_ROOT / 'data' / 'json' / 'map_objects.json'


def load(src: Path, name: str):
    with open(src / name, encoding='utf-8') as f:
        d = json.load(f)
    return d.get('values') or d


def as_items(v):
    """save-pal files are sometimes dicts keyed by id, sometimes lists."""
    return list(v.items()) if isinstance(v, dict) else list(enumerate(v))


def fetch_tag(tag: str) -> Path:
    url = f'https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz'
    print(f'Downloading {url} ...')
    with urllib.request.urlopen(url) as r:
        blob = r.read()
    tmp = Path(tempfile.mkdtemp(prefix='save-pal-'))
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        t.extractall(tmp)
    inner = next(tmp.glob('palworld-save-pal-*'))
    return inner / 'data' / 'json'


def build(src: Path):
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
            'map': which_map(p['x'], p['y']),
        })

    # --- bosses: alpha + predator ----------------------------------------
    pals = load(src, 'pals.json')
    bosses = load(src, 'bosses.json')
    unresolved = []
    skipped = 0
    for _, b in as_items(bosses):
        kind = b.get('spawn_type')
        # Upstream splits what this app shows as "Alpha Pals" across two spawn
        # types: 'alpha' (field alphas) and 'boss' (notable named bosses -- Ronin,
        # PoseidonOrca, CaptainPenguin...). The hand-curated file this replaced
        # treated both as alpha_pal, so taking only 'alpha' silently dropped 18
        # species. 'bounty' targets are deliberately excluded -- they're not
        # placed markers.
        if kind == 'boss':
            kind = 'alpha'
        if kind not in ('alpha', 'predator'):
            continue
        # Most entries carry the species in character_id, BOSS_-prefixed.
        # Predators leave character_id empty and put the species in "pal".
        cid = b.get('character_id') or b.get('pal') or ''
        if not cid or cid == 'None':
            # A handful of spawns carry no species (human NPCs). Emitting them
            # would create a marker with an unresolvable id -> no name and a
            # broken icon, so drop them.
            skipped += 1
            continue
        if cid in pals:
            pal_id = cid
        else:
            # Prefix casing is inconsistent upstream (BOSS_Horus_Water but
            # Boss_Anubis), so strip case-insensitively.
            stripped = re.sub(r'^boss_', '', cid, flags=re.IGNORECASE)
            pal_id = stripped if stripped in pals else cid
            if pal_id not in pals and '_' in stripped:
                # Some spawns use a variant id the pal list doesn't carry
                # (BOSS_HerculesBeetle_Ground -> HerculesBeetle). Trim trailing
                # segments until a known species is found, so the marker gets a
                # real name and a real icon instead of falling back to the raw id.
                parts = stripped.split('_')
                while len(parts) > 1:
                    parts.pop()
                    if '_'.join(parts) in pals:
                        pal_id = '_'.join(parts)
                        break
        if pal_id not in pals:
            unresolved.append(cid or '<empty>')
        entry = {'type': f'{kind}_pal', 'pal': pal_id, 'x': b['x'], 'y': b['y'],
                 'map': which_map(b['x'], b['y'])}
        if kind == 'alpha' and b.get('level') is not None:
            entry['level'] = b['level']
        objects.append(entry)

    # --- dungeons ---------------------------------------------------------
    for _, d in as_items(load(src, 'dungeons.json')):
        objects.append({'x': d['x'], 'y': d['y'], 'type': 'dungeon',
                        'map': which_map(d['x'], d['y'])})

    return objects, unresolved, skipped


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--tag', help='palworld-save-pal release tag to download, e.g. v1.4.2')
    g.add_argument('--src', type=Path, help='path to an existing save-pal data/json dir')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = fetch_tag(args.tag) if args.tag else args.src
    objects, unresolved, skipped = build(src)

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
    print(f'\nWrote {len(objects)} objects -> {OUT_PATH.relative_to(PROJECT_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
