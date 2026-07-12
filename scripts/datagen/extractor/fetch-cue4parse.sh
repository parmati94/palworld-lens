#!/usr/bin/env bash
# Vendor CUE4Parse at the exact commit FModel ships (proven-good UE5 reader).
# vendor/ is gitignored; this re-clones it deterministically.
#
# We pin purely for a stable, known-good package/texture reader. Palworld paks are
# unencrypted (zero AES key) and use tagged/unversioned properties decoded with a
# usmap (see README) — no CUE4Parse source patch needed, unlike some games.
set -euo pipefail

PIN="ab20414ab3661fbfda06afdd00c8b54bc7797c90"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vendor/CUE4Parse"

if [ -d "$DIR/.git" ] && [ "$(git -C "$DIR" rev-parse HEAD 2>/dev/null)" = "$PIN" ]; then
  echo "CUE4Parse already at $PIN"
  exit 0
fi

rm -rf "$DIR"
git clone --filter=blob:none --no-checkout https://github.com/FabianFG/CUE4Parse "$DIR"
git -C "$DIR" checkout "$PIN"
git -C "$DIR" submodule update --init --recursive --depth 1
echo "CUE4Parse vendored at $PIN"
