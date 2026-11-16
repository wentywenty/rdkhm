#!/rdkhm/busybox sh
# Read-only connector diagnostics; never changes modes or opens a DRM master.
bb=/rdkhm/busybox
found=0
for connector in /sys/class/drm/card*-HDMI-*; do
    [ -d "$connector" ] || continue
    found=1
    echo "CONNECTOR ${connector##*/}"
    for field in status enabled modes; do
        if [ -r "$connector/$field" ]; then
            echo "$field:"
            "$bb" cat "$connector/$field"
        fi
    done
    if [ -r "$connector/edid" ]; then
        echo "EDID_BYTES $("$bb" wc -c < "$connector/edid")"
    fi
done
if [ "$found" -eq 0 ]; then
    echo 'NO_HDMI_CONNECTOR: inspect DRM driver probing and device tree'
    exit 1
fi
echo 'Connector state does not prove a visible frame or desktop startup.'
