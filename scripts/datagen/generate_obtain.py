#!/usr/bin/env python3
"""
Generate data/json/obtain.json -- how you get the species nothing spawns in the wild.

Pak tables, read with the CUE4Parse extractor (scripts/datagen/extractor):

  DT_PalMonsterParameter_Common   RAID_<species> rows flagged IsRaidBoss -> raid (egg on kill)
  DT_SupplyIncident_Pal_*         what lands with a meteor event, per region, with levels -> meteor

Plus the hand-kept rows in backend/common/obtain.py (World Tree bosses, the story
catch, the one species that is not obtainable), which no table carries.

See backend/common/obtain.py for how the app reads it (the Paldeck's "how you get
one" and the Best workers catch list).

Usage:
  python3 scripts/datagen/generate_obtain.py            # extract from the pak
  python3 scripts/datagen/generate_obtain.py --src DIR  # DIR has monster.json + supply/*.json
  python3 scripts/datagen/generate_obtain.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.obtain import MIN_METEOR_SPECIES, MIN_RAID_SPECIES, SUPPLY_PREFIX, build_obtain

OUT_PATH = DATA_JSON / 'obtain.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'obtain'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')
MONSTER_TABLE = 'Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter_Common'
SUPPLY_DIR = 'Pal/Content/Pal/DataTable/Incident/SupplyIncident/'


def _run(args, env, capture=False):
    r = subprocess.run([str(EXTRACTOR), *args], env=env, stdout=subprocess.PIPE if capture else subprocess.DEVNULL, text=True)
    if r.returncode != 0:
        raise SystemExit(f'error: extractor failed on {" ".join(args)}')
    return r.stdout if capture else ''


def extract(src: Path) -> None:
    if not EXTRACTOR.exists():
        raise SystemExit(f'error: extractor not built: {EXTRACTOR} (see scripts/datagen/README.md)')
    if not PAK_DIR.is_dir() or not USMAP or not Path(USMAP).exists():
        raise SystemExit('error: PALWORLD_PAK_DIR / PALWORLD_USMAP missing -- required to read the pak')
    (src / 'supply').mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PALWORLD_PAK_DIR': str(PAK_DIR), 'PALWORLD_USMAP': USMAP}
    print('extracting DT_PalMonsterParameter_Common ...')
    _run(['dt', MONSTER_TABLE, str(src / 'monster.json')], env)
    listing = _run(['list', SUPPLY_DIR], env, capture=True)
    tables = sorted({line.strip()[:-len('.uasset')] for line in listing.splitlines()
                     if line.strip().endswith('.uasset') and Path(line.strip()).stem.startswith(SUPPLY_PREFIX)})
    print(f'extracting {len(tables)} supply incident tables ...')
    for table in tables:
        _run(['dt', table, str(src / 'supply' / f'{Path(table).stem}.json')], env)


def load_rows(path: Path) -> dict:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    rows = data.get('Rows') if isinstance(data, dict) else None
    if not rows:
        raise SystemExit(f'error: {path} has no Rows')
    return dict(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with the table dumps (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = args.src or CACHE
    if not args.src:
        extract(src)

    supply = {p.stem: load_rows(p) for p in sorted((src / 'supply').glob(f'{SUPPLY_PREFIX}*.json'))}
    with open(DATA_JSON / 'pals.json', encoding='utf-8') as f:
        known = list(json.load(f).keys())
    doc = build_obtain(load_rows(src / 'monster.json'), supply, known=known)
    species = doc['species']
    by_how = {}
    for sid, row in species.items():
        by_how.setdefault(row['how'], []).append(sid)
    print()
    for how, ids in sorted(by_how.items()):
        print(f'{how:<12} {len(ids):>3}  {", ".join(sorted(ids))}')
    if len(by_how.get('raid', [])) < MIN_RAID_SPECIES or len(by_how.get('meteor', [])) < MIN_METEOR_SPECIES:
        print(f'WARNING: fewer species than expected (raid >= {MIN_RAID_SPECIES}, meteor >= {MIN_METEOR_SPECIES}) -- stale usmap?')
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = (json.load(f).get('species') or {})
        gained, lost = sorted(set(species) - set(old)), sorted(set(old) - set(species))
        print(f'vs committed: +{len(gained)} / -{len(lost)}' + (f'  LOST: {", ".join(lost)}' if lost else ''))

    if args.dry_run:
        print('\n--dry-run: not written')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write('\n')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
