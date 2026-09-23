#!/usr/bin/env python3
"""
Generate data/json/activity.json -- the pak tables the base Activity view needs.

The save says what a base is doing (recipe ids, research ids, mission ids, work
amounts) but not what those ids are called or how long they take. Three tables
from the client pak fill that in, read with the CUE4Parse extractor
(scripts/datagen/extractor):

  DT_LabResearchDataTable + DT_LabResearchText     research name, work needed, category, prerequisite
  DT_CharacterTeamMissionDataTable + ...MissionText expedition name, duration, difficulty
  DT_ItemRecipeDataTable                            the few recipes whose id is not the product's id
  DT_BuildObjectDataTable + DT_MapObjectMasterDataTable
    -> each power building's blueprint (obj)        generator capacity (MaxEnergyStorage) + rate per worker

Recipe ids are the product's item id for 1376 of 1414 recipes, so only the
exceptions are shipped and the item table names the rest.

Usage:
  python3 scripts/datagen/generate_activity_tables.py            # extract from the pak
  python3 scripts/datagen/generate_activity_tables.py --src DIR  # DIR has the dumps (skips the extractor)
  python3 scripts/datagen/generate_activity_tables.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.activity import (MIN_GENERATORS, MIN_LAB_RESEARCH, MIN_MISSIONS, build_activity_tables,
                                     generator_ids)

OUT_PATH = DATA_JSON / 'activity.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'activity'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')

EN = 'Pal/Content/L10N/en/Pal/DataTable/Text/'
TABLES = {
    'lab.json': 'Pal/Content/Pal/DataTable/Lab/DT_LabResearchDataTable',
    'labtext.json': EN + 'DT_LabResearchText',
    'missions.json': 'Pal/Content/Pal/DataTable/CharacterTeamMission/DT_CharacterTeamMissionDataTable',
    'missiontext.json': EN + 'DT_CharacterTeamMissionText',
    'recipes.json': 'DT_ItemRecipeDataTable',
    'buildobjects.json': 'DT_BuildObjectDataTable',
    'master.json': 'Pal/Content/Pal/DataTable/MapObject/DT_MapObjectMasterDataTable',
}
BLUEPRINTS = 'blueprints'     # <src>/blueprints/<build object id>.json, one obj dump per power building


def blueprint_asset(master_row: dict) -> str | None:
    """'/Game/Pal/Blueprint/.../BP_X.BP_X_C' -> 'Pal/Content/Pal/Blueprint/.../BP_X' for the extractor."""
    path = ((master_row or {}).get('BlueprintClassSoft') or {}).get('AssetPathName') or ''
    if not path.startswith('/Game/'):
        return None
    return 'Pal/Content/' + path[len('/Game/'):].split('.')[0]


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
    master = load_rows(src, 'master.json')
    (src / BLUEPRINTS).mkdir(exist_ok=True)
    for oid in generator_ids(load_rows(src, 'buildobjects.json')):
        asset = blueprint_asset(master.get(oid))
        if not asset:
            print(f'  {oid}: no blueprint in the master table, skipped')
            continue
        print(f'extracting {asset.rsplit("/", 1)[-1]} ...')
        r = subprocess.run([str(EXTRACTOR), 'obj', asset, str(src / BLUEPRINTS / f'{oid}.json')], env=env,
                           stdout=subprocess.DEVNULL)
        if r.returncode != 0:
            raise SystemExit(f'error: extractor failed on {asset}')


def load_rows(src: Path, fname: str) -> dict:
    with open(src / fname, encoding='utf-8') as f:
        data = json.load(f)
    rows = data.get('Rows') if isinstance(data, dict) else None
    if not rows:
        raise SystemExit(f'error: {src / fname} has no Rows')
    return dict(rows)


def load_blueprints(src: Path) -> dict:
    out = {}
    for p in sorted((src / BLUEPRINTS).glob('*.json')) if (src / BLUEPRINTS).is_dir() else []:
        with open(p, encoding='utf-8') as f:
            out[p.stem] = json.load(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with the table dumps + blueprints/ (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = args.src or CACHE
    if not args.src:
        extract(src)

    doc = build_activity_tables(load_rows(src, 'lab.json'), load_rows(src, 'labtext.json'),
                                load_rows(src, 'missions.json'), load_rows(src, 'missiontext.json'),
                                load_rows(src, 'recipes.json'), load_blueprints(src))
    lab, missions, recipes, generators = doc['lab'], doc['expeditions'], doc['recipe_products'], doc['generators']
    unnamed = [k for k, v in lab.items() if not v.get('name')] + [k for k, v in missions.items() if not v.get('name')]
    print(f'\n{len(lab)} research entries, {len(missions)} expeditions, {len(recipes)} recipes whose id is not the product, '
          f'{len(generators)} power buildings')
    for oid, g in generators.items():
        print(f'  {oid}: capacity {g["capacity"]:,.0f}' + (f', {g["rate"]:g}/s per worker' if g.get('rate') else ''))
    if unnamed:
        print(f'WARNING: {len(unnamed)} entries without a name: ' + ', '.join(unnamed[:8]))
    if len(lab) < MIN_LAB_RESEARCH or len(missions) < MIN_MISSIONS or len(generators) < MIN_GENERATORS:
        print(f'WARNING: fewer rows than expected (lab >= {MIN_LAB_RESEARCH}, expeditions >= {MIN_MISSIONS}, '
              f'generators >= {MIN_GENERATORS}) -- stale usmap?')

    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = json.load(f)
        for key in ('lab', 'expeditions'):
            gained = sorted(set(doc[key]) - set(old.get(key) or {}))
            lost = sorted(set(old.get(key) or {}) - set(doc[key]))
            print(f'vs committed {key}: +{len(gained)} / -{len(lost)}' + (f'  LOST: {", ".join(lost[:8])}' if lost else ''))

    if args.dry_run:
        print('\n--dry-run: not written')
        return 0
    doc = {
        '_comment': 'Generated by scripts/datagen/generate_activity_tables.py from the game\'s '
                    'DT_LabResearchDataTable(+Text), DT_CharacterTeamMissionDataTable(+Text) and '
                    'DT_ItemRecipeDataTable, plus each power building\'s blueprint (MaxEnergyStorage). Names, '
                    'durations, work amounts and capacities for what the save says a base is doing. Do not edit by hand.',
        **doc,
    }
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'\nwrote {OUT_PATH.relative_to(REPO)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
