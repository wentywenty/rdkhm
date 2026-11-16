#!/rdkhm/busybox sh
# Board-specific Bluetooth UART mapping and baud rate must come from X5 DTS.
# The default path only proves that the requested endpoint and AIC firmware exist.
set -eu

firmware=/vendor/etc/firmware
uart=${RDKHM_BT_UART:-}
baud=${RDKHM_BT_BAUD:-}

usage() {
    echo "usage: $0 [--probe] | --attach <hciattach> <uart> <baud>" >&2
    exit 2
}

[ "$#" -gt 0 ] || usage
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

[ -n "$uart" ] || { echo "BT_UART_UNSET: set RDKHM_BT_UART from the X5 DTS" >&2; exit 3; }
[ -c "$uart" ] || { echo "BT_UART_NOT_CHAR_DEVICE: $uart" >&2; exit 4; }
[ -n "$baud" ] || { echo "BT_BAUD_UNSET: set RDKHM_BT_BAUD from the controller firmware" >&2; exit 5; }

bt_firmware=0
for blob in "$firmware"/fmacfwbt_*.bin; do
    [ -f "$blob" ] || continue
    echo "BT_FIRMWARE_PRESENT: $blob"
    bt_firmware=1
done
[ "$bt_firmware" -eq 1 ] || { echo "BT_FIRMWARE_MISSING: fmacfwbt_*.bin" >&2; exit 7; }

echo "BT_UART_READY_CANDIDATE: $uart baud=$baud"
if [ "$mode" = attach ]; then
    [ -x "$hciattach" ] || { echo "HCIATTACH_NOT_FOUND: $hciattach" >&2; exit 6; }
    exec "$hciattach" "$uart" any "$baud" noflow
fi
