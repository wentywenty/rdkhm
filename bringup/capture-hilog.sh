#!/rdkhm/busybox sh
# Capture without depending on OH service startup or an interactive console.
bb=/rdkhm/busybox
umask 077
dir=/data/rdkhm-logs
"$bb" mkdir -p "$dir" || exit 1
[ ! -f "$dir/hilog-current.txt" ] || "$bb" mv -f "$dir/hilog-current.txt" "$dir/hilog-previous.txt"
log=$dir/hilog-current.txt
: >"$log" || exit 1
echo 'RDKHM-HILOG: waiting for hilogOutput; capture saved under /data/rdkhm-logs' >/dev/console
for minute_part in 1 2 3 4 5 6; do
    for second in 1 2 3 4 5 6 7 8 9 10; do
        [ ! -S /dev/unix/socket/hilogOutput ] || break 2
        "$bb" sleep 1
    done
done
if [ ! -S /dev/unix/socket/hilogOutput ]; then
    echo 'RDKHM-HILOG: hilogOutput did not appear within 60 seconds' >/dev/console
    exit 1
fi
# Bound disk usage to 8 MiB and retain only the previous and current boot.
(
    ulimit -f 16384
    exec /system/bin/hilog -L W,E,F
) >>"$log" 2>&1 &
reader=$!
"$bb" tail -n +1 -f "$log" >/dev/console 2>&1 &
forwarder=$!
cleanup()
{
    kill "$reader" "$forwarder" 2>/dev/null
    wait "$reader" "$forwarder" 2>/dev/null
    "$bb" sync
}
trap cleanup EXIT
trap 'exit 0' TERM INT
echo 'RDKHM-HILOG: forwarding warnings/errors to serial for up to 90 seconds' >/dev/console
for interval in 1 2 3 4 5 6 7 8 9; do
    kill -0 "$reader" 2>/dev/null || break
    "$bb" sleep 10
done
echo 'RDKHM-HILOG: capture finished' >/dev/console
