#!/usr/bin/env bash
#
# One command to re-ingest everything after a Palworld update.
#
# Runs the whole pipeline in dependency order and validates the result:
#   1. sync_game_data.py       data/json  <- a palworld-save-pal release
#   2. generate_map_objects.py map_objects.json <- that same release
#   3. generate_icons.py       missing icons <- the game pak  (needs pak + usmap)
#   3b. generate_spawns.py     spawns.json <- the pak's spawner tables (same inputs)
#   3c. generate_partner_skills.py partner_skills.json <- the pak's skill text tables (same inputs)
#   3d. generate_pal_parameters.py pal_parameters.json <- the pak's species table (same inputs)
#   3e. generate_schematics.py  schematics.json <- the pak's recipe + build-object tables (same inputs)
#   3f. generate_activity_tables.py activity.json <- lab research, expedition and recipe tables (same inputs)
#   3g. generate_loadout.py     loadout.json <- item stats, food buffs and player base tables (same inputs)
#   4. slice_map.py            map tiles <- the committed map images
#   5. validate.py             coverage checks
#
# Steps 3-4 need the extractor inputs; see README.md. Without them, pass
# --skip-icons / --skip-tiles and the rest still runs. The save-pal release is
# downloaded once and cached under .cache/<tag>/ for steps 1 and 2.
#
# Usage:
#   bash scripts/datagen/update.sh --tag v1.4.2
#   bash scripts/datagen/update.sh --tag v1.4.2 --dry-run
#   bash scripts/datagen/update.sh --skip-sync          # data/json already current
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || PY=python3

TAG=""; DRY=""; SKIP_SYNC=0; SKIP_ICONS=0; SKIP_TILES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --dry-run) DRY="--dry-run"; shift ;;
    --skip-sync) SKIP_SYNC=1; shift ;;
    --skip-icons) SKIP_ICONS=1; shift ;;
    --skip-tiles) SKIP_TILES=1; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

if [ $SKIP_SYNC -eq 0 ] && [ -z "$TAG" ]; then
  echo "error: --tag <save-pal release> is required (or pass --skip-sync)"; exit 2
fi

# The extractor is a net8.0 apphost; without DOTNET_ROOT it fails with a
# confusing "You must install .NET" even though ~/.dotnet is present.
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
export PALWORLD_PAK_DIR="${PALWORLD_PAK_DIR:-$HOME/.gamedata/palworld-pak-data}"
export PALWORLD_USMAP="${PALWORLD_USMAP:-$HOME/.gamedata/palworld-pak-data/Palworld.usmap}"

step() { echo; echo "==> $*"; }

if [ $SKIP_SYNC -eq 0 ]; then
  step "1/5  sync data/json from save-pal $TAG"
  "$PY" "$HERE/sync_game_data.py" --tag "$TAG" $DRY

  step "2/5  regenerate map_objects.json"
  "$PY" "$HERE/generate_map_objects.py" --tag "$TAG" $DRY
else
  echo "==> 1-2/5  skipped (--skip-sync)"
fi

if [ $SKIP_ICONS -eq 0 ]; then
  step "3/5  extract missing icons from the pak"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (see README.md)"
    echo "    PALWORLD_PAK_DIR=$PALWORLD_PAK_DIR"
    echo "    PALWORLD_USMAP=$PALWORLD_USMAP"
  elif [ -n "$DRY" ]; then
    "$PY" "$HERE/generate_icons.py"          # report-only without --extract
  else
    "$PY" "$HERE/generate_icons.py" --extract
  fi
else
  echo "==> 3/5  skipped (--skip-icons)"
fi

if [ $SKIP_ICONS -eq 0 ]; then
  step "3b/5 regenerate spawns.json from the pak's spawner tables"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed spawns.json stays as is)"
  else
    "$PY" "$HERE/generate_spawns.py" $DRY
  fi

  step "3c/5 regenerate partner_skills.json from the pak's skill text + parameter tables"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed partner_skills.json stays as is)"
  else
    "$PY" "$HERE/generate_partner_skills.py" $DRY
  fi

  step "3d/5 regenerate pal_parameters.json from the pak's species table (needs a usmap >= the game)"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed pal_parameters.json stays as is)"
  else
    "$PY" "$HERE/generate_pal_parameters.py" $DRY
  fi

  step "3e/5 regenerate schematics.json from the pak's recipe + build-object tables"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed schematics.json stays as is)"
  else
    "$PY" "$HERE/generate_schematics.py" $DRY
  fi

  step "3f/5 regenerate activity.json from the pak's lab, expedition and recipe tables"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed activity.json stays as is)"
  else
    "$PY" "$HERE/generate_activity_tables.py" $DRY
  fi

  step "3g/5 regenerate loadout.json from the pak's item, food-effect and player-parameter tables"
  if [ ! -d "$PALWORLD_PAK_DIR" ] || [ ! -f "$PALWORLD_USMAP" ]; then
    echo "  pak or usmap missing -- skipping (the committed loadout.json stays as is)"
  else
    "$PY" "$HERE/generate_loadout.py" $DRY
  fi
fi

if [ $SKIP_TILES -eq 0 ] && [ -z "$DRY" ]; then
  step "4/5  slice map tiles"
  "$PY" "$ROOT/scripts/slice_map.py"
else
  echo "==> 4/5  skipped"
fi

step "5/5  validate"
if [ $SKIP_TILES -eq 1 ] || [ -n "$DRY" ]; then
  "$PY" "$HERE/validate.py" --skip-tiles
else
  "$PY" "$HERE/validate.py"
fi

echo
echo "Done. Review 'git diff' (and 'git status' for new icons), then commit."
