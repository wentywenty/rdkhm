#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$workspace/sources"
while read -r path url revision; do
    [[ -n "$path" && "$path" != \#* ]] || continue
    destination="$workspace/sources/$path"
    if [[ ! -e "$destination/.git" ]]; then
        if [[ -e "$destination" ]]; then
            echo "Refusing to replace existing directory: $destination" >&2
            exit 1
        fi
        mkdir -p "$destination"
        git -C "$destination" init
        git -C "$destination" remote add origin "$url"
        git -C "$destination" fetch --depth 1 origin "$revision"
        git -C "$destination" checkout --detach FETCH_HEAD
    fi
    actual=$(git -C "$destination" rev-parse HEAD)
    if [[ "$actual" != "$revision" ]]; then
        echo "Revision mismatch for $path: $actual != $revision" >&2
        exit 1
    fi
    printf '%s %s\n' "$path" "$actual"
done < "$workspace/sources.lock.tsv"
