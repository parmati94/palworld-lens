#!/usr/bin/env bash
# Fetch the Oodle data-compression library CUE4Parse needs to decompress UE5 pak
# chunks on Linux. We don't commit the binary; this re-acquires it deterministically.
#
# Source: WorkingRobot/OodleUE GitHub releases — the same open-source Oodle build
# CUE4Parse/FModel download automatically. Tag is pinned and integrity-checked.
set -euo pipefail

TAG="2026-06-04-1357"
ASSET="gcc-x64-release.zip"
SO_IN_ZIP="lib/liboodle-data-shared.so"
EXPECT_SHA="f21d70299bbe873f63e8aef778b30f4dee6dec1fc09140c185caf1f8d153f771"

DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/runtime"
DEST="$DEST_DIR/liboodle-data-shared.so"
mkdir -p "$DEST_DIR"

if [ -f "$DEST" ] && [ "$(sha256sum "$DEST" | cut -d' ' -f1)" = "$EXPECT_SHA" ]; then
  echo "Oodle already present and verified: $DEST"
  exit 0
fi

URL="https://github.com/WorkingRobot/OodleUE/releases/download/$TAG/$ASSET"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading Oodle from $URL"
curl -fsSL --retry 3 --max-time 120 "$URL" -o "$TMP/oodle.zip"
unzip -o -j "$TMP/oodle.zip" "$SO_IN_ZIP" -d "$TMP" >/dev/null
mv "$TMP/$(basename "$SO_IN_ZIP")" "$DEST"

GOT_SHA="$(sha256sum "$DEST" | cut -d' ' -f1)"
if [ "$GOT_SHA" != "$EXPECT_SHA" ]; then
  echo "ERROR: sha256 mismatch for liboodle-data-shared.so" >&2
  echo "  expected $EXPECT_SHA" >&2
  echo "  got      $GOT_SHA" >&2
  rm -f "$DEST"
  exit 1
fi

if command -v nm >/dev/null && ! nm -D "$DEST" 2>/dev/null | grep -qw OodleLZ_Decompress; then
  echo "ERROR: $DEST does not export OodleLZ_Decompress" >&2
  exit 1
fi

echo "Oodle ready and verified: $DEST"
