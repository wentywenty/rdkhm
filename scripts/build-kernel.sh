#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output="$workspace/out/kernel/obj"
source "$workspace/env.sh"
kernel="$RDKHM_KERNEL_TREE"
cross=${CROSS_COMPILE:-aarch64-none-linux-gnu-}
jobs=${JOBS:-16}
profile=${RDKHM_KERNEL_PROFILE:-default}
target=${1:-configure}
case "$target" in
    configure|Image|dtbs|modules) ;;
    *) echo "Usage: $0 [configure|Image|dtbs|modules]" >&2; exit 2 ;;
esac
case "$profile" in
    default)
        defconfig=hobot_x5_rdk_ubuntu_defconfig
        ;;
    rt)
        defconfig=hobot_x5_rdk_ubuntu_rt_defconfig
        tracked="$workspace/config/kernel/$defconfig"
        tree_defconfig="$kernel/arch/arm64/configs/$defconfig"
        [[ -f "$tracked" ]] || { echo "Missing tracked RT defconfig: $tracked" >&2; exit 1; }
        [[ -f "$tree_defconfig" ]] || { echo "Missing kernel RT defconfig: $tree_defconfig" >&2; exit 1; }
        cmp -s "$tracked" "$tree_defconfig" || {
            echo "RT defconfig drift: $tracked differs from $tree_defconfig" >&2
            exit 1
        }
        ;;
    *) echo "Unknown RDKHM_KERNEL_PROFILE: $profile (expected default or rt)" >&2; exit 2 ;;
esac
command -v "${cross}gcc" >/dev/null
bash "$workspace/scripts/link-hdf.sh"
mkdir -p "$output" "$workspace/out/logs"
exec > >(tee "$workspace/out/logs/kernel-$target.log") 2>&1
echo "Kernel profile: $profile ($defconfig)"
hcgen="$workspace/out/host-tools/hc-gen"
make -C "$RDKHM_OH_DEPS_TREE/drivers/hdf_core/framework/tools/hc-gen" \
    BUILD_DIR="$(dirname "$hcgen")" -j"$jobs"
make_args=(-C "$kernel" O="$output" ARCH=arm64 CROSS_COMPILE="$cross"
    PRODUCT_PATH=vendor/drobotics/rdk_x5 RDKHM_HC_GEN="$hcgen")
make "${make_args[@]}" "$defconfig"
KCONFIG_CONFIG="$output/.config" "$kernel/scripts/kconfig/merge_config.sh" -m -O "$output" \
    "$output/.config" "$workspace/config/kernel/openharmony-base.config"
make "${make_args[@]}" olddefconfig
# Kconfig silently drops unknown or dependency-disabled symbols. Fail explicitly.
while IFS= read -r setting; do
    [[ "$setting" == CONFIG_*=* || "$setting" == \#\ CONFIG_*\ is\ not\ set ]] || continue
    if ! grep -Fxq -- "$setting" "$output/.config"; then
        echo "Required config was not retained: $setting" >&2
        exit 1
    fi
done < "$workspace/config/kernel/openharmony-base.config"
if [[ "$profile" == rt ]]; then
    grep -qx 'CONFIG_PREEMPT_RT=y' "$output/.config" || {
        echo "RT profile did not retain CONFIG_PREEMPT_RT=y; check Kconfig/defconfig" >&2
        exit 1
    }
fi
if [[ "$target" != configure ]]; then
    make "${make_args[@]}" -j"$jobs" "$target"
fi
