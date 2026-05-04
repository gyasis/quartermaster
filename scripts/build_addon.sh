#!/usr/bin/env bash
# Package src/quartermaster/ as Blender-installable zips.
#
# Builds two zips so users on either old or new Blender install paths work:
#   dist/quartermaster.zip            — legacy bl_info add-on, nested folder
#                                        layout. Edit > Preferences > Add-ons
#                                        > Install... (Blender 4.0+).
#   dist/quartermaster-extension.zip  — Blender 4.2+ extension format. Flat
#                                        layout with blender_manifest.toml
#                                        at root. Installable as an extension
#                                        (also works via the Add-ons > Install
#                                        path in 4.2+).
#
# Both come from the same source tree. The __init__.py has both bl_info and
# blender_manifest.toml because the inner package files are identical; only
# the zip's *layout* differs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/src"
OUT_DIR="$REPO_ROOT/dist"
LEGACY_ZIP="$OUT_DIR/quartermaster.zip"
EXTENSION_ZIP="$OUT_DIR/quartermaster-extension.zip"

mkdir -p "$OUT_DIR"
rm -f "$LEGACY_ZIP" "$EXTENSION_ZIP"

# Legacy: zip the package folder so the archive contains "quartermaster/..."
cd "$SRC"
zip -r "$LEGACY_ZIP" quartermaster \
    -x 'quartermaster/__pycache__/*' \
    -x 'quartermaster/**/__pycache__/*' \
    -x '*.pyc' \
    > /dev/null

# Extension: zip the package CONTENTS flat at the archive root, so the manifest
# and __init__.py are at the top — what extensions.blender.org expects.
cd "$SRC/quartermaster"
zip -r "$EXTENSION_ZIP" . \
    -x '__pycache__/*' \
    -x '**/__pycache__/*' \
    -x '*.pyc' \
    > /dev/null

echo "Built:"
echo "  legacy:    $LEGACY_ZIP    $(du -h "$LEGACY_ZIP"    | cut -f1)"
echo "  extension: $EXTENSION_ZIP $(du -h "$EXTENSION_ZIP" | cut -f1)"
echo
echo "Install in Blender 4.0+:    Edit > Preferences > Add-ons > Install... > legacy zip"
echo "Install as extension (4.2+): same path, or Get Extensions > Install from Disk."
