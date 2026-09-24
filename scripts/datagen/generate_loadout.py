#!/usr/bin/env python3
"""
Generate data/json/loadout.json -- what gear and food do to a player's stats.

The status screen shows stats after enhancements (Health 1900 >> 3550); the numbers
come from three pak tables, read with the CUE4Parse extractor (scripts/datagen/extractor):

  DT_ItemDataTable_Common   armour HPValue / PhysicalDefenseValue / ShieldValue + PassiveSkillName*
  DT_StatusEffectFood       a dish's buff (type, percent, seconds)
  DT_PalPlayerParameter     the player's base stats (the same at every level)

Usage:
  python3 scripts/datagen/generate_loadout.py            # extract from the pak
  python3 scripts/datagen/generate_loadout.py --src DIR  # DIR has the dumps (skips the extractor)
  python3 scripts/datagen/generate_loadout.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.loadout import MIN_FOOD, MIN_GEAR, build_loadout_tables

OUT_PATH = DATA_JSON / 'loadout.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'loadout'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')

TABLES = {
    'items.json': 'Pal/Content/Pal/DataTable/Item/DT_ItemDataTable_Common',
    'food.json': 'Pal/Content/Pal/DataTable/Item/DT_StatusEffectFood',
    'player.json': 'Pal/Content/Pal/DataTable/Character/DT_PalPlayerParameter',
}


def extract(src: Path) -> None:
    if not EXTRACTOR.exists():
        raise SystemExit(f'error: extractor not built: {EXTRACTOR} (see scripts/datagen/README.md)')
    if not PAK_DIR.is_dir() or not USMAP or not Path(USMAP).exists():
        raise SystemExit('error: PALWORLD_PAK_DIR / PALWORLD_USMAP missing -- required to read the pak')
    src.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PALWORLD_PAK_DIR': str(PAK_DIR), 'PALWORLD_USMAP': USMAP}
    for fname, table in TABLES.items():
        print(f'extracting {table.rsplit("/", 1)[-1]} ...')
        r = subprocess.run([str(EXTRACTOR), 'dt', table, str(src / fname)], env=env, stdout=subprocess.DEVNULL)
        if r.returncode != 0:
            raise SystemExit(f'error: extractor failed on {table}')


def load_rows(src: Path, fname: str) -> dict:
    with open(src / fname, encoding='utf-8') as f:
        data = json.load(f)
    rows = data.get('Rows') if isinstance(data, dict) else None
    if not rows:
        raise SystemExit(f'error: {src / fname} has no Rows')
    return dict(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with the table dumps (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = args.src or CACHE
    if not args.src:
        extract(src)

    doc = build_loadout_tables(load_rows(src, 'items.json'), load_rows(src, 'food.json'), load_rows(src, 'player.json'))
    gear, food, base = doc['gear'], doc['food'], doc['player_base']
    print(f'\n{len(gear)} items with a stat or passive, {len(food)} dishes with a buff, player base {base}')
    if len(gear) < MIN_GEAR or len(food) < MIN_FOOD or len(base) < 5:
        print(f'WARNING: fewer rows than expected (gear >= {MIN_GEAR}, food >= {MIN_FOOD}, base 5 stats) -- stale usmap?')
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = json.load(f)
        for key in ('gear', 'food'):
            gained = sorted(set(doc[key]) - set(old.get(key) or {}))
            lost = sorted(set(old.get(key) or {}) - set(doc[key]))
            print(f'vs committed {key}: +{len(gained)} / -{len(lost)}' + (f'  LOST: {", ".join(lost[:8])}' if lost else ''))

    if args.dry_run:
        print('\n--dry-run: not written')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
