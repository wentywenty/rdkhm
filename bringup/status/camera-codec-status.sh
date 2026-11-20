#!/system/bin/sh
# Read-only camera/codec inventory. Enumeration is not a stream or VPU proof.
BB=/rdkhm/busybox

echo '=== Video nodes ==='
nodes=0
for node in /dev/video*; do
    [ -e "$node" ] || continue
    nodes=1
    echo "$node"
    $BB ls -l "$node"
done
[ "$nodes" -eq 1 ] || echo 'NO_VIDEO_NODES: UVC/CSI kernel path is not enumerated'

echo '=== V4L2 sysfs ==='
for dev in /sys/class/video4linux/video*; do
    [ -d "$dev" ] || continue
    echo "${dev##*/}"
    for field in name dev; do
        [ -r "$dev/$field" ] && printf '%s: ' "$field" && $BB cat "$dev/$field"
    done
done

echo '=== HDF multimedia services ==='
$BB ps -A | $BB grep -E 'camera|codec|media|avcodec|hdf' || true

echo '=== HDF capability/config files ==='
for file in /vendor/etc/hdfconfig/camera_host_config.hcb \
            /vendor/etc/hdfconfig/media_codec_capabilities.hcb \
            /vendor/etc/hdfconfig/codec_hdi1.0_capabilities.hcb \
            /vendor/etc/hdfconfig/image_codec_capabilities.hcb; do
    if [ -e "$file" ]; then
        echo "PRESENT $file"
        $BB ls -l "$file"
    else
        echo "ABSENT $file"
    fi
done

echo 'Camera host registration does not prove a sensor or UVC stream.'
echo 'Codec libraries without X5 VPU capabilities do not prove hardware encode/decode.'
