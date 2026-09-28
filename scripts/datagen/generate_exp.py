#!/usr/bin/env python3
"""
Generate data/json/exp.json -- the capture bonus chain and the player level ladder.

Two pak tables, read with the CUE4Parse extractor (scripts/datagen/extractor):

  DT_PalCaptureBonusExpTable   BonusExp per running bonus-catch index (4999 rows on 1.0);
                               the save's RecordData.PalCaptureBonusExpTableIndex is the
                               player's position in it
  DT_PalExpTable               per level: TotalEXP (cumulative to reach it), NextEXP

See backend/common/exp_tables.py for how the app reads them (the Paldeck tab's
"what is the next catch worth" figures).

Usage:
  python3 scripts/datagen/generate_exp.py            # extract from the pak
  python3 scripts/datagen/generate_exp.py --src DIR  # DIR has bonus.json + levels.json (skips the extractor)
  python3 scripts/datagen/generate_exp.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.exp_tables import MIN_BONUS_ROWS, MIN_LEVELS, build_exp_tables

OUT_PATH = DATA_JSON / 'exp.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'exp'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')
TABLES = {
    'bonus.json': 'Pal/Content/Pal/DataTable/Exp/DT_PalCaptureBonusExpTable',
    'levels.json': 'Pal/Content/Pal/DataTable/Exp/DT_PalExpTable',
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

    doc = build_exp_tables(load_rows(src, 'bonus.json'), load_rows(src, 'levels.json'))
    chain, levels = doc['capture_bonus'], doc['levels']
    print(f'\n{len(chain)} bonus rows (first {chain[:3]}, last {chain[-1]}), {len(levels)} levels')
    if len(chain) < MIN_BONUS_ROWS or len(levels) < MIN_LEVELS:
        print(f'WARNING: fewer rows than expected (bonus >= {MIN_BONUS_ROWS}, levels >= {MIN_LEVELS}) -- stale usmap?')
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = json.load(f)
        print(f'vs committed: bonus rows {len(old.get("capture_bonus") or [])} -> {len(chain)}, '
              f'levels {len(old.get("levels") or {})} -> {len(levels)}')

    if args.dry_run:
        print('\n--dry-run: not written')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, separators=(',', ':'), sort_keys=True)
        f.write('\n')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
