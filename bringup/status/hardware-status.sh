#!/rdkhm/busybox sh
# Read-only X5 hardware/framework acceptance report.
# It never loads modules, opens device nodes, changes links, or starts services.
set -u

BB=${RDKHM_BUSYBOX:-/rdkhm/busybox}
[ -x "$BB" ] || BB=busybox

say() { printf '%s\n' "$*"; }
exists() { [ -e "$1" ]; }
first_node() {
    for node in "$@"; do
        [ -e "$node" ] && { printf '%s' "$node"; return 0; }
    done
    return 1
}

say 'RDKHM_HARDWARE_STATUS_V1'
say "KERNEL: $($BB uname -r 2>/dev/null || echo unknown)"
if exists /sys/fs/selinux/enforce; then
    say "SELINUX: $($BB cat /sys/fs/selinux/enforce 2>/dev/null || echo unreadable)"
else
    say 'SELINUX: unavailable'
fi

if exists /sys/class/drm/card0-HDMI-A-1/status; then
    say "HDMI_STATUS: $($BB cat /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null || echo unreadable)"
    [ -e /sys/class/drm/card0-HDMI-A-1/enabled ] &&
        say "HDMI_ENABLED: $($BB cat /sys/class/drm/card0-HDMI-A-1/enabled 2>/dev/null || echo unreadable)"
    [ -e /sys/class/drm/card0-HDMI-A-1/modes ] &&
        say "HDMI_MODES: $($BB sed -n '1p' /sys/class/drm/card0-HDMI-A-1/modes 2>/dev/null || echo none)"
else
    say 'HDMI_STATUS: connector-missing'
fi

input_count=0
for node in /dev/input/event*; do
    [ -e "$node" ] || continue
    input_count=$($BB expr "$input_count" + 1 2>/dev/null || echo "$input_count")
done
say "INPUT_EVENT_NODES: $input_count"
if exists /dev/video0 || exists /dev/video1; then
    say "CAMERA_VIDEO_NODE: $(first_node /dev/video0 /dev/video1)"
else
    say 'CAMERA_VIDEO_NODE: missing'
fi
if exists /dev/dri/card0; then say 'GPU_DRM_NODE: present'; else say 'GPU_DRM_NODE: missing'; fi
if exists /dev/galcore; then say 'GPU_GALCORE_NODE: present'; else say 'GPU_GALCORE_NODE: missing'; fi
if exists /dev/bpu || exists /dev/bpu_core0; then say 'NPU_BPU_NODE: present'; else say 'NPU_BPU_NODE: missing'; fi
if exists /dev/snd; then say 'AUDIO_NODE: present'; else say 'AUDIO_NODE: missing'; fi

for net in eth0 end0 wlan0; do
    if exists "/sys/class/net/$net"; then
        state=$($BB cat "/sys/class/net/$net/operstate" 2>/dev/null || echo unknown)
        say "NET_${net}: $state"
    fi
done
if exists /sys/class/bluetooth; then
    count=$($BB find /sys/class/bluetooth -maxdepth 1 -type l 2>/dev/null | $BB wc -l)
    say "BLUETOOTH_CONTROLLERS: $count"
else
    say 'BLUETOOTH_CONTROLLERS: 0'
fi

for module in galcore bpu_framework bpu_governor bpu_cores bpu_hw_io_x5 wifi_soc plat_soc ble_soc sle_soc hci_uart; do
    if exists "/sys/module/$module"; then say "MODULE_${module}: loaded"; else say "MODULE_${module}: absent"; fi
done

if exists /vendor/bin/rdkhm-accelerator; then
    say 'ACCELERATOR_PROBE: installed'
else
    say 'ACCELERATOR_PROBE: missing'
fi
if exists /vendor/etc/hdfconfig/camera_host_config.hcb; then
    say 'CAMERA_HDF_CONFIG: present'
else
    say 'CAMERA_HDF_CONFIG: missing'
fi
if exists /vendor/etc/hdfconfig/codec_hdi1.0_capabilities.hcb ||
   exists /vendor/etc/hdfconfig/media_codec_capabilities.hcb; then
    say 'CODEC_HDF_CAPABILITIES: present'
else
    say 'CODEC_HDF_CAPABILITIES: absent-unqualified'
fi

say 'RDKHM_HARDWARE_STATUS_END'
