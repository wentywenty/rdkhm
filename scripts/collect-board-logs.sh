#!/usr/bin/env bash
set -u
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
hdc="$RDKHM_HDC"
target=${1:?usage: $0 <hdc-target:port>}
output="$workspace/out/board-logs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$output"
printf '%s\n' "$output"
capture() {
    local name=$1 command=$2 status
    timeout 35 "$hdc" -t "$target" shell "$command" > "$output/$name.txt" 2>&1
    status=$?
    printf '%s\t%s\t%s\n' "$name" "$status" "$command" >> "$output/commands.tsv"
}
receive() {
    local name=$1 path=$2 status
    mkdir -p "$output/$name"
    timeout 60 "$hdc" -t "$target" file recv "$path" "$output/$name/" > "$output/transfer-$name.txt" 2>&1
    status=$?
    printf 'recv-%s\t%s\t%s\n' "$name" "$status" "$path" >> "$output/commands.tsv"
}
capture identity '/rdkhm/busybox date; /rdkhm/busybox uname -a; /rdkhm/busybox cat /proc/uptime /proc/cmdline /proc/sys/kernel/random/boot_id'
capture dmesg-start '/rdkhm/busybox dmesg'
capture hilog-start 'hilog -x'
receive startup /data/rdkhm-logs
receive faultlog /data/log/faultlog
receive reliability /data/log/reliability
receive eventlog /data/log/eventlog
receive hilog /data/log/hilog
receive all-data-log /data/log
capture log-inventory 'du -ak /data/log; /rdkhm/busybox ls -la /sys/fs/pstore'
capture parameters 'param get'
capture processes '/rdkhm/busybox ps -A; /rdkhm/busybox cat /proc/loadavg /proc/meminfo /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io'
capture mounts '/rdkhm/busybox cat /proc/mounts; /rdkhm/busybox df -h; /rdkhm/busybox cat /proc/diskstats'
capture display '/rdkhm/hdmi-status.sh; /rdkhm/busybox cat /sys/kernel/debug/dri/0/state /proc/interrupts'
capture touch '/rdkhm/touch-status.sh'
capture devices '/rdkhm/busybox ls -l /dev/dri /dev/input /dev/snd /dev/video* /dev/galcore /dev/bpu*; /rdkhm/busybox cat /proc/modules /proc/asound/cards /proc/asound/pcm; /rdkhm/busybox ls /sys/class/net /sys/class/bluetooth /sys/class/udc'
capture network '/rdkhm/busybox cat /proc/net/dev /proc/net/tcp /proc/net/tcp6 /proc/net/route /proc/net/ipv6_route; /rdkhm/busybox cat /etc/resolv.conf'
capture service-list 'hidumper -ls'
capture clusters 'hidumper -c'
capture crash-history 'hidumper -e'
capture memory 'hidumper --mem'
capture cpu 'hidumper --cpuusage'
capture frequency 'hidumper --cpufreq'
capture bundles 'bm dump -a'
capture abilities 'aa dump -a'
capture windows 'hidumper -s WindowManagerService -a "-a"'
capture screens 'hidumper -s DisplayManagerService -a "-s -a"'
capture input 'hidumper -s MultimodalInput -a "-l"'
capture boot-files '/rdkhm/busybox ls -la /data/service/el1/public /data/service/el1/public/param /data/log/faultlog/temp; /rdkhm/busybox cat /vendor/etc/rdkhm-drivers.json'
capture hilog-end 'hilog -x'
capture dmesg-end '/rdkhm/busybox dmesg'
capture identity-end '/rdkhm/busybox date; /rdkhm/busybox cat /proc/uptime /proc/sys/kernel/random/boot_id'
find "$output" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$output/SHA256SUMS"
printf 'Completed: %s\n' "$output"
