# Data-generation pipeline

Regenerates the game-data assets palworld-lens ships when Palworld updates:

- **`data/json/`** — re-synced from [palworld-save-pal](https://github.com/oMaN-Rod/palworld-save-pal)
  (`data/json/`, matched to a release tag). See [Updating game data](#updating-game-data).
- **`frontend/public/img/*.webp`** — pal/item/building/tech icons, extracted from the
  game pak with a CUE4Parse extractor (replaces a manual FModel export).
- **`data/json/spawns.json`** — wild spawn zones per species, from the pak's
  `DT_PalSpawnerPlacement` + `DT_PalWildSpawner` tables via the same extractor
  (`generate_spawns.py`; `pal-extract dt <table> out.json` dumps any data table --
  pass a full pak path such as `Pal/Content/L10N/en/Pal/DataTable/Text/DT_SkillNameText_Common`
  to pin one localisation, a bare name takes the first match; `pal-extract obj <asset> out.json`
  dumps any other asset's exports, e.g. a blueprint's default values).
- **`data/json/pal_parameters.json`** -- per-species pak fields save-pal lacks, today the
  designated best job that the first condensing star raises (`generate_pal_parameters.py`).
- **`data/json/partner_skills.json`** -- every species' partner skill name and description
  rendered per condensing level, from the pak's skill text + parameter tables
  (`generate_partner_skills.py`; see `backend/common/partner_skills.py` for the table map).
- **`data/json/schematics.json`** -- what each schematic unlocks, from the pak's
  `DT_ItemRecipeDataTable` (UnlockItemID) and `DT_BuildObjectDataTable` (BlueprintItemID), so
  chests can draw the product instead of the game's one generic blueprint icon
  (`generate_schematics.py`; resolved at runtime by `backend/common/schematics.py`).
- **`data/json/activity.json`** -- what the base Activity view needs to name what the save says a
  base is doing: lab research names + work amounts (`DT_LabResearchDataTable` + text), expedition
  names + durations (`DT_CharacterTeamMissionDataTable` + text), the few recipe ids that are not
  the product's item id, and each power building's capacity (MaxEnergyStorage on its blueprint, found
  through `DT_MapObjectMasterDataTable`) (`generate_activity_tables.py`; read by `backend/common/activity.py`).
- **`data/json/loadout.json`** -- what gear and food do to a player's stats, so the player modal can
  show the status screen's enhanced values (Health 1900 >> 3550): armour HP / defense / shield and
  equip passives from `DT_ItemDataTable_Common`, dish buffs from `DT_StatusEffectFood`, the player's
  base row from `DT_PalPlayerParameter` (`generate_loadout.py`; applied by `backend/common/loadout.py`).

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
| Client pak | `~/.gamedata/palworld-pak-data/Pal-Windows.pak` | **Client** `Pal-Windows.pak` from a Steam install — NOT the dedicated-server pak (its textures are stripped). Unencrypted → no AES key. On Windows: `C:\Program Files (x86)\Steam\steamapps\common\Palworld\Pal\Content\Paks\Pal-Windows.pak` (swap the prefix for another Steam library drive). |
| usmap | `~/.gamedata/palworld-pak-data/Palworld.usmap` | Palworld ships unversioned client properties, so CUE4Parse needs a usmap. A community usmap works (icons are the engine `UTexture2D` class). Fetch it (see gotchas below):<br>`curl -sL https://raw.githubusercontent.com/PalworldModding/UsefulFiles/master/Mappings.usmap -o ~/.gamedata/palworld-pak-data/Palworld.usmap` |

Env vars: `PALWORLD_PAK_DIR` (dir containing the pak), `PALWORLD_USMAP` (usmap path).

### usmap gotchas

- The file is **`Mappings.usmap`** on branch **`master`** — not `Palworld.usmap`, not `main`.
  A URL with `main/` or the renamed path returns an HTML 404 page that saves as a ~269 KB
  "usmap" and fails much later with `ParserException: Usmap has invalid magic`.
- **Verify after downloading:** ~2.3 MB, and `xxd -l 8 Palworld.usmap` starts `c430`
  (magic `0x30C4`). All-`0a` bytes means you downloaded HTML.
- It is **not published per patch** — as of 2026-09-22 the newest dump is 1.0.5
  (2026-09-20). Fine for icons, since `UTexture2D` is an engine class whose properties
  don't shift between patches, but **data tables need a usmap at least as new as the
  game**: with a stale one a table whose row struct gained a column decodes to zero rows
  (`DT_PalMonsterParameter_Common` did this on 1.0.3). Run the extractor with
  `PAL_EXTRACT_VERBOSE=1` to see CUE4Parse's own error ("Unknown property with value N").
- Neither input is committed; both are disposable and get cleaned up. Expect to re-fetch
  the usmap whenever you re-run this pipeline.

Smoke-test the inputs before a full run (no `--extract` needed):

```bash
cd scripts/datagen/extractor
PALWORLD_PAK_DIR=~/.gamedata/palworld-pak-data \
PALWORLD_USMAP=~/.gamedata/palworld-pak-data/Palworld.usmap \
  dotnet bin/Release/net8.0/pal-extract.dll tex Alpaca_icon /tmp
```

Expect `usmap=<path>`, `tagged properties: ...`, `format=PF_DXT5`, and a decoded
`.rgba` — that exercises pak mount, Oodle, usmap parsing and texture decode in one go.

## Updating game data

One command does the whole ingest:

```bash
bash scripts/datagen/update.sh --tag v1.4.2      # a palworld-save-pal release tag
bash scripts/datagen/update.sh --tag v1.4.2 --dry-run
bash scripts/datagen/update.sh --skip-sync       # data/json already current
```

It runs, in dependency order:

| # | step | produces | from |
|---|------|----------|------|
| 1 | `sync_game_data.py` | `data/json/*.json` + `l10n/en` | a save-pal release |
| 2 | `generate_map_objects.py` | `data/json/map_objects.json` | that same release |
| 3 | `generate_icons.py --extract` | missing `frontend/public/img/*.webp` | the game pak |
| 4 | `slice_map.py` | `img/tiles/`, `img/tiles_tree/` | the committed map images |
| 5 | `validate.py` | coverage report | everything above |

Steps 3-4 need the pak + usmap (see [Inputs](#inputs-per-game-update));
`--skip-icons` / `--skip-tiles` run the rest without them. Each script also works
standalone, and all of them take `--dry-run`.

Only the map textures themselves aren't automated -- they change rarely, and
re-extracting a 40GB pak isn't worth doing on every run. When a patch redraws the
map:

```bash
cd scripts/datagen/extractor
dotnet bin/Release/net8.0/pal-extract.dll tex T_WorldMap.uasset /tmp/out   # MainMap
dotnet bin/Release/net8.0/pal-extract.dll tex T_TreeMap.uasset  /tmp/out   # World Tree
# then convert the raw .rgba to frontend/public/img/{World,Tree}_Map_8k.webp
```

### What validate.py catches

Silent breakages the 1.0 ingest actually shipped:

- **Pals with no icon.** The app never reads the `icon` field for pals. The pals
  tab, the pal modal and the map all derive `t_<stem>_icon_normal.webp` from the
  `character_id` -- and upstream sets `icon` to a placeholder that already exists
  (`t_commonhuman_icon_normal`) for most new species. `generate_icons.py`
  historically only extracted what `icon` named, so four map markers (July) and
  then every new 1.0 species in the pals tab (Clovee, Lapiron, Dupin, ... 25 of
  them, found 2026-09-11 after a map-only fix that same morning) shipped blank.

  The derivation now lives in ONE place, `backend/common/pal_icons.py`
  (`icon_candidates(character_id)`), used by the API (`image_id`,
  `image_candidates`), by `generate_icons.py` (what to pull) and by `validate.py`
  (every `is_pal` row must resolve to a webp on disk). Variant ids (`PREDATOR_`,
  `GYM_`, `RAID_`, `SUMMON_`, `POLICE_` prefixes; `_Oilrig`, `_Tower`, `_Otomo`,
  `_2` ... suffixes) mostly have no texture of their own, so the candidate list
  falls back token by token to the base species, and the frontend walks it on
  `<img>` error. Pals with no texture anywhere in the pak (the Moon Lord raid
  parts) are allow-listed in `icons_known_missing.txt`; the validator notes when
  an allow-listed id gains an icon after a patch.
- **Map objects on a layer with no tiles**, e.g. adding a layer and forgetting to
  slice it.
- **A missing map source image.**
- **A work type with no icon slot.** `OilExtraction` (1.0) wasn't in
  `WORK_ICON_MAPPING`, so every oil pal showed the Kindling icon (slot 00).
  Every work type in `pals.json` must now have a slot, a name and a webp.
- **A registered table that's missing, or a stray file nobody reads.**

`--skip-tiles` runs everything except the tile check (CI uses it; tiles are
built in the Docker image). `tests/test_game_data.py` covers the same ground
under pytest so a bad sync fails a pull request.

Note `nginx.conf` now returns a real 404 for missing `/img/*` assets. Previously
the SPA fallback served `index.html` with a 200, so a missing icon produced a
200KB HTML response, `onerror` never fired, and nothing appeared in the logs.

### Map layers

Palworld 1.0 added the World Tree as a **second map layer** with its own texture
and its own world bounds. The layers live in ONE file, `data/json/map_layers.json`
(name, label, source image, tile dir, world bounds), read by:

- `scripts/slice_map.py` (what to slice, where to)
- `scripts/datagen/generate_map_objects.py` (tagging each object with its layer)
- `scripts/datagen/validate.py` (tiles + sources exist for every layer)
- `backend/common/map_layers.py` -> `/api/game-data`
- `frontend/js/utils.js` -> `MAP_LAYERS` (imported at build time)

Adding a layer = one entry there plus its source image. Bounds come from the
game's own `DT_WorldMapUIData`; dump it with `pal-extract dt DT_WorldMapUIData
out.json`. Don't hand-fit projection constants -- the pre-1.0 code did, and every
marker broke when 1.0 redrew the texture.

### One rule per derivation

Everything that maps game data to something the app shows lives in a pure-python
module under `backend/common/`, and the datagen scripts, the app and the tests
import the SAME module:

| derivation | module | used by |
|---|---|---|
| which tables ship | `game_tables.py` | data_loader, sync_game_data, validate, tests |
| character_id -> species | `pal_ids.py` | pal builder, /api/map-objects, generate_map_objects, validate |
| character_id -> icon | `pal_icons.py` | PalInfo.image_candidates, /api/map-objects, generate_icons, validate |
| work type -> icon slot | `constants.py` | /api/game-data, validate, tests |
| map layer bounds | `map_layers.py` | generate_map_objects, validate, /api/game-data |

`backend/common/__init__.py` is deliberately empty so these import without the
backend's dependencies. `savepal.py` puts the repo root on `sys.path` for the
scripts, and caches downloaded save-pal releases under `.cache/<tag>/` so one
`update.sh` run downloads once.

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
