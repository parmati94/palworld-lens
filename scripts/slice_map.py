#!/usr/bin/env python3
"""
Slice each world map texture into XYZ tiles.

The layers (source image -> tile dir) come from data/json/map_layers.json,
the same file the frontend and the datagen scripts read. Sources are 8192px,
so z5 is native 1:1; zooms 0-5 are generated and the map overzooms past that.

Tiles are NOT committed -- they're derived from the source image and are
regenerated here (and at Docker build time). Run this once after a fresh clone
so the Vite dev server has tiles to serve:

    python3 scripts/slice_map.py
"""

import json
import os
import time
from multiprocessing import get_context
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SCRIPTS_DIR  = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
IMG_DIR      = PROJECT_ROOT / 'frontend' / 'public' / 'img'
LAYERS_JSON  = PROJECT_ROOT / 'data' / 'json' / 'map_layers.json'

TILE_PX       = 256
OUTPUT_DIR    = None             # set per-map by slice_one()
OUTPUT_ZOOMS  = range(0, 6)      # z5 = 8192/256 = 32 tiles = native
WEBP_QUALITY  = 90
WEBP_METHOD   = 4                # 0=fast .. 6=slowest; 4 is ~6's size, far faster

# Per-zoom scaled image, set in the parent before each pool is created; forked
# workers inherit it copy-on-write and only ever read from it.
_SCALED = None


def _write_column(args):
    """Crop and save every tile in one column (tx) of one zoom level."""
    zoom, tx, n = args
    col = OUTPUT_DIR / str(zoom) / str(tx)
    col.mkdir(parents=True, exist_ok=True)
    for ty in range(n):
        tile = _SCALED.crop((tx * TILE_PX, ty * TILE_PX,
                             (tx + 1) * TILE_PX, (ty + 1) * TILE_PX))
        tile.save(str(col / f'{ty}.webp'), 'WEBP',
                  quality=WEBP_QUALITY, method=WEBP_METHOD)
    return n


def slice_one(input_image, output_dir):
    global _SCALED, OUTPUT_DIR
    OUTPUT_DIR = output_dir

    if not input_image.exists():
        print(f"Error: source image not found: {input_image}")
        return 1

    print(f"Loading {input_image.name} ...")
    src = Image.open(input_image).convert('RGB')
    print(f"  {src.width}x{src.height}")

    ctx   = get_context('fork')
    nproc = os.cpu_count() or 4
    print(f"Slicing zooms {list(OUTPUT_ZOOMS)} -> {OUTPUT_DIR.name} "
          f"(WebP q{WEBP_QUALITY}, {nproc} workers)")

    # Walk high->low zoom so each level downsamples from the previous (2x larger)
    # one rather than from the full-res source -- a mip pyramid.
    t_all = time.time()
    prev = src
    for zoom in sorted(OUTPUT_ZOOMS, reverse=True):
        n  = 2 ** zoom
        px = n * TILE_PX

        t0 = time.time()
        if px == prev.width:
            _SCALED = prev                                   # native, no resample
            note = 'native 1:1'
        else:
            _SCALED = prev.resize((px, px), Image.LANCZOS)
            note = f'downsample {prev.width}->{px}'
        prev = _SCALED
        t_resize = time.time() - t0

        t1 = time.time()
        with ctx.Pool(nproc) as pool:
            counts = pool.map(_write_column, [(zoom, tx, n) for tx in range(n)])
        t_encode = time.time() - t1
        print(f"  z={zoom}: {sum(counts):>5,} tiles ({note})  "
              f"resize {t_resize:4.1f}s  encode {t_encode:4.1f}s")

    _SCALED = None
    total = sum(1 for _ in OUTPUT_DIR.rglob('*.webp'))
    mb    = sum(f.stat().st_size for f in OUTPUT_DIR.rglob('*.webp')) / 1e6
    print(f"  done in {time.time()-t_all:.1f}s: {total:,} tiles, {mb:.1f} MB\n")
    return 0


def slice_map():
    with open(LAYERS_JSON, encoding='utf-8') as f:
        layers = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    rc = 0
    for name, m in layers.items():
        print(f"== {name}")
        rc |= slice_one(IMG_DIR / m['source'], IMG_DIR / m['tiles'])
    return rc


if __name__ == "__main__":
    raise SystemExit(slice_map())
