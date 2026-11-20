#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
bash "$workspace/scripts/fetch-sources.sh"
python3 "$workspace/scripts/apply-patches.py" --only kernel
if [[ "${RDKHM_KERNEL_PROFILE:-default}" == rt ]]; then
    python3 "$workspace/scripts/apply-patches.py" --only kernel-rt
else
    python3 "$workspace/scripts/apply-patches.py" --only kernel-rt --revert
fi
bash "$workspace/scripts/link-hdf.sh"
