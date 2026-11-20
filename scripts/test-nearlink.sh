#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd "$(dirname "$0")/.." && pwd)
source "$workspace/env.sh"
python3 "$workspace/scripts/prepare-nearlink.py"
# nearlink-ssap is generated beside the OpenHarmony tree under sources/oh.
stack="$(dirname "$RDKHM_OH_TREE")/nearlink-ssap"
mkdir -p "$workspace/out/tests/nearlink"
if [[ "${1:-}" == --ohos ]]; then
    tree="$RDKHM_OH_TREE"
    for suite in codec server feature link; do
        "$tree/prebuilts/clang/ohos/linux-x86_64/llvm/bin/clang" \
          --target=aarch64-linux-ohos --sysroot="$tree/out/rdk_x5/obj/third_party/musl" \
          -std=c11 -I"$stack/include" "$stack"/src/*.c "$stack/test/test_$suite.c" \
          -o "$workspace/out/tests/nearlink/$suite-ohos"
        qemu-aarch64-static -L "$tree/out/rdk_x5/packages/phone/system" \
          "$workspace/out/tests/nearlink/$suite-ohos"
    done
    exit 0
fi
for suite in codec server feature link; do
    cc -std=c11 -O1 -g -Wall -Wextra -fsanitize=address,undefined \
      -I"$stack/include" "$stack"/src/*.c "$stack/test/test_$suite.c" \
      -o "$workspace/out/tests/nearlink/$suite"
    "$workspace/out/tests/nearlink/$suite"
done
