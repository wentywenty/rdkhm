#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
archive="$workspace/sources/ohos-sdk-windows_linux-public.tar.gz"
hash=a315834ac133625efc912bd078f3e2b2550868d04aef1b5aa4f9679c8b3c9d8e
destination="$workspace/sources/openharmony-full/prebuilts/ohos-sdk/linux/20"
if [[ ! -f "$archive" ]]; then
    curl -fL --retry 3 --connect-timeout 20 \
        https://repo.huaweicloud.com/openharmony/os/6.0-Release/ohos-sdk-windows_linux-public.tar.gz \
        -o "$archive.part"
    mv "$archive.part" "$archive"
fi
echo "$hash  $archive" | sha256sum -c -
mkdir -p "$destination" "$workspace/out/sdk-extract"
if [[ ! -f "$workspace/out/sdk-extract/linux/native-linux-x64-6.0.0.47-Beta1.zip" ]]; then
    tar -xzf "$archive" -C "$workspace/out/sdk-extract" linux
fi
for component in native ets js toolchains; do
    unzip -q -o "$workspace/out/sdk-extract/linux/$component-linux-x64-6.0.0.47-Beta1.zip" -d "$destination"
done
test -f "$destination/native/sysroot/usr/lib/aarch64-linux-ohos/libbundle_ndk.z.so"
echo 'OpenHarmony API 20 SDK installed'
