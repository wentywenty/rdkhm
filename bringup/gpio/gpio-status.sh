#!/rdkhm/busybox sh
set -u

BB=${RDKHM_BUSYBOX:-/rdkhm/busybox}
PATH=/rdkhm:/system/bin:/vendor/bin
export PATH

say() { printf '%s\n' "$*"; }

say 'RDKHM_GPIO_STATUS_V1'
say '--- gpiochips ---'
for dir in /sys/class/gpio/gpiochip*; do
    [ -e "$dir" ] || continue
    say "$dir base=$(cat "$dir/base" 2>/dev/null) ngpio=$(cat "$dir/ngpio" 2>/dev/null) label=$(cat "$dir/label" 2>/dev/null)"
done

say '--- gpio service ---'
ls -l /dev/rdkhm-gpio.sock 2>/dev/null || say 'socket: missing'
ps 2>/dev/null | grep gpio-daemon | grep -v grep || say 'daemon: not running'

say '--- 40pin map (snapshot) ---'
if [ -x /rdkhm/gpio ]; then
    /rdkhm/gpio list
else
    cat /rdkhm/rdk_x5_40pin.tsv 2>/dev/null
fi

say '--- current pinmux (claimed pads) ---'
for file in /sys/kernel/debug/pinctrl/*iomuxc/pinmux-pins; do
    [ -f "$file" ] || continue
    say "== $file"
    grep '^pin ' "$file" 2>/dev/null | grep -v 'MUX UNCLAIMED' | "$BB" head -n 100
done
say 'RDKHM_GPIO_STATUS_END'
