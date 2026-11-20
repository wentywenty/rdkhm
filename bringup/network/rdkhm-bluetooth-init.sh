#!/rdkhm/busybox sh
# Board-specific Bluetooth UART mapping and baud rate must come from X5 DTS.
# Probe is deliberately read-only. Attach is an explicit operator action.
set -eu

firmware=/vendor/etc/firmware
uart=${RDKHM_BT_UART:-}
baud=${RDKHM_BT_BAUD:-}

usage() {
    echo "usage: $0 --probe | --attach <hciattach> <uart> <baud>" >&2
    exit 2
}

[ "$#" -gt 0 ] || set -- --probe
mode=probe
if [ "$1" = "--probe" ]; then
    [ "$#" -eq 1 ] || usage
elif [ "$1" = "--attach" ] && [ "$#" -eq 4 ]; then
    mode=attach
    hciattach=$2
    uart=$3
    baud=$4
else
    usage
fi

bt_firmware=0
for blob in "$firmware"/fmacfwbt_*.bin; do
    [ -f "$blob" ] || continue
    echo "BT_FIRMWARE_PRESENT: $blob"
    bt_firmware=1
done
[ "$bt_firmware" -eq 1 ] || { echo "BT_FIRMWARE_MISSING: fmacfwbt_*.bin" >&2; exit 7; }

if [ "$mode" = probe ]; then
    found=0
    for candidate in /dev/ttyS* /dev/ttyUSB* /dev/ttyACM*; do
        [ -c "$candidate" ] || continue
        echo "BT_UART_CANDIDATE: $candidate"
        found=1
    done
    if [ "$found" -eq 0 ]; then
        echo "BT_UART_CANDIDATE: none"
        echo "BT_ATTACH_BLOCKED: UART mapping is not proven by the X5 DTS"
        exit 8
    fi
    for module in hci_uart hci_uart_h4 hci_uart_h5; do
        [ -d "/sys/module/$module" ] && echo "BT_MODULE_LOADED: $module"
    done
    echo "BT_PROBE_ONLY: no UART opened and no module loaded"
    exit 0
fi

[ -n "$uart" ] || { echo "BT_UART_UNSET: set RDKHM_BT_UART from the X5 DTS" >&2; exit 3; }
[ -c "$uart" ] || { echo "BT_UART_NOT_CHAR_DEVICE: $uart" >&2; exit 4; }
[ -n "$baud" ] || { echo "BT_BAUD_UNSET: set RDKHM_BT_BAUD from the controller firmware" >&2; exit 5; }

echo "BT_UART_READY_CANDIDATE: $uart baud=$baud"
if [ "$mode" = attach ]; then
    [ -x "$hciattach" ] || { echo "HCIATTACH_NOT_FOUND: $hciattach" >&2; exit 6; }
    if [ -e /sys/class/rfkill/rfkill0/state ]; then
        printf '1\n' > /sys/class/rfkill/rfkill0/state || true
    fi
    echo "BT_ATTACH_EXPLICIT: $uart baud=$baud"
    exec "$hciattach" "$uart" any "$baud" noflow
fi
