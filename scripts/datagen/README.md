# Data-generation pipeline

Regenerates the game-data assets palworld-lens ships when Palworld updates:

- **`data/json/`** — re-synced from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal)
  (`data/json/`, matched to a release tag). See [Updating game data](#updating-game-data).
- **`frontend/public/img/*.webp`** — pal/item/building/tech icons, extracted from the
  game pak with a CUE4Parse extractor (replaces a manual FModel export).

Output is committed to the repo, so end users never run this.

## One-time setup

```bash
# 1. .NET 8+ SDK (the extractor targets net8.0). User-local, no sudo:
curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0 --install-dir ~/.dotnet

# 2. Extractor native deps → gitignored vendor/ and runtime/:
cd scripts/datagen/extractor
./fetch-cue4parse.sh   # vendors CUE4Parse at FModel's pinned commit
./fetch-oodle.sh       # Oodle .so (CUE4Parse needs it to decompress pak chunks)

# 3. Python deps for the icon converter:
cd .. && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

## Inputs (per game update)

Put these where the tools look (override paths with env vars):

| Input | Default location | Notes |
|---|---|---|
| Client pak | `~/.gamedata/palworld-pak-data/Pal-Windows.pak` | **Client** `Pal-Windows.pak` from a Steam install — NOT the dedicated-server pak (its textures are stripped). Unencrypted → no AES key. |
| usmap | `PALWORLD_USMAP=/path/Palworld.usmap` | Palworld ships unversioned client properties, so CUE4Parse needs a usmap. A community usmap works (icons are the engine `UTexture2D` class): [PalworldModding/UsefulFiles](https://github.com/PalworldModding/UsefulFiles). |

Env vars: `PALWORLD_PAK_DIR` (dir containing the pak), `PALWORLD_USMAP` (usmap path).

## Updating game data

```bash
# 1. Re-sync data/json from a palworld-save-pal release (e.g. v0.17.4), preserving our
#    custom map_objects.json (alpha-pal / fast-travel locations) and en-only l10n.
#    (Manual copy for now; see git history for the last sync.)

# 2. Extract the icons the new data references but we don't ship yet:
cd scripts/datagen/extractor && dotnet build -c Release -m:1 Extractor.csproj
cd ..
PALWORLD_PAK_DIR=~/.gamedata/palworld-pak-data \
PALWORLD_USMAP=~/.gamedata/palworld-pak-data/Palworld.usmap \
  python3 generate_icons.py --extract        # report-only without --extract
```

`generate_icons.py` collects every `icon` referenced by `data/json/*.json`, diffs
against `frontend/public/img/*.webp`, and (with `--extract`) decodes the missing icons
via the extractor and writes them as webp. Review the `git diff`, then commit.

## Extractor (`pal-extract`)

CUE4Parse-based, targets Palworld (UE5.1, unencrypted paks). Commands:

| Command | Purpose |
|---|---|
| `smoke <needle>` | mount + list keys matching a substring (sanity check) |
| `list <needle> <out>` | dump all matching mount keys to a file |
| `pull <needle> <out>` | raw-copy matching files (uasset/uexp) — no usmap needed |
| `tex <needle> <out>` | decode first matching texture → `.rgba` + `.json` sidecar |
| `icons <listfile> <out>` | batch-decode a list of icon names → `.rgba` + `.json` |

The `.rgba` (raw RGBA pixels) + `.json` ({width,height,pixelFormat}) sidecars are
encoded to webp by `generate_icons.py` via PIL — we avoid SkiaSharp (its native lib
isn't on the build host).
