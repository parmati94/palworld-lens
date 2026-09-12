"""Shared helpers for the datagen scripts: locating the repo, importing the
backend's pure modules, and fetching a palworld-save-pal release.

Releases are cached under scripts/datagen/.cache/<tag>/ (gitignored) so one
update.sh run downloads the tarball once, not once per script.
"""
from __future__ import annotations

import io
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = 'oMaN-Rod/palworld-save-pal'
ROOT = Path(__file__).resolve().parents[2]
DATA_JSON = ROOT / 'data' / 'json'
IMG_DIR = ROOT / 'frontend' / 'public' / 'img'
CACHE = Path(__file__).resolve().parent / '.cache'

# backend/common/* are pure python (no backend deps); make them importable.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def fetch_release(tag: str) -> Path:
    """Path to <release>/data/json for a save-pal tag, downloading once."""
    dest = CACHE / tag
    marker = dest / 'data' / 'json' / 'pals.json'
    if marker.exists():
        print(f'Using cached save-pal {tag} ({dest})')
        return marker.parent
    url = f'https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz'
    print(f'Downloading {url} ...')
    with urllib.request.urlopen(url) as r:
        blob = r.read()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        t.extractall(dest)
    inner = next(dest.glob('palworld-save-pal-*'))
    for child in inner.iterdir():
        shutil.move(str(child), dest / child.name)
    inner.rmdir()
    if not marker.exists():
        raise SystemExit(f'error: {tag} archive has no data/json/pals.json')
    return marker.parent


def add_source_args(ap):
    """--tag / --src on an argparse parser; resolve with source_dir(args)."""
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--tag', help='palworld-save-pal release tag, e.g. v1.4.2')
    g.add_argument('--src', type=Path, help='path to an existing save-pal data/json dir')


def source_dir(args) -> Path:
    src = fetch_release(args.tag) if args.tag else args.src
    if not (src / 'pals.json').exists():
        raise SystemExit(f'error: {src} does not look like a save-pal data/json dir')
    return src
