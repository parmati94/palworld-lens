#!/usr/bin/env python3
"""
Generate data/json/paldeck.json -- what a species drops and the skills it learns by level.

Two pak tables, read with the CUE4Parse extractor (scripts/datagen/extractor):

  DT_PalDropItem       per character id and level threshold: up to ten ItemIdN / RateN / minN / MaxN
                       (Level 0 = always; a Level 70 / 80 row is the whole table at that level, with
                       awakening materials and relics on top; BOSS_ rows are the alpha's own table)
  DT_WazaMasterLevel   per pal id: the active skill (EPalWazaID::X, the active_skills.json key) and
                       the level it is learned at

See backend/common/paldeck.py (build_paldeck_tables, drops_for, learnset_for) for how the
species modal reads them.

Usage:
  python3 scripts/datagen/generate_paldeck_tables.py            # extract from the pak
  python3 scripts/datagen/generate_paldeck_tables.py --src DIR  # DIR has drops.json + learn.json
  python3 scripts/datagen/generate_paldeck_tables.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.paldeck import MIN_DROP_SPECIES, MIN_LEARN_SPECIES, build_paldeck_tables

OUT_PATH = DATA_JSON / 'paldeck.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'paldeck'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')
TABLES = {
    'drops.json': 'Pal/Content/Pal/DataTable/Character/DT_PalDropItem',
    'learn.json': 'Pal/Content/Pal/DataTable/Waza/DT_WazaMasterLevel',
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

    doc = build_paldeck_tables(load_rows(src, 'drops.json'), load_rows(src, 'learn.json'))
    drops, learn = doc['drops'], doc['learn']
    print(f'\n{len(drops)} characters with drops, {len(learn)} pals with a learnset')
    if len(drops) < MIN_DROP_SPECIES or len(learn) < MIN_LEARN_SPECIES:
        print(f'WARNING: fewer rows than expected (drops >= {MIN_DROP_SPECIES}, learn >= {MIN_LEARN_SPECIES}) -- stale usmap?')
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = json.load(f)
        for key in ('drops', 'learn'):
            gained = sorted(set(doc[key]) - set(old.get(key) or {}))
            lost = sorted(set(old.get(key) or {}) - set(doc[key]))
            print(f'vs committed {key}: +{len(gained)} / -{len(lost)}' + (f'  LOST: {", ".join(lost[:8])}' if lost else ''))

    if args.dry_run:
        print('\n--dry-run: not written')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, separators=(',', ':'), sort_keys=True)
        f.write('\n')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
