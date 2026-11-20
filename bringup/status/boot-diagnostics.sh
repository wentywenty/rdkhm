#!/rdkhm/busybox sh
# Read-only boot report. It never loads modules, changes networking, or opens devices.
bb=/rdkhm/busybox
dir=/data/rdkhm-logs
out=$dir/boot-status.txt
umask 077
$bb mkdir -p "$dir" || exit 1
$bb sleep 20
{
    echo "RDKHM_BOOT_DIAGNOSTICS_BEGIN"
    date 2>/dev/null || true
    $bb cat /proc/uptime /proc/cmdline 2>/dev/null || true
    for script in hardware-status.sh screen-status.sh audio-status.sh system-security-status.sh hdmi-status.sh touch-status.sh camera-codec-status.sh ws73-probe.sh; do
        path=/rdkhm/$script
        [ -x "$path" ] || continue
        echo "--- $script ---"
        "$path" 2>&1 || echo "$script exit=$?"
    done
    echo "RDKHM_BOOT_DIAGNOSTICS_END"
} >"$out"
$bb sync
echo "RDKHM: boot diagnostics saved to $out" >/dev/console
