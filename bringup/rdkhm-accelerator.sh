#!/system/bin/sh
runtime=/vendor/lib64/rdkhm-accelerator
if [ "${1:-}" = --gpu ]; then
    shift
    exec "$runtime/ld-linux-aarch64.so.1" --inhibit-cache --library-path "$runtime" \
        "$runtime/gpu-probe" "$@"
fi
if [ "${1:-}" = --describe ]; then
    exec "$runtime/ld-linux-aarch64.so.1" --inhibit-cache --library-path "$runtime" \
        "$runtime/nnrt-worker" "$@"
fi
exec "$runtime/ld-linux-aarch64.so.1" --inhibit-cache --library-path "$runtime" \
    "$runtime/accelerator-probe" "$@"
