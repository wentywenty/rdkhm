#!/system/bin/sh
# Read-only discovery; does not grab the input device or inject events.
BB=/rdkhm/busybox
echo '=== Input devices and handlers ==='
$BB cat /proc/bus/input/devices
echo '=== Input node permissions ==='
$BB ls -l /dev/input
echo '=== Event capabilities ==='
for dev in /sys/class/input/event*; do
    [ -d "$dev" ] || continue
    echo "$dev"
    for field in name id/vendor id/product capabilities/ev capabilities/abs properties; do
        echo "$field:"
        $BB cat "$dev/device/$field"
    done
done
echo '=== Input services ==='
$BB ps -A | $BB grep -E 'mmi|input|hdf'
echo 'Enumeration does not prove touch events or application delivery.'
