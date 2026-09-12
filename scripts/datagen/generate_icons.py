#!/usr/bin/env python3
"""
Regenerate palworld-lens icon assets (frontend/public/img/*.webp) from the game pak.

Flow:
  1. Collect every distinct `icon` value referenced by data/json/*.json.
  2. Diff against the webp we already ship → the set of MISSING icons.
  3. (--extract) run the CUE4Parse extractor to decode the missing icons to raw
     RGBA, then encode each to <icon>.webp in frontend/public/img/.

Report-only by default (safe): prints needed/existing/missing counts and writes the
missing list. Pass --extract to actually pull + convert. Pass --all to (re)generate
every referenced icon, ignoring what already exists.

Env:
  PALWORLD_PAK_DIR  dir containing Pal-Windows.pak (default ~/.gamedata/palworld-pak-data)
  PALWORLD_USMAP    path to Palworld.usmap (required for --extract)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from savepal import ROOT as REPO, DATA_JSON, IMG_DIR
from backend.common import pal_icons

EXTRACTOR = REPO / "scripts" / "datagen" / "extractor" / "bin" / "Release" / "net8.0" / "pal-extract"

PAK_DIR = Path(os.environ.get("PALWORLD_PAK_DIR", str(Path.home() / ".gamedata" / "palworld-pak-data")))
USMAP = os.environ.get("PALWORLD_USMAP", "")


def collect_derived_pal_icons() -> set[str]:
    """Icon names the app DERIVES from pal ids, which the `icon` field never covers.

    The pals tab, the pal modal and the map all build the file name from the
    character_id (backend/common/pal_icons.py) and ignore the `icon` field --
    save-pal sets it to a placeholder (t_commonhuman_icon_normal) for most new
    pals, so keying extraction on `icon` alone missed every new 1.0 species
    (Clovee, Lapiron, Dupin, ... 25 of them, found 2026-09-11) even after the
    map-only version of this pass had already been added the same day.

    For every pal in pals.json plus every pal placed on the map we request each
    fallback candidate; the extractor skips names that aren't in the pak, so
    over-requesting costs nothing. Pals that already have any candidate on disk
    are not re-requested.
    """
    needed: set[str] = set()
    existing = existing_webp()

    ids: set[str] = set()
    pj = DATA_JSON / "pals.json"
    if pj.exists():
        for cid, row in json.loads(pj.read_text()).items():
            if isinstance(row, dict) and row.get("is_pal") and not row.get("disabled"):
                ids.add(cid)
    mo = DATA_JSON / "map_objects.json"
    if mo.exists():
        try:
            for o in json.loads(mo.read_text()):
                pid = o.get("pal")
                if isinstance(pid, str) and pid.strip():
                    ids.add(pid.strip())
        except Exception as e:
            print(f"  warn: could not read map_objects.json: {e}")

    for cid in ids:
        cands = pal_icons.icon_candidates(cid)
        # Always ask for the exact texture: a variant with its own icon (Petallia
        # Ignis = flowerdoll_fire) must not be left showing the base species just
        # because the base icon happened to be on disk already.
        if f"t_{cands[0]}_icon_normal" not in existing and cands[0] not in existing:
            needed.add(f"t_{cands[0]}_icon_normal")
        # Only fan out to the fallbacks if nothing in the chain exists yet.
        if not any(f"t_{c}_icon_normal" in existing or c in existing for c in cands):
            needed.update(f"t_{c}_icon_normal" for c in cands)
    return needed


def collect_needed() -> set[str]:
    """Every distinct `icon` string across the top-level data/json files (lowercased)."""
    needed: set[str] = set()
    for jf in sorted(DATA_JSON.glob("*.json")):
        try:
            data = json.loads(jf.read_text())
        except Exception as e:
            print(f"  warn: could not read {jf.name}: {e}")
            continue
        entries = data.values() if isinstance(data, dict) else data
        for entry in entries:
            if isinstance(entry, dict):
                ic = entry.get("icon")
                if isinstance(ic, str) and ic.strip():
                    needed.add(ic.strip().lower())
    return needed


def existing_webp() -> set[str]:
    return {p.stem.lower() for p in IMG_DIR.glob("*.webp")}


def convert_rgba_dir(rgba_dir: Path) -> int:
    from PIL import Image
    n = 0
    for meta in rgba_dir.glob("*.json"):
        stem = meta.stem
        rgba = rgba_dir / f"{stem}.rgba"
        if not rgba.exists():
            continue
        m = json.loads(meta.read_text())
        w, h = m["width"], m["height"]
        data = rgba.read_bytes()
        if len(data) < w * h * 4:
            print(f"  SKIP {stem}: short data {len(data)} < {w*h*4}")
            continue
        img = Image.frombytes("RGBA", (w, h), data[: w * h * 4], "raw", "RGBA")
        img.save(IMG_DIR / f"{stem}.webp", "WEBP", lossless=True)
        n += 1
    return n


def main() -> int:
    extract = "--extract" in sys.argv
    do_all = "--all" in sys.argv

    needed = collect_needed()
    existing = existing_webp()

    derived = collect_derived_pal_icons()
    new_from_derived = derived - needed
    needed |= derived
    # Must come AFTER the merge -- it used to be computed before it, so the derived
    # names were counted in the report but never written to the extract list.
    missing = sorted(needed if do_all else (needed - existing))
    print(f"needed icons (distinct, from data/json): {len(needed)}"
          f"  [{len(derived)} pal-id-derived, {len(new_from_derived)} of them only reachable that way]")
    print(f"already shipped (webp):                  {len(existing)}")
    print(f"referenced but MISSING webp:             {len(needed - existing)}")
    print(f"shipped but no longer referenced:        {len(existing - needed)}")
    print(f"to {'regenerate (all)' if do_all else 'extract (missing)'}:               {len(missing)}")

    out = REPO / "scripts" / "datagen" / ("icons_all.txt" if do_all else "icons_missing.txt")
    out.write_text("\n".join(missing) + ("\n" if missing else ""))
    print(f"wrote list → {out}")

    if not extract:
        print("\n(report-only; pass --extract to decode + convert)")
        return 0
    if not missing:
        print("nothing to extract.")
        return 0
    if not USMAP or not Path(USMAP).exists():
        print("ERROR: PALWORLD_USMAP not set / missing — required for extraction.", file=sys.stderr)
        return 1

    rgba_dir = REPO / "scripts" / "datagen" / "_rgba"
    rgba_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PALWORLD_PAK_DIR": str(PAK_DIR), "PALWORLD_USMAP": USMAP}
    print(f"\nextracting {len(missing)} icons via {EXTRACTOR.name} ...")
    r = subprocess.run([str(EXTRACTOR), "icons", str(out), str(rgba_dir)], env=env)
    if r.returncode != 0:
        print("extractor failed", file=sys.stderr)
        return r.returncode

    print("converting rgba → webp ...")
    n = convert_rgba_dir(rgba_dir)
    print(f"done: wrote {n} webp into {IMG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
