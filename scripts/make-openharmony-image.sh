#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
images=${1:-$workspace/sources/openharmony-full/out/rdk_x5/packages/phone/images}
kernel="$workspace/out/kernel/obj/arch/arm64/boot"
for file in "$images/system.img" "$images/vendor.img" "$images/userdata.img" \
    "$kernel/Image" "$workspace/out/bringup-bin/busybox"; do
    [[ -f "$file" ]] || { echo "Missing $file; finish the full userspace build first" >&2; exit 1; }
done
for tool in debugfs e2fsck resize2fs mkimage sfdisk mkfs.vfat mcopy; do
    command -v "$tool" >/dev/null
done
mkdir -p "$workspace/out/images"
stage=$(mktemp -d "$workspace/out/images/.openharmony.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
for name in system vendor userdata sys_prod chip_prod eng_system eng_chipset; do
    if [[ ! -f "$images/$name.img" ]]; then
        [[ ! -d "$images/../$name" ]] || {
            echo "Missing image for staged partition $name" >&2; exit 1;
        }
        continue
    fi
    # Android sparse and raw ext4 images both occur in upstream build outputs.
    magic=$(od -An -tx4 -N4 "$images/$name.img" | tr -d ' ')
    if [[ "$magic" == ed26ff3a ]]; then
        simg2img "$images/$name.img" "$stage/$name.img"
    else
        cp --reflink=auto --sparse=always "$images/$name.img" "$stage/$name.img"
    fi
    e2fsck -fn "$stage/$name.img"
done
python3 "$workspace/scripts/inject-driver-bundle.py" "$stage/vendor.img"
e2fsck -fn "$stage/vendor.img"
# Preserve upstream ownership, capabilities and labels by extending its image.
system_bytes=$(stat -c %s "$stage/system.img")
system_mib=$(( (system_bytes + 1048575) / 1048576 + 256 ))
truncate -s "${system_mib}M" "$stage/system.img"
resize2fs "$stage/system.img"
mkimage -C none -A arm -T script -d "$workspace/bringup/openharmony-boot.cmd" "$stage/boot.scr"
debugfs -w -R 'mkdir /boot' "$stage/system.img"
debugfs -w -R 'mkdir /boot/hobot' "$stage/system.img"
debugfs -w -R 'mkdir /rdkhm' "$stage/system.img"
inject() {
    debugfs -w -R "write $1 $2" "$stage/system.img"
    debugfs -w -R "set_inode_field $2 uid 0" "$stage/system.img"
    debugfs -w -R "set_inode_field $2 gid 0" "$stage/system.img"
    debugfs -w -R "set_inode_field $2 mode $3" "$stage/system.img"
    debugfs -R "dump $2 $stage/injected" "$stage/system.img"
    cmp "$1" "$stage/injected"
    rm "$stage/injected"
}
inject "$kernel/Image" /boot/Image 0100644
for dtb in x5-rdk x5-rdk-v1p0; do
    inject "$kernel/dts/hobot/$dtb.dtb" "/boot/hobot/$dtb.dtb" 0100644
done
inject "$stage/boot.scr" /boot/boot.scr 0100644
inject "$workspace/bringup/openharmony-init" /rdkhm/init 0100755
inject "$workspace/bringup/load-drivers.sh" /rdkhm/load-drivers.sh 0100755
inject "$workspace/bringup/hdmi-status.sh" /rdkhm/hdmi-status.sh 0100755
inject "$workspace/bringup/touch-status.sh" /rdkhm/touch-status.sh 0100755
inject "$workspace/bringup/capture-hilog.sh" /rdkhm/capture-hilog.sh 0100755
inject "$workspace/bringup/rdkhm-bluetooth-init.sh" /rdkhm/bluetooth-init.sh 0100755
inject "$workspace/out/bringup-bin/busybox" /rdkhm/busybox 0100755
for name in sys_prod chip_prod eng_system eng_chipset; do
    [[ -f "$stage/$name.img" ]] || continue
    inject "$stage/$name.img" "/rdkhm/$name.img" 0100644
done
e2fsck -fn "$stage/system.img"
truncate -s 256M "$stage/config.img"
mkfs.vfat -F 32 -s 4 -n CONFIG "$stage/config.img"
mcopy -i "$stage/config.img" "$workspace/STATUS.md" ::STATUS.txt
system_sectors=$(( $(stat -c %s "$stage/system.img") / 512 ))
vendor_sectors=$(( $(stat -c %s "$stage/vendor.img") / 512 ))
data_sectors=$(( $(stat -c %s "$stage/userdata.img") / 512 ))
vendor_start=$(( (532480 + system_sectors + 8191) / 8192 * 8192 ))
data_start=$(( (vendor_start + vendor_sectors + 8191) / 8192 * 8192 ))
image="$stage/rdkhm-x5-openharmony-dev.img"
truncate -s "$(( (data_start + data_sectors) * 512 ))" "$image"
sfdisk "$image" <<PARTITIONS
label: dos
unit: sectors

start=8192, size=524288, type=c
start=532480, size=$system_sectors, type=83, bootable
start=$vendor_start, size=$vendor_sectors, type=83
start=$data_start, size=$data_sectors, type=83
PARTITIONS
dd if="$stage/config.img" of="$image" bs=1M seek=4 conv=notrunc,sparse status=none
dd if="$stage/system.img" of="$image" bs=1M seek=260 conv=notrunc,sparse status=none
dd if="$stage/vendor.img" of="$image" bs=1M seek="$((vendor_start / 2048))" conv=notrunc,sparse status=none
dd if="$stage/userdata.img" of="$image" bs=1M seek="$((data_start / 2048))" conv=notrunc,sparse status=none
mv "$image" "$workspace/out/images/"
cd "$workspace/out/images"
sha256sum rdkhm-x5-openharmony-dev.img > rdkhm-x5-openharmony-dev.img.sha256
sfdisk --json rdkhm-x5-openharmony-dev.img > rdkhm-x5-openharmony-dev.partitions.json
echo "Created $workspace/out/images/rdkhm-x5-openharmony-dev.img"
