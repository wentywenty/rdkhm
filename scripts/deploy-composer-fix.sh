#!/usr/bin/env bash
# Hot-deploy the rebuilt composer VDI/service pair for a controlled board test.
# Dry-run is the default. --apply changes /vendor and restarts display services.
# A serial console MUST be available before using --apply.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
hdc="$RDKHM_HDC"
[[ $# -ge 1 ]] || { echo "usage: $0 <target:port> [--apply]" >&2; exit 2; }
target=$1
apply=0
[[ ${2:-} == --apply ]] && apply=1
phy="$RDKHM_OH_TREE/out/rdk_x5/packages/phone/vendor/lib64"
stage="/data/rdkhm-fixes/composer-$(date +%Y%m%d-%H%M%S)"
files=(libdisplay_composer_vdi_impl_default.z.so libdisplay_composer_service_1.3.z.so)

for name in "${files[@]}"; do
    [[ -f "$phy/$name" ]] || { echo "Missing build output: $phy/$name" >&2; exit 1; }
done

remote() {
    local output status
    output=$(timeout 40 "$hdc" -t "$target" shell "set -e; { $1; }; result=\$?; echo __RDKHM_STATUS:\$result")
    output=${output//$'\r'/}
    status=$(printf '%s\n' "$output" | sed -n 's/^__RDKHM_STATUS://p' | tail -n 1)
    printf '%s\n' "$output" | sed '/^__RDKHM_STATUS:/d'
    [[ "$status" == 0 ]]
}
send() { timeout 30 "$hdc" -t "$target" file send "$1" "$2"; }

echo "target: $target"
echo "stage:  $stage"
echo "mode:   $([[ $apply == 1 ]] && echo apply || echo dry-run)"
for name in "${files[@]}"; do
    printf '  %s  %s\n' "$(sha256sum "$phy/$name" | awk '{print $1}')" "$name"
done

if [[ $apply == 0 ]]; then
    echo "dry-run only; re-run with --apply after arranging serial access"
    exit 0
fi

restore() {
    remote "/rdkhm/busybox mount -o remount,rw /vendor" >/dev/null 2>&1 || true
    for name in "${files[@]}"; do
        remote "test -f $stage/original/$name && /rdkhm/busybox cp -p $stage/original/$name /vendor/lib64/$name"
    done
    remote "/rdkhm/busybox mount -o remount,ro /vendor" >/dev/null 2>&1 || true
    remote 'service_control stop composer_host; service_control start composer_host; service_control stop render_service; service_control start render_service' || true
}
trap 'echo "deployment failed; restoring backup" >&2; restore' ERR

remote "mkdir -p $stage/original"
for name in "${files[@]}"; do
    send "$phy/$name" "$stage/$name"
    expected=$(sha256sum "$phy/$name" | awk '{print $1}')
    actual=$(remote "/rdkhm/busybox sha256sum $stage/$name" | awk '{print $1}')
    [[ "$actual" == "$expected" ]] || { echo "Transfer mismatch: $name" >&2; exit 1; }
    remote "/rdkhm/busybox cp -p /vendor/lib64/$name $stage/original/$name"
done

remote '/rdkhm/busybox mount -o remount,rw /vendor'
for name in "${files[@]}"; do
    remote "/rdkhm/busybox cp $stage/$name /vendor/lib64/$name.rdkhm-new && chmod 0644 /vendor/lib64/$name.rdkhm-new && chown root:root /vendor/lib64/$name.rdkhm-new && /rdkhm/busybox mv /vendor/lib64/$name.rdkhm-new /vendor/lib64/$name"
    expected=$(sha256sum "$phy/$name" | awk '{print $1}')
    actual=$(remote "/rdkhm/busybox sha256sum /vendor/lib64/$name" | awk '{print $1}')
    [[ "$actual" == "$expected" ]] || { echo "Installed hash mismatch: $name" >&2; exit 1; }
done
remote '/rdkhm/busybox mount -o remount,ro /vendor'
trap - ERR

remote 'service_control stop composer_host; service_control start composer_host'
sleep 1
remote 'service_control stop render_service; service_control start render_service'
sleep 2
remote '/rdkhm/screen-status.sh --capture' || true
echo "Deployed. Backup: $stage/original"
