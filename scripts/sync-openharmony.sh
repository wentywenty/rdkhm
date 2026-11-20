#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
tree="$RDKHM_OH_TREE"
mkdir -p "$tree" "$workspace/out/logs"
cd "$tree"
repo init -u https://gitcode.com/openharmony/manifest.git \
    -b d6a0fef04cd19e2ecf0ea978e683e5d2f7953198 \
    -m tag/manifest_tag_20250906_181023.xml --depth=1 -g default \
    --repo-url=https://github.com/GerritCodeReview/git-repo.git --no-repo-verify
# A resolved manifest pins every project, rather than following release branches.
install -m 0644 "$workspace/config/sources/openharmony.lock.xml" .repo/manifests/rdkhm-locked.xml
repo init -m rdkhm-locked.xml --no-repo-verify
# Mirror routing is scoped to this process and does not alter global Git settings.
env GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=url.https://gitcode.com/openharmony/.insteadOf \
    GIT_CONFIG_VALUE_0=https://gitee.com/openharmony/ \
    repo sync -c -j"${SYNC_JOBS:-8}" --no-clone-bundle --fail-fast \
    2>&1 | tee "$workspace/out/logs/openharmony-sync.log"
repo manifest -r -o "$workspace/out/openharmony-resolved.xml"
repo forall -j"${SYNC_JOBS:-6}" -c 'git lfs pull' \
    2>&1 | tee "$workspace/out/logs/openharmony-lfs.log"
