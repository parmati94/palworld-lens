#!/usr/bin/env python3
"""
Sync data/json from a palworld-save-pal release.

This was the one manual step left in the ingest ("Manual copy for now" in the
README) -- it's why data/json sat on v0.17.4 for two months after Palworld 1.0.

Only the files this app actually ships are synced; save-pal publishes many more.
Two things are deliberately preserved:
  * map_objects.json -- generated separately by generate_map_objects.py
  * l10n -- en only; we don't ship the other locales

Usage:
  python3 scripts/datagen/sync_game_data.py --tag v1.4.2
  python3 scripts/datagen/sync_game_data.py --src /path/to/save-pal/data/json
  python3 scripts/datagen/sync_game_data.py --tag v1.4.2 --dry-run
"""

import argparse
import io
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = 'oMaN-Rod/palworld-save-pal'
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_JSON = PROJECT_ROOT / 'data' / 'json'

# Generated here, never copied from upstream (upstream has no equivalent file).
LOCAL_ONLY = {'map_objects.json'}


def fetch_tag(tag: str) -> Path:
    url = f'https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz'
    print(f'Downloading {url} ...')
    with urllib.request.urlopen(url) as r:
        blob = r.read()
    tmp = Path(tempfile.mkdtemp(prefix='save-pal-'))
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        t.extractall(tmp)
    return next(tmp.glob('palworld-save-pal-*')) / 'data' / 'json'


def counts(path: Path):
    try:
        d = json.loads(path.read_text(encoding='utf-8'))
        return len(d.get('values') or d)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--tag', help='save-pal release tag, e.g. v1.4.2')
    g.add_argument('--src', type=Path, help='existing save-pal data/json dir')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    src = fetch_tag(args.tag) if args.tag else args.src
    if not (src / 'pals.json').exists():
        print(f'error: {src} does not look like a save-pal data/json dir')
        return 1

    rows, changed = [], 0

    for local in sorted(DATA_JSON.glob('*.json')):
        if local.name in LOCAL_ONLY:
            rows.append((local.name, counts(local), None, 'local-only (generated)'))
            continue
        up = src / local.name
        if not up.exists():
            rows.append((local.name, counts(local), None, 'not in upstream - kept'))
            continue
        before, after = counts(local), counts(up)
        same = local.read_bytes() == up.read_bytes()
        if not same and not args.dry_run:
            shutil.copyfile(up, local)
        changed += 0 if same else 1
        rows.append((local.name, before, after, 'unchanged' if same else 'SYNCED'))

    # l10n: en only, and only files we already ship
    for local in sorted((DATA_JSON / 'l10n' / 'en').glob('*.json')):
        up = src / 'l10n' / 'en' / local.name
        if not up.exists():
            rows.append((f'l10n/en/{local.name}', counts(local), None, 'not in upstream - kept'))
            continue
        before, after = counts(local), counts(up)
        same = local.read_bytes() == up.read_bytes()
        if not same and not args.dry_run:
            shutil.copyfile(up, local)
        changed += 0 if same else 1
        rows.append((f'l10n/en/{local.name}', before, after, 'unchanged' if same else 'SYNCED'))

    print(f"\n{'file':<34} {'before':>8} {'after':>8}  status")
    print('-' * 72)
    for name, before, after, status in rows:
        b = '-' if before is None else before
        a = '-' if after is None else after
        print(f'{name:<34} {b:>8} {a:>8}  {status}')
    print(f'\n{changed} file(s) {"would be " if args.dry_run else ""}updated')
    if args.dry_run:
        print('--dry-run: nothing written')
    elif changed:
        print('\nNext: regenerate derived assets ->  bash scripts/datagen/update.sh --skip-sync')
    return 0


if __name__ == '__main__':
    sys.exit(main())
