#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
hdc="$root/sources/openharmony-full/prebuilts/ohos-sdk/linux/20/toolchains/hdc"
target=${1:-10.43.10.159:5555}
stage="/data/rdkhm-fixes/boot-audio-$(date +%Y%m%d-%H%M%S)"
system="$root/sources/openharmony-full/out/rdk_x5/packages/phone/system"
remote() {
    local output status
    output=$(timeout 30 "$hdc" -t "$target" shell "set -e; { $1; }; result=\$?; echo __RDKHM_STATUS:\$result")
    output=${output//$'\r'/}
    status=$(printf '%s\n' "$output" | sed -n 's/^__RDKHM_STATUS://p' | tail -n 1)
    printf '%s\n' "$output" | sed '/^__RDKHM_STATUS:/d'
    [[ "$status" == 0 ]]
}
send() { timeout 30 "$hdc" -t "$target" file send "$1" "$2"; }
remote "mkdir -p $stage/original"
for lib in libaccountmgr.z.so libsink_adapter.z.so libmodule-hdi-sink.z.so; do
    send "$system/lib64/$lib" "$stage/$lib"
    remote "/rdkhm/busybox cp -p /system/lib64/$lib $stage/original/$lib"
    expected=$(sha256sum "$system/lib64/$lib" | awk '{print $1}')
    actual=$(remote "/rdkhm/busybox sha256sum $stage/$lib" | awk '{print $1}' | tr -d '\r')
    [[ "$actual" == "$expected" ]] || { echo "Transfer mismatch: $lib" >&2; exit 1; }
done
send "$root/out/driver-bundle/lib/modules/6.1.83-rdkhm/designware_i2s.ko" "$stage/designware_i2s.ko"
remote '/rdkhm/busybox mount -o remount,rw /'
trap 'remote "/rdkhm/busybox mount -o remount,ro /" || true' EXIT
# Replacing pathnames keeps existing library mappings intact until service restart.
for lib in libaccountmgr.z.so libsink_adapter.z.so libmodule-hdi-sink.z.so; do
    remote "/rdkhm/busybox cp $stage/$lib /system/lib64/$lib.rdkhm-new && chmod 0644 /system/lib64/$lib.rdkhm-new && chown root:root /system/lib64/$lib.rdkhm-new && /rdkhm/busybox mv /system/lib64/$lib.rdkhm-new /system/lib64/$lib"
    expected=$(sha256sum "$system/lib64/$lib" | awk '{print $1}')
    actual=$(remote "/rdkhm/busybox sha256sum /system/lib64/$lib" | awk '{print $1}')
    [[ "$actual" == "$expected" ]] || { echo "Installed hash mismatch: $lib" >&2; exit 1; }
done
remote 'for level in el3 el4 el5; do mkdir -p /data/app/$level /data/service/$level; chmod 0711 /data/app/$level /data/service/$level; done'
remote "test -d /sys/module/designware_i2s || /rdkhm/busybox insmod $stage/designware_i2s.ko"
remote 'service_control stop audio_server; service_control stop accountmgr'
sleep 2
remote 'service_control start accountmgr; service_control start audio_server'
printf 'Board backup and staged files: %s\n' "$stage"
