# HDMI CRTC selection correction

The follow-up board capture shows HDMI-A-1 connected, 256 EDID bytes and valid
1080p modes, but the connector remains disabled. Composer and RenderService
report ready while DMS has no default screen. At 26.275 seconds, composer logs
`can not find crtc for id 0`, `have no crtc 2`, and
`can not pick a crtc for connector`.

The default VDI encoder selector compares `possible_crtcs` to a single pipe bit
using equality. This field is a bitmask of allowed CRTC indices, not a single
CRTC choice or an object ID. With no active CRTC and multiple allowed bits,
the equality test rejects every candidate. The same comparison exists in the
connector hotplug path. Patch `display/0003-crtc-mask-selection.patch` changes
both comparisons to bit membership checks using an unsigned shift.

`tests/test-drm-encoder.py` compiles the actual encoder implementation and header
against mocked DRM resource types, then exercises eight cases: multiple allowed
pipes at cold boot, each single pipe, a busy first pipe, reuse of the current
CRTC, no allowed pipes, unavailable pipe indices, and all pipes busy. It does
not simulate kernel ioctls or the connector hotplug implementation.

The source bug matches the board's failure path; the capture does not print the
actual mask value. Validation on the board must still establish that a default
screen is created, HDMI becomes enabled, and a visible frame is produced.
The same capture shows audio_server SIGSEGV/restart failures, which are a
separate unresolved issue.

The incremental ARM64 `images` target completed successfully. SD verification
passed all 38 required composer exports, the MBR and checksum, four filesystems,
and 134 packaged artifact comparisons. Logs: `out/logs/build-crtc-mask.log` and
`out/logs/image-crtc-mask.log`. The rebuilt SD image SHA256 is
`407b4686fcb08c0eae1838c479bdb7a0684a21620dc71c58e96f536009736b83`.
