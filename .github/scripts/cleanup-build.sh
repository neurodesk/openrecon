#!/bin/bash
set -euo pipefail

application=${1:-}
if [[ ! "$application" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  printf 'Invalid recipe name for cleanup: %s\n' "$application" >&2
  exit 1
fi
recipe_dir="recipes/$application"
if [[ -L recipes || -L "$recipe_dir" || ! -f "$recipe_dir/OpenReconLabel.json" ]]; then
  printf 'Cleanup requires a recipe directory with OpenReconLabel.json: %s\n' "$recipe_dir" >&2
  exit 1
fi

# The self-hosted runners share one /storage disk. Packages left in the
# workspace until that runner's next checkout fill it for concurrent builds.
rm -rf -- "$recipe_dir/openrecon" "$recipe_dir/fire" "$recipe_dir"/fire-bundle-*
rm -f -- "$recipe_dir"/OpenRecon_*.tar "$recipe_dir"/FIRE_*.img \
  "$recipe_dir"/FIRE_*.rootfs.tar "$recipe_dir/.base_image.tar"
df -h . || true
