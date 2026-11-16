#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd "$(dirname "$0")/.." && pwd)
sdk=$(python3 "$workspace/scripts/prepare-ws73-bsp.py")
obj="$workspace/out/kernel/obj"
source "$workspace/scripts/workspace-env.sh"
cross=${CROSS_COMPILE:-aarch64-none-linux-gnu-}
command -v "${cross}gcc" >/dev/null || { echo "Missing WS73 cross compiler: ${cross}gcc" >&2; exit 1; }
compiler_include=$(${cross}gcc -print-file-name=include)
[[ -f "$compiler_include/stdarg.h" ]] || { echo "Missing compiler builtin header: $compiler_include/stdarg.h" >&2; exit 1; }
export KCFLAGS="-I$compiler_include"
make -C "$sdk" prepare ini
export DIR_MAP_CONFIG_FILE=release.mk
export WSCFG_KCONFIG_CONFIG="$sdk/.config"
export WSCFG_AUTOCONFIG_H="$sdk/output/bin/autoconfig.h"
export CONFIG_WSXX_KERNEL_MODULES_BUILD_SUPPORT=yes
export BUILD_DEVICE_WITH_ROM_REPO=yes
for module in platform wifi bsle/ble_driver/linux bsle/sle_driver; do
    extra=()
    if [[ "$module" != platform ]]; then
        extra+=(KBUILD_EXTRA_SYMBOLS="$sdk/driver/platform/Module.symvers")
    fi
    make -C "$obj" ARCH=arm64 CROSS_COMPILE="$cross" \
        WSCFG_ARCH_NAME=arm64 WSCFG_CROSS_COMPILE="$cross" WSCFG_KERNEL_DIR="$obj" \
        WSCFG_EXTRA_CFLAGS="-Wno-error" M="$sdk/driver/$module" -j"${JOBS:-16}" "${extra[@]}" modules
done
install -d "$workspace/out/nearlink/modules"
for entry in platform/plat_soc wifi/wifi_soc bsle/ble_driver/linux/ble_soc bsle/sle_driver/sle_soc; do
    install -m 0644 "$sdk/driver/$entry.ko" "$workspace/out/nearlink/modules/"
done
install -m 0644 "$sdk/output/bin/ws73_cfg.ini" "$workspace/out/nearlink/"
