#!/rdkhm/busybox sh
bb=/rdkhm/busybox
release=$("$bb" uname -r)
directory=/vendor/lib/modules/$release
if [ ! -f "$directory/modules.load" ]; then
    echo "RDKHM: no driver bundle for $release" >/dev/console
    exit 1
fi
# Firmware exists before cfg80211 or the SDIO driver requests it.
echo /vendor/etc/firmware >/sys/module/firmware_class/parameters/path
failed=0
while IFS= read -r module; do
    [ -n "$module" ] || continue
    name=${module%.ko}
    [ -d "/sys/module/$name" ] && continue
    if ! "$bb" insmod "$directory/$module"; then
        echo "RDKHM: module load failed: $module" >/dev/console
        failed=1
    fi
done <"$directory/modules.load"
exit "$failed"
