#!/rdkhm/busybox sh
set -eu
bb=/rdkhm/busybox
export PATH=/system/bin:/vendor/bin
# Only use a controller already in device mode. Do not switch USB host ports.
while :; do
    udc=$(param get persist.rdkhm.usb.controller 2>/dev/null || true)
    udc=${udc% }
    case "$udc" in
        ''|*/*|*' '*) udc= ;;
    esac
    if [ -n "$udc" ] && [ -e "/sys/class/udc/$udc" ]; then break; fi
    set -- /sys/class/udc/*
    if [ "$#" -eq 1 ] && [ -e "$1" ]; then
        udc=${1##*/}
        break
    fi
    "$bb" sleep 2
done
g=/config/usb_gadget/g1
"$bb" mkdir -p /config /dev/usb-ffs/hdc
"$bb" mount -t configfs none /config
"$bb" mkdir -p "$g"
echo 0x1d6b > "$g/idVendor"
echo 0x0104 > "$g/idProduct"
echo 0x0200 > "$g/bcdUSB"
"$bb" mkdir -p "$g/strings/0x409"
serial=rdkhm-x5
if [ -r /proc/device-tree/serial-number ]; then
    serial=$("$bb" cat /proc/device-tree/serial-number)
fi
echo "$serial" > "$g/strings/0x409/serialnumber"
echo D-Robotics > "$g/strings/0x409/manufacturer"
echo 'RDKHM development HDC' > "$g/strings/0x409/product"
"$bb" mkdir -p "$g/functions/ffs.hdc" "$g/configs/b.1/strings/0x409"
echo 250 > "$g/configs/b.1/MaxPower"
echo 1 > "$g/os_desc/b_vendor_code"
echo MSFT100 > "$g/os_desc/qw_sign"
"$bb" ln -s "$g/configs/b.1" "$g/os_desc/b.1"
"$bb" mount -t functionfs -o uid=2000,gid=2000 hdc /dev/usb-ffs/hdc
param set sys.usb.controller "$udc"
param set sys.usb.configfs 1
param set persist.hdc.mode.tcp disable
param set sys.usb.config hdc
