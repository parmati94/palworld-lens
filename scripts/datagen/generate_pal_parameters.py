#!/usr/bin/env python3
"""
Generate data/json/pal_parameters.json -- per-species fields from the pak's
DT_PalMonsterParameter that palworld-save-pal's pals.json does not carry.

Two sections:

  species   keyed by pals.json id
    best_work_suitability   the job the designers flag as the species' main one
                            (EPalWorkSuitability). Since 1.0 the first condensing
                            star raises this job (see backend/parser/utils/stats.py);
                            it is NOT always the highest-level job -- ranch pals
                            such as Serpent (Watering 3, Ranch 2) point at Ranch.

  stat_rows keyed by the pak row id, i.e. the save's CharacterID (BOSS_IceHorse,
            WingGolem_Oilrig, ...), one per pal row: the stat inputs of
            backend/parser/utils/stats.py -- hp / shot / melee / defense / craft
            scaling and the four friendship values. The boss and lucky variants
            have their OWN rows (Hp x1.2, a lower Friendship_HP), which is why a
            BOSS_ pal's stats are not the base species' with a multiplier.

Keys are pals.json ids (species) and pak row ids (stat_rows). Reading the table needs a usmap at least as new as the
game (1.0.5+ for the 91-column row); an older one decodes zero rows.

Usage:
  python3 scripts/datagen/generate_pal_parameters.py            # extract from the pak
  python3 scripts/datagen/generate_pal_parameters.py --src DIR  # DIR has monster.json
  python3 scripts/datagen/generate_pal_parameters.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON
from backend.common.pal_ids import SpeciesIndex

OUT_PATH = DATA_JSON / 'pal_parameters.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'pal_parameters'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')
TABLE = 'Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter_Common'
NONE = 'None'


def extract(src: Path) -> None:
    if not EXTRACTOR.exists():
        raise SystemExit(f'error: extractor not built: {EXTRACTOR} (see scripts/datagen/README.md)')
    if not PAK_DIR.is_dir() or not USMAP or not Path(USMAP).exists():
        raise SystemExit('error: PALWORLD_PAK_DIR / PALWORLD_USMAP missing -- required to read the pak')
    src.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PALWORLD_PAK_DIR': str(PAK_DIR), 'PALWORLD_USMAP': USMAP}
    print('extracting DT_PalMonsterParameter_Common ...')
    r = subprocess.run([str(EXTRACTOR), 'dt', TABLE, str(src / 'monster.json')], env=env, stdout=subprocess.DEVNULL)
    if r.returncode != 0:
        raise SystemExit('error: extractor failed')


def build(src: Path, species: SpeciesIndex):
    with open(src / 'monster.json', encoding='utf-8') as f:
        rows = (json.load(f).get('Rows') or {})
    if not rows:
        raise SystemExit('error: DT_PalMonsterParameter_Common decoded with no rows -- usmap older than the game? '
                         '(needs 1.0.5+; see scripts/datagen/README.md)')
    out, unresolved, stat_rows = {}, [], {}
    for pak_id, r in rows.items():
        if not r.get('IsPal'):
            continue
        stat_rows[pak_id] = {
            'hp': r.get('Hp', 0), 'shot': r.get('ShotAttack', 0), 'melee': r.get('MeleeAttack', 0),
            'defense': r.get('Defense', 0), 'craft': r.get('CraftSpeed', 0),
            'f_hp': r.get('Friendship_HP', 0.0), 'f_shot': r.get('Friendship_ShotAttack', 0.0),
            'f_defense': r.get('Friendship_Defense', 0.0), 'f_craft': r.get('Friendship_CraftSpeed', 0.0),
        }
        best = str(r.get('BestWorkSuitability') or NONE).split('::')[-1]
        # A few raid / quest rows flag a job the species does not have; skip those.
        if best == NONE or not r.get(f'WorkSuitability_{best}', 0):
            continue
        sid = species.resolve(pak_id, trim_variants=False)
        if sid is None:
            unresolved.append(pak_id)
            continue
        out.setdefault(sid, {})['best_work_suitability'] = best
    return dict(sorted(out.items())), unresolved, dict(sorted(stat_rows.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with monster.json (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    src = args.src or CACHE
    if not args.src:
        extract(src)
    with open(DATA_JSON / 'pals.json', encoding='utf-8') as f:
        pals = json.load(f)
    out, unresolved, stat_rows = build(src, SpeciesIndex(pals.keys()))
    print(f'\n{len(out)} species with a best job; {len(unresolved)} pak ids not in pals.json; {len(stat_rows)} stat rows')
    gap = [k for k, v in pals.items() if v.get('is_pal') and any((v.get('work_suitability') or {}).values()) and k not in out]
    if gap:
        print(f'  WARNING {len(gap)} working species without a best job: ' + ', '.join(gap[:8]))
    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = json.load(f).get('species') or {}
        changed = [k for k in out if k in old and old[k] != out[k]]
        print(f'vs committed: {len(old)} -> {len(out)} species, {len(changed)} changed')
    if args.dry_run:
        print('\n(dry run: nothing written)')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump({'species': out, 'stat_rows': stat_rows}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'\nwrote {OUT_PATH.relative_to(REPO)}')


if __name__ == '__main__':
    main()
