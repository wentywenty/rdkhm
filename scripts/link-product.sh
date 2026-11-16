#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tree="$workspace/sources/openharmony-full"
for path in vendor/drobotics device/board/drobotics; do
    target="$tree/$path"
    source_dir="$workspace/overlay/$path"
    mkdir -p "$(dirname "$target")"
    if [[ -e "$target" || -L "$target" ]]; then
        [[ $(readlink -f "$target") == "$(readlink -f "$source_dir")" ]] || {
            echo "Refusing to replace $target" >&2; exit 1;
        }
    else
        ln -s "$source_dir" "$target"
    fi
done
