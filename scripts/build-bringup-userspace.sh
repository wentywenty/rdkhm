#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
cross=${CROSS_COMPILE:-aarch64-none-linux-gnu-}
kernel="$RDKHM_KERNEL_TREE"
# repo.xml keeps the deps tree beside oh/ and rdk/.
deps_root=$(dirname "$(dirname "$kernel")")/deps
archive="$RDKHM_CACHE_DIR/busybox-1.36.1.tar.bz2"
source_dir="$deps_root/busybox-1.36.1"
output="$workspace/out/busybox"
mkdir -p "$output" "$workspace/out/bringup-bin" "$workspace/out/logs" "$deps_root"
if [[ ! -f "$archive" ]]; then
    curl -fL --retry 3 https://busybox.net/downloads/busybox-1.36.1.tar.bz2 -o "$archive"
fi
echo "b8cc24c9574d809e7279c3be349795c5d5ceb6fdf19ca709f80cde50e47de314  $archive" | sha256sum -c -
[[ -d "$source_dir" ]] || tar -xjf "$archive" -C "$deps_root"
exec > >(tee "$workspace/out/logs/bringup-userspace.log") 2>&1
make -C "$source_dir" O="$output" CROSS_COMPILE="$cross" allnoconfig
"$kernel/scripts/config" --file "$output/.config" \
    -e STATIC -e LONG_OPTS -e SHOW_USAGE -e FEATURE_VERBOSE_USAGE \
    -e LFS -e BUSYBOX -e FEATURE_INSTALLER -e SH_IS_ASH -e ASH \
    -e ASH_JOB_CONTROL -e ASH_ALIAS -e ASH_ECHO -e ASH_PRINTF -e ASH_TEST \
    -e ASH_CMDCMD -e ASH_OPTIMIZE_FOR_SIZE -e ASH_INTERNAL_GLOB \
    -e FEATURE_SH_STANDALONE -e FEATURE_SH_NOFORK \
    -e CAT -e CHMOD -e CP -e DATE -e DD -e DF -e DMESG -e ECHO -e FALSE \
    -e GREP -e HEAD -e LS -e MKDIR -e MKNOD -e MOUNT -e FEATURE_MOUNT_FLAGS -e FEATURE_MOUNT_LOOP \
    -e MV -e LN -e READLINK -e RM -e SLEEP -e SYNC -e TAIL -e TEE -e TEST \
    -e TRUE -e UMOUNT -e UNAME -e WC -e POWEROFF -e REBOOT -e FEATURE_CALL_TELINIT \
    -e CTTYHACK -e SETSID -e PS -e FREE -e FIND -e READLINK -e SHA256SUM \
    -e INSMOD -e LSMOD
make -C "$source_dir" O="$output" CROSS_COMPILE="$cross" oldconfig </dev/null
make -C "$source_dir" O="$output" CROSS_COMPILE="$cross" -j"${JOBS:-16}"
install -m 0755 "$output/busybox" "$workspace/out/bringup-bin/busybox"
headers="$workspace/out/probe-headers"
mkdir -p "$headers/linux/android"
# These two UAPI-only headers use the compiler sysroot's linux/types.h.
# Do not add the entire raw kernel include tree to userspace include paths.
install -m 0644 "$kernel/include/uapi/linux/android/binder.h" "$headers/linux/android/binder.h"
install -m 0644 "$kernel/drivers/staging/android/uapi/ashmem.h" "$headers/ashmem.h"
"${cross}gcc" -static -O2 -Wall -Wextra -Werror \
    -I "$headers" \
    "$workspace/bringup/probes/kernel-probe.c" -o "$workspace/out/bringup-bin/kernel-probe"
python3 "$workspace/scripts/gen-gpio-map.py" \
    "$workspace/config/gpio/rdk_x5_40pin.json" \
    "$workspace/out/bringup-bin/rdk_x5_40pin.tsv"
"${cross}gcc" -static -O2 -Wall -Wextra -Werror \
    "$workspace/bringup/gpio/rdkhm-gpio.c" -o "$workspace/out/bringup-bin/rdkhm-gpio"
"${cross}gcc" -static -O2 -Wall -Wextra -Werror \
    "$workspace/bringup/gpio/rdkhm-gpio-daemon.c" -o "$workspace/out/bringup-bin/rdkhm-gpio-daemon"
