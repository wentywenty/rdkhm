#!/rdkhm/busybox sh
# Read-only audio inventory. It does not open PCM devices or change routing.
set -u
BB=${RDKHM_BUSYBOX:-/rdkhm/busybox}
PATH=/rdkhm:/system/bin:/vendor/bin
export PATH
say() { printf '%s\n' "$*"; }

say 'RDKHM_AUDIO_STATUS_V1'
say '--- ALSA cards ---'
cat /proc/asound/cards 2>/dev/null || say 'no /proc/asound/cards'
say '--- ALSA PCM ---'
cat /proc/asound/pcm 2>/dev/null || say 'no /proc/asound/pcm'
say '--- Device nodes ---'
ls -l /dev/snd 2>/dev/null || say 'no /dev/snd'
say '--- Audio services ---'
ps -A 2>/dev/null | grep -E 'audio|pulse|hdf' || true
say '--- HDF/config ---'
for f in /vendor/etc/hdfconfig/audio_adapter.json \
         /vendor/etc/hdfconfig/alsa_adapter.json \
         /vendor/etc/audio/audio_policy_config.xml \
         /vendor/etc/audio/alsa/share/alsa.conf; do
    [ -e "$f" ] && say "PRESENT $f" || say "ABSENT $f"
done
say 'Presence does not prove playback, capture or routing.'
say 'RDKHM_AUDIO_STATUS_END'
