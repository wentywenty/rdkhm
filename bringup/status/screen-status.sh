#!/rdkhm/busybox sh
# Read-only display/power/RS inventory. --capture writes JPEG and UI layout
# under /data/rdkhm-logs; it does not change display power or modes.
set -u

BB=${RDKHM_BUSYBOX:-/rdkhm/busybox}
PATH=/rdkhm:/system/bin:/vendor/bin
export PATH
say() { printf '%s\n' "$*"; }

say 'RDKHM_SCREEN_STATUS_V1'
say '--- HDMI connector ---'
/rdkhm/hdmi-status.sh 2>&1 || true
say '--- RenderService screen ---'
hidumper -s RenderService -a "screen" 2>&1 | sed -n '1,12p'
say '--- PowerManager state ---'
hidumper -s PowerManagerService -a "-s" 2>&1 | sed -n '1,12p'
say '--- DisplayPowerManager ---'
hidumper -s DisplayPowerManagerService -a "-a" 2>&1 | sed -n '1,12p'
say '--- RenderService screen/layer summary ---'
hidumper -s RenderService -a "allInfo" 2>&1 | grep -E "ScreenLockWindow|FrameBufferSurface|BufferQueue|usedBufferListLen|default-size|powerStatus|PreProcessLayersComp|layerIdMap" | sed -n '1,40p'
say '--- Display/window services ---'
ps -A 2>/dev/null | grep -E 'render_service|composer_host|systemui|launcher|powermgr|display' || true

if [ "${1:-}" = "--capture" ]; then
    "$BB" mkdir -p /data/rdkhm-logs || exit 1
    # Capture is explicitly state-changing: wake the panel and extend timeout.
    power-shell wakeup >/dev/null 2>&1 || true
    power-shell timeout 600000 >/dev/null 2>&1 || true
    sleep 1
    # snapshot_display restricts its output path to /data/local/tmp.
    snapshot_display -i 0 -f /data/local/tmp/rdkhm-screen.jpeg >/dev/null 2>&1 &&
        "$BB" cp /data/local/tmp/rdkhm-screen.jpeg /data/rdkhm-logs/screen.jpeg &&
        say 'CAPTURE /data/rdkhm-logs/screen.jpeg'
    uitest dumpLayout -p /data/rdkhm-logs/layout.json >/dev/null 2>&1 &&
        say 'CAPTURE /data/rdkhm-logs/layout.json'
fi
say 'RDKHM_SCREEN_STATUS_END'
