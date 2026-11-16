#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd "$(dirname "$0")/.." && pwd)
source "$workspace/scripts/workspace-env.sh"
cross=${CROSS_COMPILE:-aarch64-none-linux-gnu-}
source_dir="$workspace/sources/x5-hobot-drivers"
revision=$(git -C "$source_dir" rev-parse HEAD)
make -C "$workspace/out/kernel/obj" ARCH=arm64 CROSS_COMPILE="$cross" \
    M="$source_dir/bpu-hw_io" PWD="$source_dir" BPUIO_GIT_COMMIT="$revision" -j"${JOBS:-16}" modules
