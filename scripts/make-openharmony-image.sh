#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"

usage() {
    cat <<'EOF'
Usage: make-openharmony-image.sh [OPTIONS] [IMAGES_DIR]

Default: assemble out/images/rdkhm-x5-openharmony-dev.img from IMAGES_DIR.

Options:
  --partitions-only   Prepare flashable partitions under out/fastboot/ and
                      skip CONFIG/MBR/whole-disk assembly.
  --only NAME         With --partitions-only, prepare only NAME
                      (system|vendor|userdata). Repeatable or comma-separated.
                      Implies --partitions-only.
  --no-sparse         Do not create Android sparse .simg copies.
  -h, --help          Show this help.

IMAGES_DIR defaults to the OpenHarmony phone images directory.
EOF
}

partitions_only=0
sparse=1
only_names=""
images=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --partitions-only) partitions_only=1; shift ;;
        --no-sparse) sparse=0; shift ;;
        --only)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            only_names+=" ${2//,/ }"; partitions_only=1; shift 2 ;;
        --only=*)
            only_names+=" ${1#*=}"; only_names=${only_names//,/ }; partitions_only=1; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)
            [[ -z "$images" ]] || { echo "Unexpected argument: $1" >&2; exit 2; }
            images=$1; shift ;;
    esac
done
images=${images:-$RDKHM_OH_TREE/out/rdk_x5/packages/phone/images}
kernel="$workspace/out/kernel/obj/arch/arm64/boot"

if [[ -n "$only_names" ]]; then
    for name in $only_names; do
        case "$name" in
            system|vendor|userdata) ;;
            *) echo "Unknown --only target: $name" >&2; exit 2 ;;
        esac
    done
elif [[ $partitions_only -eq 1 ]]; then
    only_names=" system vendor"
fi
want() { [[ " $only_names " == *" $1 "* ]]; }

required=()
if [[ $partitions_only -eq 0 ]]; then
    required+=("$images/system.img" "$images/vendor.img" "$images/userdata.img"
               "$kernel/Image" "$workspace/out/kernel/obj/.config"
               "$workspace/out/bringup-bin/busybox")
else
    # Offsets for vendor need the assembled system size.
    required+=("$images/system.img" "$images/vendor.img")
    if want system; then
        required+=("$kernel/Image" "$workspace/out/bringup-bin/busybox")
    fi
    if want vendor; then
        required+=("$kernel/Image" "$workspace/out/kernel/obj/.config")
    fi
    if want userdata; then
        required+=("$images/userdata.img")
    fi
fi
for file in "${required[@]}"; do
    [[ -f "$file" ]] || { echo "Missing $file; finish the full userspace build first" >&2; exit 1; }
done

tools=(debugfs e2fsck)
if [[ $partitions_only -eq 0 ]] || want system; then
    tools+=(resize2fs mkimage)
fi
if [[ $partitions_only -eq 0 ]]; then
    tools+=(sfdisk mkfs.vfat mcopy)
fi
for tool in "${tools[@]}"; do
    command -v "$tool" >/dev/null
done

image_bytes() {
    python3 - "$1" <<'PY'
import os
import struct
import sys

path = sys.argv[1]
with open(path, "rb") as stream:
    header = stream.read(28)
if len(header) >= 20 and struct.unpack("<I", header[:4])[0] == 0xed26ff3a:
    block_size, total_blocks = struct.unpack("<II", header[12:20])
    print(block_size * total_blocks)
else:
    print(os.path.getsize(path))
PY
}

system_bytes=$(image_bytes "$images/system.img")
system_mib=$(( (system_bytes + 1048575) / 1048576 + 256 ))
system_sectors=$(( system_mib * 2048 ))
vendor_sectors=$(( $(image_bytes "$images/vendor.img") / 512 ))
vendor_start=$(( (532480 + system_sectors + 8191) / 8192 * 8192 ))
data_sectors=""
data_start=""
if [[ -f "$images/userdata.img" ]]; then
    data_sectors=$(( $(image_bytes "$images/userdata.img") / 512 ))
    data_start=$(( (vendor_start + vendor_sectors + 8191) / 8192 * 8192 ))
fi

mkdir -p "$workspace/out/images"
stage=$(mktemp -d "$workspace/out/images/.openharmony.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT

stage_partition() {
    local name=$1
    if [[ ! -f "$images/$name.img" ]]; then
        [[ ! -d "$images/../$name" ]] || {
            echo "Missing image for staged partition $name" >&2; exit 1;
        }
        return 0
    fi
    # Android sparse and raw ext4 images both occur in upstream build outputs.
    local magic
    magic=$(od -An -tx4 -N4 "$images/$name.img" | tr -d ' ')
    if [[ "$magic" == ed26ff3a ]]; then
        simg2img "$images/$name.img" "$stage/$name.img"
    else
        cp --reflink=auto --sparse=always "$images/$name.img" "$stage/$name.img"
    fi
    e2fsck -fn "$stage/$name.img"
}

stage_names=""
if [[ $partitions_only -eq 0 ]]; then
    stage_names="system vendor userdata sys_prod chip_prod eng_system eng_chipset"
else
    if want system; then
        stage_names+=" system sys_prod chip_prod eng_system eng_chipset"
    fi
    if want vendor; then
        stage_names+=" vendor"
    fi
    if want userdata; then
        stage_names+=" userdata"
    fi
fi
for name in $stage_names; do
    stage_partition "$name"
done

# The buffer HDI service dlopen's the generic VDI by its short name; the
# upstream build installs it only under vendor/lib64/chipset-sdk.
inject_into() {
    local image=$1 source=$2 path=$3 mode=$4
    debugfs -w -R "rm $path" "$image" >/dev/null 2>&1 || true
    debugfs -w -R "write $source $path" "$image"
    debugfs -w -R "set_inode_field $path uid 0" "$image"
    debugfs -w -R "set_inode_field $path gid 0" "$image"
    debugfs -w -R "set_inode_field $path mode $mode" "$image"
    debugfs -R "dump $path $stage/injected" "$image"
    cmp "$source" "$stage/injected"
    rm "$stage/injected"
}

if [[ -f "$stage/vendor.img" ]]; then
    vendor_pkg="$(dirname "$images")/vendor"
    buffer_vdi="$vendor_pkg/lib64/chipset-sdk/libdisplay_buffer_vdi_impl_default.z.so"
    [[ -f "$buffer_vdi" ]] || { echo "Missing default buffer VDI: $buffer_vdi" >&2; exit 1; }
    for name in libdisplay_buffer_vdi_impl_default.z.so libdisplay_buffer_vdi_impl.z.so; do
        inject_into "$stage/vendor.img" "$buffer_vdi" "/lib64/$name" 0100644
    done
    composer_vdi="$workspace/sources/oh/openharmony-full/out/rdk_x5/hdf/drivers_peripheral_display/libdisplay_composer_vdi_impl_default.z.so"
    [[ -f "$composer_vdi" ]] || { echo "Missing composed composer VDI: $composer_vdi" >&2; exit 1; }
    inject_into "$stage/vendor.img" "$composer_vdi" "/lib64/libdisplay_composer_vdi_impl_default.z.so" 0100644
    python3 "$workspace/scripts/inject-driver-bundle.py" "$stage/vendor.img"
    e2fsck -fn "$stage/vendor.img"
fi

if [[ -f "$stage/system.img" ]]; then
    # Preserve upstream ownership, capabilities and labels by extending its image.
    truncate -s "${system_mib}M" "$stage/system.img"
    resize2fs "$stage/system.img"
    mkimage -C none -A arm -T script -d "$workspace/bringup/boot/openharmony-boot.cmd" "$stage/boot.scr"
    debugfs -w -R 'mkdir /boot' "$stage/system.img"
    debugfs -w -R 'mkdir /boot/hobot' "$stage/system.img"
    debugfs -w -R 'mkdir /rdkhm' "$stage/system.img"
    debugfs -w -R 'mkdir /system/etc/bootanimation' "$stage/system.img" || true
    inject() {
        debugfs -w -R "rm $2" "$stage/system.img" >/dev/null 2>&1 || true
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
    inject "$workspace/bringup/boot/openharmony-init" /rdkhm/init 0100755
    inject "$workspace/bringup/boot/load-drivers.sh" /rdkhm/load-drivers.sh 0100755
    inject "$workspace/bringup/status/hdmi-status.sh" /rdkhm/hdmi-status.sh 0100755
    inject "$workspace/bringup/status/touch-status.sh" /rdkhm/touch-status.sh 0100755
    inject "$workspace/bringup/status/camera-codec-status.sh" /rdkhm/camera-codec-status.sh 0100755
    inject "$workspace/bringup/status/hardware-status.sh" /rdkhm/hardware-status.sh 0100755
    inject "$workspace/bringup/status/boot-diagnostics.sh" /rdkhm/boot-diagnostics.sh 0100755
    inject "$workspace/bringup/status/capture-hilog.sh" /rdkhm/capture-hilog.sh 0100755
    inject "$workspace/bringup/network/rdkhm-bluetooth-init.sh" /rdkhm/bluetooth-init.sh 0100755
    inject "$workspace/bringup/network/rdkhm-ws73-probe.sh" /rdkhm/ws73-probe.sh 0100755
    inject "$workspace/bringup/status/system-security-status.sh" /rdkhm/system-security-status.sh 0100755
    inject "$workspace/bringup/status/screen-status.sh" /rdkhm/screen-status.sh 0100755
    inject "$workspace/bringup/status/audio-status.sh" /rdkhm/audio-status.sh 0100755
    inject "$workspace/overlay/vendor/drobotics/rdk_x5/ams_extension_config.json" \
        /system/etc/ams_extension_config.json 0100644
    inject "$workspace/overlay/vendor/drobotics/rdk_x5/bootanimation/bootanimation_custom_config.json" \
        /system/etc/bootanimation/bootanimation_custom_config.json 0100644
    inject "$workspace/out/bringup-bin/busybox" /rdkhm/busybox 0100755
    inject "$workspace/out/bringup-bin/rdkhm-gpio" /rdkhm/gpio 0100755
    inject "$workspace/out/bringup-bin/rdkhm-gpio-daemon" /rdkhm/gpio-daemon 0100755
    inject "$workspace/out/bringup-bin/rdkhm-sle-daemon" /rdkhm/sle-daemon 0100755
    inject "$workspace/out/bringup-bin/rdk_x5_40pin.tsv" /rdkhm/rdk_x5_40pin.tsv 0100644
    inject "$workspace/bringup/gpio/gpio-status.sh" /rdkhm/gpio-status.sh 0100755
    # Settings carries the GPU composition developer option. Build it from the
    # patched source during image assembly so the image never picks up a stale
    # prebuilt. Set RDKHM_SKIP_SETTINGS_HAP=1 only for offline re-assembly.
    if [[ "${RDKHM_SKIP_SETTINGS_HAP:-0}" != "1" ]]; then
        python3 "$workspace/scripts/build-hap.py" settings
    fi
    # Locally built HAPs replace their upstream counterparts through one
    # manifest (config/build/haps.json "image") shared with the verifier.
    # Optional artifacts (PinTool) are skipped when absent; a missing required
    # HAP aborts assembly instead of silently keeping the stale prebuilt.
    hap_tsv=$(python3 "$workspace/scripts/image_haps.py" --tsv)
    while IFS=$'\t' read -r hap_source hap_dest; do
        [[ -n "$hap_source" ]] || continue
        debugfs -w -R "mkdir ${hap_dest%/*}" "$stage/system.img" >/dev/null 2>&1 || true
        inject "$workspace/$hap_source" "$hap_dest" 0100644
    done <<< "$hap_tsv"

    # Preinstall trust lists must match the signer of every injected HAP.
    # They are injected here so an allowlist change does not require a full
    # OpenHarmony rebuild to take effect.
    preinstall="$workspace/overlay/vendor/drobotics/rdk_x5/preinstall-config"
    for name in install_list.json install_list_capability.json \
                install_list_permissions.json uninstall_list.json; do
        [[ -f "$preinstall/$name" ]] || continue
        inject "$preinstall/$name" "/system/etc/app/$name" 0100644
    done
    for name in sys_prod chip_prod eng_system eng_chipset; do
        [[ -f "$stage/$name.img" ]] || continue
        inject "$stage/$name.img" "/rdkhm/$name.img" 0100644
    done
    e2fsck -fn "$stage/system.img"
fi

if [[ $partitions_only -eq 1 ]]; then
    out="$workspace/out/fastboot"
    mkdir -p "$out"
    for name in $only_names; do
        rm -f "$out/$name.img" "$out/$name.simg"
    done
    emit() {
        local name=$1
        [[ -f "$stage/$name.img" ]] || return 0
        cp --reflink=auto --sparse=always "$stage/$name.img" "$out/$name.img"
        if [[ $sparse -eq 1 ]] && command -v img2simg >/dev/null 2>&1; then
            if ! img2simg "$out/$name.img" "$out/$name.simg"; then
                rm -f "$out/$name.simg"
                echo "WARN: sparse conversion failed for $name; use $out/$name.img" >&2
            fi
        fi
        sha256sum "$out/$name.img" | sed "s#$workspace/##"
    }
    if want system; then emit system; fi
    if want vendor; then emit vendor; fi
    if want userdata; then emit userdata; fi

    python3 - "$out/partitions.json" "$system_sectors" "$vendor_start" "$vendor_sectors" \
        "${data_start:-0}" "${data_sectors:-0}" <<'PY'
import json
import sys

path, system_sectors, vendor_start, vendor_sectors, data_start, data_sectors = sys.argv[1:]
data = {
    "unit": "sectors",
    "sectorsize": 512,
    "partitions": {
        "config": {"start": 8192, "sectors": 524288},
        "system": {"start": 532480, "sectors": int(system_sectors)},
        "vendor": {"start": int(vendor_start), "sectors": int(vendor_sectors)},
    },
}
if int(data_sectors):
    data["partitions"]["userdata"] = {"start": int(data_start), "sectors": int(data_sectors)}
open(path, "w").write(json.dumps(data, indent=2) + "\n")
PY

    {
        echo "# Paste into the U-Boot console, then: fastboot -t emmc -m 0 usb 0"
        printf 'setenv fastboot_raw_partition_system "0x%x 0x%x"\n' 532480 "$system_sectors"
        printf 'setenv fastboot_raw_partition_vendor "0x%x 0x%x"\n' "$vendor_start" "$vendor_sectors"
        if [[ -n "$data_sectors" ]]; then
            printf 'setenv fastboot_raw_partition_userdata "0x%x 0x%x"\n' "$data_start" "$data_sectors"
        fi
    } | tee "$out/fastboot-uboot.cmd"

    echo
    for name in system vendor userdata; do
        [[ -f "$out/$name.img" ]] || continue
        file="$out/$name.simg"
        [[ -f "$file" ]] || file="$out/$name.img"
        echo "  fastboot flash $name $file"
    done
    echo "Partitions written to $out"
    exit 0
fi

truncate -s 256M "$stage/config.img"
mkfs.vfat -F 32 -s 4 -n CONFIG "$stage/config.img"
mcopy -i "$stage/config.img" "$workspace/STATUS.md" ::STATUS.txt
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
