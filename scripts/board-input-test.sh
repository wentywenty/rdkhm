#!/usr/bin/env bash
# Compare UI snapshots; observe mode requires a person to touch the screen.
# This changes only UI state; it does not replace services or load modules.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
hdc="$RDKHM_HDC"
[[ $# -ge 1 ]] || { echo "usage: $0 <target:port> [observe|click|swipe]" >&2; exit 2; }
target=$1
action=${2:-observe}
case "$action" in observe|click|swipe) ;; *) echo "unknown action: $action" >&2; exit 2 ;; esac
out="$workspace/out/board-logs/input-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
send() { timeout 30 "$hdc" -t "$target" file send "$1" "$2"; }
recv() { timeout 60 "$hdc" -t "$target" file recv "$1" "$2" >>"$out/transfers.txt" 2>&1 || true; }
shell() { timeout 40 "$hdc" -t "$target" shell "$1"; }

printf 'target=%s\naction=%s\nimage_sha256_user_reported=%s\n' \
    "$target" "$action" "${RDKHM_BOARD_IMAGE_SHA256:-unknown}" >"$out/session.txt"
shell 'uname -a; cat /proc/uptime /proc/sys/kernel/random/boot_id; param get const.window.scb.enabled' \
    >"$out/identity-before.txt" 2>&1
shell 'cat /proc/sys/kernel/random/boot_id' >"$out/boot-id-before.txt"
shell '/rdkhm/touch-status.sh; hidumper -s MultimodalInput -a "-l"; hidumper -s WindowManagerService -a "-a"; hidumper -s DisplayManagerService -a "-s -a"' \
    >"$out/binding-before.txt" 2>&1

send "$workspace/bringup/status/screen-status.sh" /data/local/tmp/rdkhm-screen-status.sh
shell 'chmod 755 /data/local/tmp/rdkhm-screen-status.sh'
shell '/data/local/tmp/rdkhm-screen-status.sh --capture' >"$out/before-status.txt" 2>&1
recv /data/rdkhm-logs/screen.jpeg "$out/before.jpeg"
recv /data/rdkhm-logs/layout.json "$out/before-layout.json"

case "$action" in
    observe)
        echo 'Observe for 15 seconds: physically tap/swipe the panel. Record the gesture and visible result.'
        sleep 15
        ;;
    click) shell 'uitest uiInput click 400 240' >"$out/input.txt" 2>&1 ;;
    swipe) shell 'uitest uiInput swipe 400 430 400 80 800' >"$out/input.txt" 2>&1 ;;
    *) echo "unknown action: $action" >&2; exit 2 ;;
esac
sleep 1
shell '/data/local/tmp/rdkhm-screen-status.sh --capture' >"$out/after-status.txt" 2>&1
recv /data/rdkhm-logs/screen.jpeg "$out/after.jpeg"
recv /data/rdkhm-logs/layout.json "$out/after-layout.json"
shell 'hilog -x' >"$out/hilog-after.txt" 2>&1
shell 'uname -a; cat /proc/uptime /proc/sys/kernel/random/boot_id' >"$out/identity-after.txt" 2>&1
shell 'cat /proc/sys/kernel/random/boot_id' >"$out/boot-id-after.txt"
shell 'hidumper -s MultimodalInput -a "-l"; hidumper -s WindowManagerService -a "-a"; hidumper -s DisplayManagerService -a "-s -a"' \
    >"$out/binding-after.txt" 2>&1
find "$out" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >"$out/SHA256SUMS"
echo "Saved: $out"
if ! cmp -s "$out/boot-id-before.txt" "$out/boot-id-after.txt"; then
    echo 'INVALID: board restarted during the input test' >&2
    exit 1
fi
echo 'Capture complete, not an acceptance verdict. Injection does not test USB/evdev or physical wakeup.'
