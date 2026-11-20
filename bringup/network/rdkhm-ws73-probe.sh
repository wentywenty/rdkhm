#!/rdkhm/busybox sh
# Read-only WS73 USB/firmware/module probe. Never insmods or changes networking.
set -eu

firmware=/vendor/etc/firmware/ws73
found_usb=0
for id in /sys/bus/usb/devices/*; do
    [ -f "$id/idVendor" ] || continue
    vendor=$(/rdkhm/busybox cat "$id/idVendor" 2>/dev/null || true)
    product=$(/rdkhm/busybox cat "$id/idProduct" 2>/dev/null || true)
    if [ "$vendor" = ffff ] && [ "$product" = 3733 ]; then
        echo "WS73_USB_PRESENT: $id $vendor:$product"
        found_usb=1
    fi
done
[ "$found_usb" -eq 1 ] || echo "WS73_USB_PRESENT: none (expected ffff:3733)"

for module in plat_soc wifi_soc ble_soc sle_soc; do
    if [ -d "/sys/module/$module" ]; then
        echo "WS73_MODULE_LOADED: $module"
    else
        echo "WS73_MODULE_STATE: $module absent"
    fi
done

for blob in ws73.bin wifi_cali.bin btc_cali.bin wow.bin; do
    if [ -f "$firmware/$blob" ]; then
        echo "WS73_FIRMWARE_PRESENT: $firmware/$blob"
    else
        echo "WS73_FIRMWARE_MISSING: $firmware/$blob"
    fi
done
if [ -f /vendor/etc/ws73_cfg.ini ]; then
    echo "WS73_CONFIG_PRESENT: /vendor/etc/ws73_cfg.ini"
else
    echo "WS73_CONFIG_MISSING: /vendor/etc/ws73_cfg.ini"
fi
echo "WS73_PROBE_ONLY: no module loaded and no network state changed"
