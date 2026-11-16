#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
kernel="$workspace/sources/x5-kernel"
oh="$workspace/sources/openharmony"
link_directory() {
    local source=$1 destination=$2
    mkdir -p "$(dirname "$destination")"
    if [[ -e "$destination" || -L "$destination" ]]; then
        [[ -L "$destination" && "$(realpath "$destination")" == "$(realpath "$source")" ]] || {
            echo "Refusing to replace $destination" >&2
            exit 1
        }
    else
        ln -s "$source" "$destination"
    fi
}
link_directory "$oh/drivers/hdf_core/adapter/khdf/linux" "$kernel/drivers/hdf/khdf"
link_directory "$oh/drivers/hdf_core/framework" "$kernel/drivers/hdf/framework"
link_directory "$oh/drivers/hdf_core/interfaces/inner_api" "$kernel/drivers/hdf/inner_api"
link_directory "$oh/drivers/hdf_core/framework/include" "$kernel/include/hdf"
link_directory "$oh/third_party/bounds_checking_function" "$kernel/bounds_checking_function"
link_directory "$workspace/overlay/vendor/drobotics" "$oh/vendor/drobotics"
