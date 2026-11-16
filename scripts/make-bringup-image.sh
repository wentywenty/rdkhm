#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${RDKHM_FAKEROOT:-0} != 1 ]]; then
    exec fakeroot -- env RDKHM_FAKEROOT=1 bash "$0" "$@"
fi
for tool in mkimage mkfs.ext4 mkfs.vfat mcopy sfdisk e2fsck; do
    command -v "$tool" >/dev/null
done
kernel="$workspace/out/kernel/obj"
binary="$workspace/out/bringup-bin"
for file in "$kernel/arch/arm64/boot/Image" "$binary/busybox" "$binary/kernel-probe"; do
    [[ -f "$file" ]] || { echo "Missing $file" >&2; exit 1; }
done
mkdir -p "$workspace/out/images"
stage=$(mktemp -d "$workspace/out/images/.bringup.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
root="$stage/root"
mkdir -p "$root"/{bin,sbin,etc,dev,proc,sys,run,tmp,var/log,boot/hobot,boot/config}
install -m 0755 "$binary/busybox" "$binary/kernel-probe" "$root/bin/"
# List target applets via user-mode emulation; never execute the target init here.
qemu-aarch64-static "$binary/busybox" --list | while IFS= read -r applet; do
    [[ "$applet" == busybox ]] || ln -s busybox "$root/bin/$applet"
done
install -m 0755 "$workspace/bringup/init" "$root/sbin/init"
install -m 0644 "$kernel/arch/arm64/boot/Image" "$root/boot/Image"
install -m 0644 "$kernel/arch/arm64/boot/dts/hobot/"x5-rdk{,-v1p0}.dtb "$root/boot/hobot/"
install -m 0644 "$workspace/bringup/boot.cmd" "$root/boot/boot.cmd"
mkimage -C none -A arm -T script -d "$root/boot/boot.cmd" "$root/boot/boot.scr"
printf '%s\n' 'NAME="RDKHM kernel bring-up"' 'ID=rdkhm-bringup' 'VERSION_ID=0.1' > "$root/etc/os-release"
printf '%s\n' 'BRINGUP ONLY. No OpenHarmony userspace, Launcher, or HAP support.' > "$root/etc/rdkhm-stage"
install -m 0644 "$workspace/sources.lock.tsv" "$root/etc/rdkhm-sources.lock.tsv"
install -m 0644 "$kernel/.config" "$root/boot/kernel.config"
printf '%s\n' 'RDKHM X5 kernel bring-up. Requires existing X5 QSPI firmware.' > "$stage/README.txt"
chown -R 0:0 "$root"
chmod 1777 "$root/tmp"
mknod -m 0600 "$root/dev/console" c 5 1
mknod -m 0666 "$root/dev/null" c 1 3
truncate -s 256M "$stage/config.img"
mkfs.vfat -F 32 -s 4 -n CONFIG "$stage/config.img"
mcopy -i "$stage/config.img" "$stage/README.txt" ::README.txt
truncate -s 256M "$stage/rootfs.img"
mkfs.ext4 -q -F -L rootfs -O '^64bit,^metadata_csum,^huge_file' \
    -E lazy_itable_init=0,lazy_journal_init=0 -d "$root" "$stage/rootfs.img"
e2fsck -fn "$stage/rootfs.img"
image="$stage/rdkhm-x5-bringup-0.1.img"
truncate -s 516M "$image"
# Match the vendor layout: 4 MiB gap, 256 MiB FAT, ext4 boot/root partition.
sfdisk "$image" <<'PARTITIONS'
label: dos
unit: sectors

start=8192, size=524288, type=c
start=532480, size=524288, type=83, bootable
PARTITIONS
dd if="$stage/config.img" of="$image" bs=1M seek=4 conv=notrunc status=none
dd if="$stage/rootfs.img" of="$image" bs=1M seek=260 conv=notrunc status=none
mv "$image" "$workspace/out/images/rdkhm-x5-bringup-0.1.img"
cd "$workspace/out/images"
sha256sum rdkhm-x5-bringup-0.1.img > rdkhm-x5-bringup-0.1.img.sha256
sfdisk --json rdkhm-x5-bringup-0.1.img > rdkhm-x5-bringup-0.1.partitions.json
echo "Created $workspace/out/images/rdkhm-x5-bringup-0.1.img (not board-tested)"
