#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tree="$workspace/sources/openharmony-full"
python3 "$workspace/scripts/prepare-nearlink.py"
[[ -d "$tree/.repo" ]] || { echo 'Run scripts/sync-openharmony.sh first' >&2; exit 1; }
for entry in 'drivers/peripheral:display/0001-x5-software-drm.patch' \
    'drivers/peripheral:display/0002-composer-c-entrypoints.patch' \
    'drivers/peripheral:display/0003-crtc-mask-selection.patch' \
    'drivers/peripheral:display/0004-drm-power-and-present.patch' \
    'drivers/peripheral:display/0005-primary-plane-zpos.patch' \
    'drivers/peripheral:display/0006-primary-plane-format.patch' \
    'drivers/peripheral:input/0001-evdev-touch-capabilities.patch' \
    'drivers/peripheral:audio/0001-x5-alsa-integration.patch' \
    'foundation/multimedia/audio_framework:audio/0002-optional-sink-aux.patch' \
    'base/account/os_account:account/0001-empty-index-object.patch' \
    'build:build-host/0001-select-host-gcc.patch' \
    'arkcompiler/ets_frontend:ets-frontend/0001-node14-rimraf.patch' \
    'developtools/ace_ets2bundle:ace-ets2bundle/0001-host-gcc.patch' \
    'foundation/ability/ability_runtime:ability-runtime/0001-dialog-want-import.patch' \
    'foundation/arkui/ace_engine:ace-engine/0001-pixelmap-ani-dependency.patch' \
    'foundation/graphic/graphic_3d:graphic3d/0001-host-shader-toolchain.patch' \
    'foundation/graphic/graphic_2d:graphic2d/0001-software-render-build.patch'; do
    repo_dir="$tree/${entry%%:*}"
    patch_file="$workspace/patches/${entry#*:}"
    if ! git -C "$repo_dir" apply --reverse --check "$patch_file" 2>/dev/null; then
        git -C "$repo_dir" apply --check "$patch_file"
        git -C "$repo_dir" apply "$patch_file"
    fi
done
patch="$workspace/patches/ark-runtime/0001-node14-rimraf.patch"
runtime="$tree/arkcompiler/runtime_core"
if ! git -C "$runtime" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$runtime" apply --check "$patch"
    git -C "$runtime" apply "$patch"
fi
patch="$workspace/patches/device-manager/0001-respect-headless-product.patch"
device_manager="$tree/foundation/distributedhardware/device_manager"
if ! git -C "$device_manager" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$device_manager" apply --check "$patch"
    git -C "$device_manager" apply "$patch"
fi
patch="$workspace/patches/libnl/0001-use-installed-host-tools.patch"
libnl="$tree/third_party/libnl"
if ! git -C "$libnl" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$libnl" apply --check "$patch"
    git -C "$libnl" apply "$patch"
fi
# Install the shared Python archive sequentially. The upstream downloader can
# write the same cache file concurrently for python and python_llvm.
name=python-linux-x86-GLIBC2.35-3.11.4_20250807.tar.gz
hash=9afb88572822af9bcdfd96b0c9726efed084608723c15a874978e35c67a55d1d
archive="$workspace/sources/$name"
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
