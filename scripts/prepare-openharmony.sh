#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
tree="$RDKHM_OH_TREE"
python3 "$workspace/scripts/prepare-nearlink.py"
[[ -d "$tree/.repo" ]] || { echo 'Run scripts/sync-openharmony.sh first' >&2; exit 1; }
python3 "$workspace/scripts/apply-patches.py" --only openharmony
python3 "$workspace/scripts/prepare-hvigor-sdk.py"
# Install the shared Python archive sequentially. The upstream downloader can
# write the same cache file concurrently for python and python_llvm.
name=python-linux-x86-GLIBC2.35-3.11.4_20250807.tar.gz
hash=9afb88572822af9bcdfd96b0c9726efed084608723c15a874978e35c67a55d1d
archive="$RDKHM_CACHE_DIR/$name"
if [[ ! -f "$archive" ]]; then
    curl -fL --retry 3 "https://mirrors.huaweicloud.com/openharmony/compiler/python/3.11.4/linux/$name" -o "$archive.tmp"
    mv "$archive.tmp" "$archive"
fi
echo "$hash  $archive" | sha256sum -c -
for destination in python python_llvm; do
    directory="$tree/prebuilts/$destination"
    mkdir -p "$directory"
    tar -xzf "$archive" -C "$directory"
    "$directory/linux-x86/3.11.4/bin/python3" --version
    touch "$directory/$hash.linux-x86.mark"
done
export NPM_CONFIG_USERCONFIG="$workspace/config/npmrc"
export PYTHONUNBUFFERED=1
mkdir -p "$workspace/out/logs"
cd "$tree"
bash build/prebuilts_download.sh --disable-rich \
    --tool-repo https://mirrors.huaweicloud.com \
    --pypi-url https://repo.huaweicloud.com/repository/pypi/simple \
    2>&1 | tee "$workspace/out/logs/openharmony-prebuilts.log"
# ace_ets2bundle's compiler imports the OpenHarmony-patched TypeScript package.
# Upstream setup does not consistently install this link on a reused checkout.
compiler_node_modules="$tree/developtools/ace_ets2bundle/compiler/node_modules"
typescript_source="$tree/third_party/typescript"
if [[ -d "$typescript_source/lib" && -f "$typescript_source/lib/typescript.js" ]]; then
    mkdir -p "$compiler_node_modules"
    if [[ -e "$compiler_node_modules/typescript" || -L "$compiler_node_modules/typescript" ]]; then
        rm -rf "$compiler_node_modules/typescript"
    fi
    ln -s "$typescript_source" "$compiler_node_modules/typescript"
else
    echo "Missing OpenHarmony TypeScript source; cannot build ace_ets2bundle" >&2
    exit 1
fi
bash "$workspace/scripts/link-product.sh"
chmod +x "$tree/prebuilts/tool/command-line-tools/ohpm/bin/ohpm" \
    "$tree/prebuilts/tool/command-line-tools/ohpm/bin/init" \
    "$tree/prebuilts/tool/command-line-tools/hvigor/bin/hvigorw"
bash "$workspace/scripts/prepare-sdk.sh"
bash "$workspace/scripts/prepare-host-tools.sh"
