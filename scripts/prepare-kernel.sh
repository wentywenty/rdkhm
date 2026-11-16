#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bash "$workspace/scripts/fetch-sources.sh"
apply_once() {
    local repository=$1 patch_file=$2
    if git -C "$repository" apply --reverse --check "$patch_file" 2>/dev/null; then
        printf 'Already applied: %s\n' "$patch_file"
    else
        git -C "$repository" apply --check "$patch_file"
        git -C "$repository" apply "$patch_file"
    fi
}
apply_once "$workspace/sources/x5-kernel" \
    "$workspace/patches/x5-kernel/0001-openharmony-core.patch"
apply_once "$workspace/sources/x5-kernel" \
    "$workspace/patches/x5-kernel/0002-builtin-display-bridge.patch"
apply_once "$workspace/sources/x5-kernel" \
    "$workspace/patches/x5-kernel/0003-display-deferred-probe-devres.patch"
apply_once "$workspace/sources/x5-kernel" \
    "$workspace/patches/x5-kernel/0004-rdk-direct-scanout.patch"
apply_once "$workspace/sources/x5-kernel" \
    "$workspace/patches/x5-kernel/0005-display-object-list-lifetime.patch"
apply_once "$workspace/sources/openharmony/drivers/hdf_core" \
    "$workspace/patches/hdf-core/0001-arm64-kernel-build.patch"
bash "$workspace/scripts/link-hdf.sh"
