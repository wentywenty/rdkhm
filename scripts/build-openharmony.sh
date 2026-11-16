#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tree="$workspace/sources/openharmony-full"
bash "$workspace/scripts/link-product.sh"
cd "$tree"
python_bin="$tree/prebuilts/python/linux-x86/current/bin"
[[ -e "$python_bin/python" ]] || ln -s python3 "$python_bin/python"
export PATH="$workspace/scripts:$tree/prebuilts/python/linux-x86/current/bin:$tree/prebuilts/build-tools/linux-x86/bin:$tree/prebuilts/build-tools/common/nodejs/current/bin:$PATH"
export NPM_CONFIG_USERCONFIG="$workspace/config/npmrc"
export PYTHONUNBUFFERED=1
mkdir -p "$workspace/out/logs"
# Hide incomplete newer GCC installations from the release's Clang 15.
host_gcc="$workspace/out/host-gcc"
mkdir -p "$host_gcc/lib/gcc/x86_64-linux-gnu" "$host_gcc/include"
[[ -e "$host_gcc/lib/gcc/x86_64-linux-gnu/11" ]] || ln -s /usr/lib/gcc/x86_64-linux-gnu/11 "$host_gcc/lib/gcc/x86_64-linux-gnu/11"
[[ -e "$host_gcc/include/c++" ]] || ln -s /usr/include/c++ "$host_gcc/include/c++"
[[ -e "$host_gcc/include/x86_64-linux-gnu" ]] || ln -s /usr/include/x86_64-linux-gnu "$host_gcc/include/x86_64-linux-gnu"
# build.py is the upstream hb entry point without build.sh's global HOME edits.
run_build() {
    python3 build.py --product-name rdk_x5 --ccache=false \
        --gn-args="rdkhm_host_gcc_install_dir=\"${RDKHM_HOST_GCC_DIR:-$host_gcc}\" selinux_adapter_build_path=\"base/security/selinux_adapter/sepolicy/ohos_product:vendor/drobotics/rdk_x5/sepolicy\"" \
        --ninja-args="-j${JOBS:-16}" --load-test-config=false "$@"
}
if [[ $# == 0 ]]; then
    run_build --build-target ohos_declaration_ets_api 2>&1 | tee "$workspace/out/logs/sdk-api.log"
    bash "$workspace/scripts/install-system-sdk-api.sh"
fi
run_build "$@" 2>&1 | tee "$workspace/out/logs/openharmony-build.log"
