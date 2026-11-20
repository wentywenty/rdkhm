#!/usr/bin/env bash
# Compatibility wrapper: Settings uses the generic HAP builder, which also
# stages out/settings/Settings.hap for image assembly.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$workspace/scripts/build-hap.py" settings
