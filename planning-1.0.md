# Palworld 1.0 Compatibility — Planning

**Date:** 2026-07-10 (Palworld 1.0 launch day); updated 2026-07-11.

## Status at a glance

Three independent surfaces. 1.0 did **not** wipe saves — the format *evolved*, so
breakage is drift, not a rewrite.

| Surface | What | Status |
|---|---|---|
| **A. Parsing** (`palworld-save-tools`) | save decodes at all | ✅ **DONE** (2026-07-11) |
| **B. Static JSON** (`data/json/`) | pal/item/skill names & stats | ⏳ **TODO** — re-sync from palworld-save-pal v0.17.4 |
| **C. Icon images** (`frontend/public/img/`) | pal/item/building icons | ⏳ **TODO** — extract from local pak |

**What we need to finish 1.0 (short version):**
1. **B:** re-sync `data/json/` from palworld-save-pal `v0.17.4`, reconciling any schema
   drift our `data_loader.py` reads.
2. **C:** build a small CUE4Parse extractor (ported from satisfactory-lens) to pull the
   new/changed icon textures from the **local Palworld pak** → PNG → webp. Inputs are
   already on this host and the pak is **unencrypted** (no AES key, no usmap needed for
   raw texture extraction — see Surface C).
3. Then verify end-to-end in the UI, add a repeatable sync/extract doc, ship.

---

## Our exposure — three independent surfaces

### A. Save parsing (the `palworld-save-tools` library) — ✅ DONE (2026-07-11)

- We depend on the **oMaN-Rod fork**, `@main`. CI now installs it in a **cache-busted
  Dockerfile layer** so every build re-resolves `@main` (no manual hash bumps);
  `workflow_dispatch` gives an on-demand rebuild + a `SAVETOOLS_REF` override to freeze
  a ref. See `Dockerfile` + `.github/workflows/docker-publish.yml`.
- **The 1.0 blockers (both fixed upstream 2026-07-11):**
  - `PalMapObjectLampModel` trailing bytes grew 4→12 → hard "EOF not reached" crash.
    Fixed by `c5805b2a4`. (We filed [issue #5](https://github.com/oMaN-Rod/palworld-save-tools/issues/5).)
  - `ColorSetting` map-object *module* also gained bytes → same crash class.
    Fixed by `fd6bd52d6`.
  - Confirmed these were the ONLY two gaps for our save via a tolerant read-only parse
    (23 lamps + 23 ColorSetting modules, nothing else left over).
- **Verified fixed:** rebuilt on `0.23.2.dev81+g3d491dadc`, redeployed → live save
  parses cleanly (`✅ Save file loaded successfully`, no EOF error).

**Remaining check (cheap):** library-parses-clean ≠ our-app-works. Our extractors in
`backend/parser/extractors/` + schemas `backend/parser/schemas/*.yaml` read specific
fields; confirm players/pals/guilds/bases/structures all still populate in the UI (esp.
guild roles & breeding farms, which changed). Fold this into Phase 4 verification.

### B. Static game data (`data/json/`)

- **Provenance (answering the open question):** our `data/json/` tree was copied
  wholesale from **palworld-save-pal**'s `data/json/` at our initial commit
  (`41ed05a`). Layout + schema match exactly (`pals.json`, `items.json`,
  `active_skills.json`, `passive_skills.json`, `elements.json`, `buildings.json`,
  `technologies.json`, `lab_research.json`, `map_objects.json`, plus `l10n/en/…`).
- **There is no re-extraction script or documented pipeline in this repo.** The only
  attribution is one line in `README.md` Credits. Files were hand-copied once and
  have drifted since.
- **Good news:** palworld-save-pal **updated its own data for 1.0 today** (bumped to
  v0.17.4 with refreshed pals/items/skills/buildings/tech/missions JSON). So we can
  **re-sync from upstream** instead of extracting from game assets ourselves.

**What's likely stale after 1.0:**
- New pals (40+ reportedly added) → missing from `pals.json` / `l10n/en/pals.json`
  → unknown pals render as raw IDs, no stats/scaling, no localized names.
- New items → missing from `items.json`.
- New/changed active & passive skills → missing names/descriptions.
- New technologies/buildings (new region content, World Tree) → missing.
- Map objects (alpha pal locations, fast-travel) if any 1.0 map changes.

Our loader (`backend/parser/loaders/data_loader.py`) already degrades gracefully
(falls back to raw ID / logs a warning) rather than crashing — so stale data is a
*correctness/completeness* problem, not a hard failure.

### C. Static image assets (`frontend/public/img/`)

- **Provenance:** ~1,805 flat `.webp` files named after Unreal Engine `Texture2D`
  assets (`t_alpaca_icon_normal.webp`, `t_itemicon_accessory_at_1.webp`,
  `t_icon_buildobject_*.webp`). These were **extracted from the game paks with
  FModel** and converted UE PNG → webp. (Separately, `img/tiles/` is the sliced
  world map produced by `scripts/slice_map.py` — unrelated to icons.)
- **Wiring:** `data/json/pals.json` / `items.json` carry an `"icon"` field; the
  frontend loads `/img/{icon}.webp` from it.
- **The gap the JSON re-sync does NOT close:** re-syncing `data/json/` gives us the
  new icon *names* for free (just strings), but the new pals'/items' actual image
  *files* are not in the JSON. New `icon` values will point at `t_*.webp` files that
  don't exist → broken images in the UI.
- **Fix — no longer needs manual FModel.** The sibling project **`satisfactory-lens`**
  (`../satisfactory-lens/scripts/datagen/`) already built an automated **Linux
  CUE4Parse extractor** that retired the manual FModel export. Much of it is
  game-agnostic UE5 tooling we can port here (both games are UE5):
  - `extractor/Program.cs` — mounts `pak/utoc/ucas`; `raw` / `raw-list` commands copy
    texture `.uasset`+`.ubulk` bytes out.
  - `convert_icons.py` — decodes UE textures (DXT1/5, BC4/5/6/7, BGRA) → PNG. Pure
    UE format handling, nothing Satisfactory-specific.
  - `extract.sh` → generators → `validate.py` coverage-check pattern.

  **Palworld-specific changes needed (all small):**
  1. **AES key** — Satisfactory paks are unencrypted (submits all-zeros key:
     `SubmitKey(new FGuid(), new FAesKey(new byte[32]))`). Palworld paks are
     encrypted → one-line change to submit Palworld's real AES key (community
     publishes it each update).
  2. **Game version** — `EGame.GAME_UE5_6` → Palworld 1.0's UE version.
  3. **`Palworld.usmap`** — supply Palworld's mappings file (community-dumped)
     instead of `FactoryGame.usmap`; `TolerantUsmap.cs` is a Satisfactory quirk we
     likely won't need.
  4. **Skip `icon_textures.py`** — it scrapes icon paths from Satisfactory
     descriptors, but our `data/json` already carries the exact `icon` texture name
     per pal/item (from palworld-save-pal). Our extract list comes free from JSON.
  5. **Add a PNG→webp + lowercase-rename step** to match our flat `t_*.webp`
     convention (PIL, same approach as `scripts/slice_map.py`).

  This turns surface C from a manual Windows chore into a scripted Linux pipeline.
  Still needs the game paks + current AES key + a Palworld usmap as inputs.

---

## Proposed plan

### Phase 0 — Reproduce & triage (do first)
- [ ] Get a real 1.0 save file and load it locally.
- [ ] Rebuild the backend image forcing a fresh pull of `palworld-save-tools`
      (`pip install --no-cache-dir --force-reinstall` or bump the pin to a specific
      1.0 commit SHA for reproducibility). Confirm which failure mode we hit:
      library parse error vs. our extractor returning empty vs. stale JSON.
- [ ] Capture the actual traceback / empty sections. Split issues into surface A vs B.

### Phase 1 — Parsing library (surface A)
- [ ] Decide pin strategy: keep `@main` (auto-updates, less reproducible) vs. pin to
      a known-good 1.0 commit SHA (reproducible, manual bumps). Note palworld-save-pal
      v0.17.4 itself stays on `@main`, so our current pin already matches the shipped
      1.0 build. Still **recommend pinning to a SHA** for our own reproducibility now
      that the format is changing fast — capture the current `main` HEAD SHA.
- [ ] Re-run all extractors against a 1.0 save; verify players, pals, guilds, bases,
      structures, relationships all populate. Pay special attention to guild
      role/security data and breeding farms (the structures that changed today).
- [ ] Reconcile any renamed/moved fields in `backend/parser/extractors/*` and
      `backend/parser/schemas/*.yaml`.

### Phase 2 — Game data JSON (surface B)
- [ ] Re-sync `data/json/` from palworld-save-pal v0.17.4+ (`data/json/`). Diff
      against ours to see exactly what changed (new pals/items/skills/tech).
- [ ] Watch for schema drift — upstream may have added/renamed keys our loader reads.
      Check every `_load_*` method in `data_loader.py` still finds its fields.
- [ ] Upstream now ships extra files we don't use (missions, effigies,
      fast_travel_points). Decide whether 1.0 features make any of these worth adding.
- [ ] **Write down the provenance this time** (see Phase 3).

### Phase 2b — Image assets (surface C) — port the satisfactory-lens extractor
- [ ] After re-syncing JSON, diff every `icon` value referenced by `pals.json` /
      `items.json` (etc.) against files in `frontend/public/img/` → the exact list of
      **missing icons** to extract (avoids exporting everything).
- [ ] Port the CUE4Parse extractor from `../satisfactory-lens/scripts/datagen/`:
      copy `extractor/` + `convert_icons.py`; apply the Palworld deltas (AES key,
      `EGame` version, `Palworld.usmap`, drop `icon_textures.py`). See surface C above.
- [ ] Gather inputs: Palworld paks/utoc/ucas, current AES key, a Palworld usmap.
- [ ] Run extractor `raw-list` over the missing-icon list → decode with
      `convert_icons.py` → PNG.
- [ ] Add PNG→webp + lowercase-rename step to match `t_*.webp`; drop into
      `frontend/public/img/`.
- [ ] Verify no broken images in the UI for new pals/items.

### Phase 3 — Documentation & repeatability (the actual gap)
- [ ] Add `data/json/README.md` (or a `docs/` note) recording: source =
      palworld-save-pal `data/json/`, which version we synced from, and the date.
- [ ] Add a small sync script (`scripts/sync_game_data.py` or a Makefile target) that
      pulls the upstream `data/json/` at a pinned tag so future game updates are a
      one-command refresh instead of archaeology.
- [ ] Note the `palworld-save-tools` pin/bump procedure in the same doc.

### Phase 4 — Verify & ship
- [ ] Load 1.0 save end-to-end through the UI: players, pals (incl. new species),
      base monitor, guilds, map. Confirm new pals show names/stats, not raw IDs.
- [ ] Smoke-test remote SFTP/FTP loading path with a 1.0 save.
- [ ] Update `README.md` compatibility note (supports Palworld 1.0).

---

## Open questions / decisions to make
- Pin `palworld-save-tools` to a SHA, or stay on `@main`?
- Sync `data/json/` manually now, or build the sync script first and use it?
- Do we want any new 1.0 data domains (missions/effigies/World Tree content), or
  keep scope to parity with pre-1.0 features?

## Key references
- Parsing lib (ours): https://github.com/oMaN-Rod/palworld-save-tools (fork, `@main`)
- Data source (ours): https://github.com/oMaN-Rod/palworld-save-pal (`data/json/`)
- Both pushed 1.0 updates on 2026-07-10.
- Reusable icon extractor: `../satisfactory-lens/scripts/datagen/` (CUE4Parse Linux
  pipeline — `extractor/Program.cs`, `convert_icons.py`, `extract.sh`, `validate.py`).
