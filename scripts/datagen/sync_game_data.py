#!/usr/bin/env python3
"""
Sync data/json from a palworld-save-pal release.

WHAT gets synced is defined once, in backend/common/game_tables.py (the same
registry the app loads from). Generated tables (map_objects, map_layers) are
never copied from upstream; only the `en` locale is shipped. Files present in
data/json that the registry doesn't list are reported as stray.

Usage:
  python3 scripts/datagen/sync_game_data.py --tag v1.4.2
  python3 scripts/datagen/sync_game_data.py --src /path/to/save-pal/data/json
  python3 scripts/datagen/sync_game_data.py --tag v1.4.2 --dry-run
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from savepal import DATA_JSON, add_source_args, source_dir
from backend.common.game_tables import TABLES, synced_tables, expected_files


def counts(path: Path):
    try:
        d = json.loads(path.read_text(encoding='utf-8'))
        return len(d.get('values') or d) if isinstance(d, dict) else len(d)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    add_source_args(ap)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    src = source_dir(args)

    rows, changed, missing = [], 0, []
    for table in synced_tables():
        for local in table.paths(DATA_JSON):
            rel = local.relative_to(DATA_JSON)
            up = src / rel
            if not up.exists():
                rows.append((str(rel), counts(local) if local.exists() else None, None, 'NOT IN UPSTREAM'))
                if table.required:
                    missing.append(str(rel))
                continue
            before = counts(local) if local.exists() else None
            same = local.exists() and local.read_bytes() == up.read_bytes()
            if not same and not args.dry_run:
                local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(up, local)
            changed += 0 if same else 1
            rows.append((str(rel), before, counts(up), 'unchanged' if same else 'SYNCED'))
    for table in TABLES.values():
        if table.generated:
            for local in table.paths(DATA_JSON):
                rows.append((str(local.relative_to(DATA_JSON)), counts(local) if local.exists() else None, None, 'local (generated)'))

    print(f"\n{'file':<34} {'before':>8} {'after':>8}  status")
    print('-' * 72)
    for name, before, after, status in rows:
        print(f"{name:<34} {'-' if before is None else before:>8} {'-' if after is None else after:>8}  {status}")

    stray = sorted(p.relative_to(DATA_JSON) for p in DATA_JSON.rglob('*.json')) 
    stray = [p for p in stray if (DATA_JSON / p) not in expected_files(DATA_JSON)]
    if stray:
        print('\nstray files not in the registry (backend/common/game_tables.py) -- delete or register them:')
        for p in stray:
            print(f'  {p}')

    print(f'\n{changed} file(s) {"would be " if args.dry_run else ""}updated')
    if args.dry_run:
        print('--dry-run: nothing written')
    elif changed:
        print('\nNext: regenerate derived assets ->  bash scripts/datagen/update.sh --skip-sync')
    if missing:
        print(f'\nERROR: required table(s) missing upstream: {", ".join(missing)}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
