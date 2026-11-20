#!/usr/bin/env bash
# Synchronize non-OpenHarmony upstreams through config/sources/repo.xml.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
manifest="$workspace/config/sources/repo.xml"
manifest_repo="$workspace/out/source-manifest"
mkdir -p "$workspace/sources" "$workspace/out/logs"

mkdir -p "$manifest_repo"
install -m 0644 "$manifest" "$manifest_repo/default.xml"
git -C "$manifest_repo" init -q
git -C "$manifest_repo" add default.xml
if git -C "$manifest_repo" rev-parse --verify HEAD >/dev/null 2>&1; then
    git -C "$manifest_repo" -c user.name=rdkhm -c user.email=rdkhm@localhost \
        commit -qm "update source manifest" || true
else
    git -C "$manifest_repo" -c user.name=rdkhm -c user.email=rdkhm@localhost \
        commit -qm "rdkhm source manifest"
fi

if [[ -d "$workspace/sources/.repo" ]]; then
    cd "$workspace/sources"
    repo sync -c -j"${SYNC_JOBS:-8}" --no-clone-bundle --fail-fast \
        2>&1 | tee "$workspace/out/logs/sources-sync.log"
elif [[ -d "$workspace/sources/rdk/x5-kernel/.git" ]]; then
    echo "Existing non-repo checkouts found; verifying pinned revisions instead of syncing."
    python3 "$workspace/scripts/check-sources.py"
else
    cd "$workspace/sources"
    repo init -u "$manifest_repo" -m default.xml \
        --repo-url=https://github.com/GerritCodeReview/git-repo.git --no-repo-verify
    repo sync -c -j"${SYNC_JOBS:-8}" --no-clone-bundle --fail-fast \
        2>&1 | tee "$workspace/out/logs/sources-sync.log"
fi

# repo cannot nest projects; expose the camsys project inside the kernel tree.
link="$workspace/sources/rdk/x5-kernel/drivers/media/platform/horizon/camsys"
if [[ -e "$link" && ! -L "$link" ]]; then
    echo "Refusing to replace existing camsys directory: $link" >&2
    exit 1
fi
ln -sfn ../../../../../x5-drv-camsys "$link"
