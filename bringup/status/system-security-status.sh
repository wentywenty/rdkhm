#!/rdkhm/busybox sh
# Read-only post-boot audit. It never changes SELinux mode, services, or USB.
bb=/rdkhm/busybox
PATH=/rdkhm:/system/bin:/vendor/bin
export PATH
say() { echo "RDKHM_SECURITY: $*"; }
has() { command -v "$1" >/dev/null 2>&1; }

say "BEGIN"
if [ -r /sys/fs/selinux/enforce ]; then
    say "SELINUX_ENFORCE=$($bb cat /sys/fs/selinux/enforce 2>/dev/null || echo unreadable)"
else
    say "SELINUX_ENFORCE=not-mounted"
fi
if [ -r /sys/fs/selinux/policy ]; then
    say "SELINUX_POLICY=present"
else
    say "SELINUX_POLICY=not-visible"
fi
if [ -r /proc/cmdline ]; then
    cmdline=$($bb cat /proc/cmdline)
    case " $cmdline " in
        *" enforcing=1 "*) say "CMDLINE_ENFORCING=1" ;;
        *" enforcing=0 "*) say "CMDLINE_ENFORCING=0" ;;
        *) say "CMDLINE_ENFORCING=default" ;;
    esac
    case " $cmdline " in
        *" selinux=0 "*) say "CMDLINE_SELINUX=0" ;;
        *) say "CMDLINE_SELINUX=1-or-default" ;;
    esac
fi

for path in /dev/access_token_id /dev/binder /dev/hwbinder /dev/vndbinder \
            /dev/galcore /dev/bpu /dev/hdf_kevent /dev/usb-ffs/hdc/ep0; do
    if [ -e "$path" ]; then
        say "NODE_PRESENT=$path"
        if has ls; then $bb ls -l "$path" 2>/dev/null | sed 's/^/RDKHM_SECURITY: NODE_STAT=/' ; fi
    else
        say "NODE_MISSING=$path"
    fi
done

if has ps; then
    for name in init appspawn hdcd render_service samgr rdkhm-accelerator; do
        if $bb ps -A 2>/dev/null | $bb grep -v grep | $bb grep -q "$name"; then
            say "SERVICE_PROCESS=$name:present"
        else
            say "SERVICE_PROCESS=$name:missing"
        fi
    done
fi
if [ -r /proc/net/tcp ]; then
    if $bb grep -q ':15B3 ' /proc/net/tcp 2>/dev/null; then
        say "HDC_TCP_5555=LISTENING"
    else
        say "HDC_TCP_5555=not-listening"
    fi
fi

for log in /data/rdkhm-logs/hilog-current.txt /data/rdkhm-logs/hilog-previous.txt; do
    [ -r "$log" ] || continue
    say "LOG=$log"
    avc=$($bb grep -c 'avc:.*denied' "$log" 2>/dev/null || echo 0)
    fail=$($bb grep -ciE 'startup.*(fail|error)|service.*(fail|crash)|critical.*(restart|reboot)' "$log" 2>/dev/null || echo 0)
    say "AVC_DENIED_COUNT=$avc"
    say "STARTUP_FAILURE_MATCHES=$fail"
done
say "NOTE=This is an inventory and log summary; enforcing and hardware behavior require a cold-boot board test."
say "END"
