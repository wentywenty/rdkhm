#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
kernel="$RDKHM_KERNEL_TREE"
oh="$RDKHM_OH_DEPS_TREE"
link_directory() {
    local source=$1 destination=$2 current
    [[ -e "$source" ]] || { echo "Missing link source: $source" >&2; exit 1; }
    mkdir -p "$(dirname "$destination")"
    if [[ -L "$destination" ]]; then
        if current=$(realpath -e "$destination" 2>/dev/null); then
            [[ "$current" == "$(realpath -e "$source")" ]] && return 0
            echo "Refusing to replace symlink to $current: $destination" >&2
            exit 1
        fi
        # Broken link left by an older source layout; regenerate it.
        rm -f "$destination"
    elif [[ -e "$destination" ]]; then
        echo "Refusing to replace existing directory: $destination" >&2
        exit 1
    fi
    ln -s "$source" "$destination"
}
link_directory "$oh/drivers/hdf_core/adapter/khdf/linux" "$kernel/drivers/hdf/khdf"
link_directory "$oh/drivers/hdf_core/framework" "$kernel/drivers/hdf/framework"
link_directory "$oh/drivers/hdf_core/interfaces/inner_api" "$kernel/drivers/hdf/inner_api"
link_directory "$oh/drivers/hdf_core/framework/include" "$kernel/include/hdf"
link_directory "$oh/third_party/bounds_checking_function" "$kernel/bounds_checking_function"
link_directory "$workspace/overlay/vendor/drobotics" "$oh/vendor/drobotics"
