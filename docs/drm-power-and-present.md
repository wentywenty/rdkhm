# DRM power and first-frame submission

The board now reports HDMI connected and enabled, but the panel stays black.
The attached early hilog establishes a 1920x1080 physical screen, followed by
`drmModeAtomicCommit failed -22 errno 22`, failed attempts to open
`/dev/graphics/fb0`, and three early `PreProcessLayersComp` errors with code -3.
Source inspection maps -3 to an empty layer map, not an allocator failure.
The later kernel-only `bsp/log` contains service restart and audit messages,
not enough information to determine why application layers are absent.

Patch `display/0004-drm-power-and-present.patch` makes these corrections:

- X5 display power uses the connector's DRM DPMS API, with the existing checked
  HDI-to-DRM state conversion. The X5 kernel implements legacy DPMS property
  changes through `drm_atomic_connector_commit_dpms`; no fbdev node is required.
- Mode, connector, active state and primary framebuffer share one atomic
  request. Modeset commits are synchronous; subsequent frames may be nonblocking.
  ALLOW_MODESET permits the initial activation and backend-required transitions.
- Pending mode state clears only after a successful commit. Invalid blobs and
  failed allocations/commits return errors, and atomic requests use RAII cleanup.
- The output fence storage uses the signed 32-bit type expected by DRM.
- First-frame submission failures propagate to display discovery, so a failed
  display is not announced as successfully initialized.
- The VSync worker's running flag is initialized before its thread starts,
  removing a race in which the thread could see its exit condition immediately.

`tests/test-drm-present.py` compiles the actual composition source with mocked
DRM objects and checks first-frame atomicity, subsequent flips, commit failures,
retry, invalid mode blobs and request allocation failures. These tests do not
validate physical HDMI timing, the real DPMS ioctl, or application rendering.
The previous eight encoder-selection tests remain relevant.

No fabricated success return or placeholder application layer is introduced.
The exact reason for the kernel's EINVAL and whether empty layers persist after
successful startup still require a new board capture. If black remains, inspect
current compositor/bootanimation errors and DRM state, rather than interpreting
the enabled connector as proof of a displayed frame.

Validation on 2026-11-16: the ARM64 images target and final VSync incremental
build both succeeded. Six mocked presentation cases and eight CRTC selection
cases passed. SD verification passed all 38 required exports, 134 packaged
artifact comparisons, MBR, checksum and four filesystems. Logs are
`out/logs/build-drm-present.log`, `out/logs/build-drm-present-final.log` and
`out/logs/image-drm-present.log`. The SD image SHA256 is
`37c179d364895daf8894fd9e9e7f4ca5b9ab5480dc5d51da7fe9fe5a3baa4ff1`.
This image has not yet been tested on the X5.
