#!/usr/bin/env bash
# Package src/quartermaster/ as a Blender-installable zip.
#
# Output: dist/quartermaster.zip
# Install: Blender > Edit > Preferences > Add-ons > Install... > select zip
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/src"
OUT_DIR="$REPO_ROOT/dist"
OUT_ZIP="$OUT_DIR/quartermaster.zip"

mkdir -p "$OUT_DIR"
rm -f "$OUT_ZIP"

# Zip the package — everything under src/quartermaster/ goes into the zip
# at the top-level path "quartermaster/...". Skip __pycache__ and .pyc.
cd "$SRC"
zip -r "$OUT_ZIP" quartermaster \
    -x 'quartermaster/__pycache__/*' \
    -x 'quartermaster/**/__pycache__/*' \
    -x '*.pyc' \
    > /dev/null

echo "Built: $OUT_ZIP"
echo "Size:  $(du -h "$OUT_ZIP" | cut -f1)"
echo
echo "Install in Blender:  Edit > Preferences > Add-ons > Install... > $OUT_ZIP"
