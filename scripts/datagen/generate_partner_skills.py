#!/usr/bin/env python3
"""
Generate data/json/partner_skills.json -- every species' partner skill, rendered
for each of its five levels.

palworld-save-pal does not carry partner skills, so this reads the client pak
with the CUE4Parse extractor (scripts/datagen/extractor). The text lives in the
English localisation tables and the numbers in the parameter tables; see
backend/common/partner_skills.py for how they fit together. Output:

  {"species": {"<pals.json id>": {"name": "Wriggling Weasel",
                                   "levels": ["...Lv1 text...", ..., "...Lv5 text..."]}}}

Descriptions are plain text with '\n' line breaks; inline references (element
names, item names, buildings, other pals) are resolved to words at generation
time from data/json/l10n, so the app never parses game markup.

Usage:
  python3 scripts/datagen/generate_partner_skills.py            # extract from the pak
  python3 scripts/datagen/generate_partner_skills.py --src DIR  # DIR has the six dumps
  python3 scripts/datagen/generate_partner_skills.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from savepal import ROOT as REPO, DATA_JSON
from backend.common.pal_ids import SpeciesIndex, is_boss_id
from backend.common.partner_skills import build_partner_skills, text_of

OUT_PATH = DATA_JSON / 'partner_skills.json'
EXTRACTOR = REPO / 'scripts' / 'datagen' / 'extractor' / 'bin' / 'Release' / 'net8.0' / 'pal-extract'
CACHE = REPO / 'scripts' / 'datagen' / '.cache' / 'partner_skills'
PAK_DIR = Path(os.environ.get('PALWORLD_PAK_DIR', str(Path.home() / '.gamedata' / 'palworld-pak-data')))
USMAP = os.environ.get('PALWORLD_USMAP', '')

EN = 'Pal/Content/L10N/en/Pal/DataTable/Text/'
TABLES = {
    'names.json': EN + 'DT_SkillNameText_Common',
    'templates.json': EN + 'DT_PalFirstActivatedInfoText',
    'appends.json': EN + 'DT_PartnerSkillAppendText',
    'ui.json': EN + 'DT_UI_Common_Text_Common',
    'params.json': 'Pal/Content/Pal/DataTable/PassiveSkill/DT_PartnerSkillParameter',
    'passives.json': 'Pal/Content/Pal/DataTable/PassiveSkill/DT_PassiveSkill_Main',
}
NAME_PREFIX = 'PARTNERSKILL_'
TEMPLATE_PREFIX = 'PAL_FIRST_SPAWN_DESC_'


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
    return rows


def _l10n(name: str) -> Dict[str, Dict]:
    p = DATA_JSON / 'l10n' / 'en' / f'{name}.json'
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _named(table: Dict[str, Dict], key_fn=lambda k: k):
    lower = {key_fn(k).lower(): v for k, v in table.items()}

    def lookup(key: str) -> Optional[str]:
        row = table.get(key_fn(key)) or lower.get(key_fn(key).lower()) or {}
        return row.get('localized_name') or None
    return lookup


def build(src: Path, species: SpeciesIndex):
    names = {k[len(NAME_PREFIX):]: text_of(v) for k, v in load_rows(src, 'names.json').items() if k.startswith(NAME_PREFIX)}
    templates = {k[len(TEMPLATE_PREFIX):]: text_of(v) for k, v in load_rows(src, 'templates.json').items()
                 if k.startswith(TEMPLATE_PREFIX)}
    ui = {k: text_of(v) for k, v in load_rows(src, 'ui.json').items()}
    appends = {k: text_of(v) for k, v in load_rows(src, 'appends.json').items()}
    params = load_rows(src, 'params.json')
    passives = load_rows(src, 'passives.json')

    pal_names = _l10n('pals')
    lookups = {
        'uiCommon': lambda k: ui.get(k) or None,
        'characterName': lambda k: (pal_names.get(species.resolve(k) or k) or {}).get('localized_name'),
        'itemName': _named(_l10n('items')),
        'mapObjectName': _named(_l10n('buildings')),
        'activeSkillName': _named(_l10n('active_skills'), lambda k: k if k.startswith('EPalWazaID::') else f'EPalWazaID::{k}'),
    }

    def resolve(pak_id: str) -> Optional[str]:
        if is_boss_id(pak_id):
            return None
        return species.resolve(pak_id, trim_variants=False)

    return build_partner_skills(names, templates, params, passives, appends, lookups, resolve)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, help='dir with the six table dumps (skips the extractor)')
    ap.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = ap.parse_args()

    src = args.src or CACHE
    if not args.src:
        extract(src)

    with open(DATA_JSON / 'pals.json', encoding='utf-8') as f:
        pals = json.load(f)
    species = SpeciesIndex(pals.keys())
    result = build(src, species)
    out, rep = result['species'], result['report']

    print(f'\n{len(out)} species with a partner skill')
    if rep['unresolved']:
        print(f'  {len(rep["unresolved"])} pak ids not in pals.json (variants that never spawn owned): '
              + ', '.join(rep['unresolved'][:8]) + (' ...' if len(rep['unresolved']) > 8 else ''))
    for key, label in (('no_name', 'species without a skill name'), ('leftover_markup', 'species with unresolved markup')):
        if rep[key]:
            print(f'  WARNING {len(rep[key])} {label}: ' + ', '.join(rep[key][:8]))
    if rep['unfilled']:
        print(f'  WARNING {len(rep["unfilled"])} species with unfilled placeholders: '
              + ', '.join(f'{k} {v}' for k, v in list(rep['unfilled'].items())[:6]))

    if OUT_PATH.exists():
        with open(OUT_PATH, encoding='utf-8') as f:
            old = (json.load(f).get('species') or {})
        gained, lost = sorted(set(out) - set(old)), sorted(set(old) - set(out))
        changed = [k for k in out if k in old and old[k] != out[k]]
        print(f'vs committed: {len(old)} -> {len(out)} species; +{len(gained)} / -{len(lost)}; {len(changed)} changed')
        if lost:
            print('  LOST: ' + ', '.join(lost))

    sample = out.get('CatMage') or next(iter(out.values()), None)
    if sample:
        print(f'\nsample -- {sample["name"]}, Lv1:\n  ' + sample['levels'][0].replace('\n', '\n  '))

    if args.dry_run:
        print('\n(dry run: nothing written)')
        return
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump({'species': out}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'\nwrote {OUT_PATH.relative_to(REPO)}')


if __name__ == '__main__':
    main()
