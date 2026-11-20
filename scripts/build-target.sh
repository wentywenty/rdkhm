#!/usr/bin/env bash
# Build one OpenHarmony ninja target without assembling a full image.
# Example: scripts/build-target.sh vendor_image
#          scripts/build-target.sh drivers/peripheral/display/composer/vdi_base:display_composer_vdi_impl_default
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -ne 1 ]]; then
    echo "usage: $0 <ninja-target>" >&2
    echo "  examples: vendor_image" >&2
    echo "            drivers/peripheral/display/composer/vdi_base:display_composer_vdi_impl_default" >&2
    exit 2
fi
exec bash "$workspace/scripts/build-openharmony.sh" --build-target "$1"
