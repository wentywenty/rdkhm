#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
hdc="$root/sources/openharmony-full/prebuilts/ohos-sdk/linux/20/toolchains/hdc"
target=${1:-10.43.10.159:5555}
stage="/data/rdkhm-fixes/ws73-$(date +%Y%m%d-%H%M%S)"
remote() {
    local output status
    output=$(timeout 40 "$hdc" -t "$target" shell "set -e; { $1; }; result=\$?; echo __RDKHM_STATUS:\$result")
    output=${output//$'\r'/}
    status=$(printf '%s\n' "$output" | sed -n 's/^__RDKHM_STATUS://p' | tail -n 1)
    printf '%s\n' "$output" | sed '/^__RDKHM_STATUS:/d'
    [[ "$status" == 0 ]]
}
remote "mkdir -p $stage"
printf 'WS73 staging directory: %s\n' "$stage"
for name in plat_soc wifi_soc ble_soc sle_soc bluetooth; do
    file="$root/out/driver-bundle/lib/modules/6.1.83-rdkhm/$name.ko"
    timeout 30 "$hdc" -t "$target" file send "$file" "$stage/$name.ko"
    expected=$(sha256sum "$file" | awk '{print $1}')
    actual=$(remote "/rdkhm/busybox sha256sum $stage/$name.ko" | awk '{print $1}')
    [[ "$actual" == "$expected" ]] || exit 1
done
timeout 30 "$hdc" -t "$target" file send "$root/out/nearlink/ws73_cfg.ini" "$stage/ws73_cfg.ini"
remote '/rdkhm/busybox mount -o remount,rw /vendor'
trap 'remote "/rdkhm/busybox mount -o remount,ro /vendor" || true' EXIT
remote "if test -f /vendor/etc/ws73_cfg.ini; then /rdkhm/busybox cp -p /vendor/etc/ws73_cfg.ini $stage/ws73_cfg.ini.original; fi"
remote "/rdkhm/busybox cp $stage/ws73_cfg.ini /vendor/etc/ws73_cfg.ini && chmod 0644 /vendor/etc/ws73_cfg.ini"
for name in plat_soc wifi_soc bluetooth ble_soc sle_soc; do
    printf 'Loading %s\n' "$name"
    remote "test -d /sys/module/$name || /rdkhm/busybox insmod $stage/$name.ko"
done
remote 'cat /proc/modules; ls -l /dev/hwsle* /sys/class/bluetooth /sys/class/net; dmesg'
printf 'Staged WS73 files: %s\n' "$stage"
