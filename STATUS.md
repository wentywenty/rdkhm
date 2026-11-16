# RDKHM status - 2026-11-16

The OpenHarmony 6.0 ARM64 standard-system `images` target builds successfully.
This is an experimental integration, not a board-qualified release.
Kernel #8 survived over 40 minutes before the WS73 loading experiment lost
network access. HDMI presents 800x480; touch reaches SystemUI. The previous
VBlank panic did not recur in the captured interval.

Live fixes on 2026-11-16 established account.ready=true and
bms.main.bundles.ready=true. User 100 now has Launcher and the input method.
Launcher is READY, but the last window dump still shows the lockscreen.
The missing EL3-EL5 storage parents blocked account creation. Product init now
creates them. Empty account indexes now serialize as objects.
The audio crash was a null optional aux string; its production-function
regression passes. The corrected libraries were installed with checksum checks.
Loading the omitted designware_i2s module registered the duplex-audio card.
Playback/capture and long-running audio stability remain unverified.

All four WS73 modules build against Linux 6.1.83 using the pinned patched SDK
from roboparty_build. Live module loading lost HDC and ping access. The cause
requires serial evidence. WS73 modules are packaged for manual testing only;
they are excluded from modules.load. No successful radio operation is claimed.
See docs/boot-audio-fixes.md and docs/nearlink.md.

## Earlier bring-up history

The latest follow-up confirms Binder devices and SAMGR readiness. RenderService
then exits and its restart job resets foundation/allocator/composer, eventually
triggering the foundation critical-service reboot threshold. Bootstrap now
automatically forwards hilog warnings/errors to serial and saves at most 8 MiB
per boot in `/data/rdkhm-logs/hilog-current.txt`, retaining one previous file.
Capture runs for up to 90 seconds after the hilog socket appears, without a
terminal or HDC connection. The captured log identifies a composer VDI ABI
mismatch: the service requires C function exports, but the default VDI only
provided C++ object methods and a factory. The default VDI now exports all 38
mandatory entry points with compile-time signature checks; image verification
checks exported symbols against the service's required function list. This
follow-up board boot confirms both ready flags and running SystemUI, but HDMI
remains disabled and DMS has no default screen. Composer reports two CRTCs yet
fails to select one. The default VDI incorrectly compares a CRTC mask with one
pipe bit; patch 0003 uses bit membership in startup and hotplug selection. Eight
host regression cases pass. The next boot enables HDMI and creates a 1920x1080
screen, but the panel remains black. Patch 0004 replaces X5 fbdev power calls
with DRM DPMS, combines mode and first-frame atomic submission, propagates
startup failures, and fixes the VSync worker startup race. Mocked atomic
submission regression cases pass; visible HDMI output remains unverified.
The follow-up boot still rejects the first commit with EINVAL and correctly
leaves the connector disabled. Patch 0005 removes the invalid UINT32_MAX client
layer zpos from X5 primary-plane requests. The corrected mock reproduces the
old failure and passes the fix; physical presentation remains pending.
The latest kernel DRM trace identifies a further blocker: CRTC 62 (bt1120)
primary plane 63 rejects ARGB8888 (AR24). Patch 0006 filters X5 primary planes
and the shared startup/hotplug CRTC candidate map by ARGB8888 support, avoiding
the YUV-only pipeline. The MPI5001 USB touchscreen (0484:5750) binds to Linux
hid-multitouch and creates event1 in this capture; application event delivery
is not yet verified. `/rdkhm/touch-status.sh` collects read-only input inventory.
The input HDI now recognizes direct-touch evdev capabilities independently of
device names and reads all advertised ABS axis ranges using bitmap bit indices.

## Current integration

- Retains D-Robotics X5 Linux 6.1.83 and existing board QSPI boot firmware.
- Ports Binder token propagation, Ashmem, AccessToken and HDF core.
- Includes built-in UINPUT/UHID, FUSE, software sync and DMA-BUF heaps.
- Packages native init, appspawn, HDC, RenderService, ArkUI and system services.
- Packages same-release Launcher/SystemUI HAPs and source-built system dialogs.
- Connects DRM/GEM display allocation and client composition with CPU rendering;
  OpenGL/Vulkan, parallel rendering and graphics profiling are disabled.
- Uses Linux evdev input with the userspace input HDI backend.
- Includes board HDF/init permissions and FunctionFS HDC setup.
- Includes 33 kernel modules and 21 pinned firmware assets. Five modules remain
  manual-only, including WS73 and its additional Bluetooth dependency.
- Connects WLAN/WPA/hostapd HDF services to the Linux nl80211 backend.
- Registers the USB serial DDK service with its existing permission checks.
- Connects ES8326 ALSA playback/capture hooks, Audio HDI and primary audio policy.
- Includes an experimental native WS73 SSAP library. Four WS73 firmware blobs
  are staged under `/vendor/etc/firmware/ws73`; kernel modules now compile and
  are packaged for manual validation.
- Packages galcore, BPU framework/governor/cores and the vendor BPU hardware-I/O module.
- Packages an isolated glibc GPU/DNN runtime, a dedicated `rdkhm_accel` service
  domain and bounded GPU/NPU capability socket. QEMU can load the real vendor
  libraries and read DNN version 1.24.5; the BPU probe exposes model tensor
  descriptors. The service explicitly reports NNRT backend unavailable and
  does not claim hardware inference or rendering. It consumes the init-owned
  socket fd, while OH RenderService remains on software rendering.
- Assembles CONFIG, system, vendor and userdata partitions into a regular SD file.

Current kernel Image SHA256:
`1fcd76db579b98b135861e21acd95af02562f5f8a76b37f09449c7dfe459cf0e`.

## Complete-system development image

`out/images/rdkhm-x5-openharmony-dev.img` (7172 MiB).
Its companion `.img.sha256` records the checksum of the latest assembly.
Rebuild and inspect with:

```sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/prepare-driver-bundle.py
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

The image requires existing X5 QSPI boot firmware. It does not update QSPI.
Assembly and verification operate on regular files without mounting filesystems
or writing a physical disk. Build and offline image checks do not prove boot,
HDMI, input, HDC enumeration or HAP execution on X5.

## Remaining work

- Cold-boot validation of the latest assembled image, full Launcher window
  startup, HAP lifecycle, audio I/O and extended stability.
- Upstream post-build startup guard reports service start-mode/job, DAC identity
  and init-library whitelist findings despite a successful build exit status.
  These remain to be reviewed against actual service startup.
- SELinux policy generation is enabled with an `rdkhm_accel` service domain,
  X5 galcore/BPU labels and a restricted DRM ioctl allowlist. Board AVC review
  is still required. The development boot script passes `selinux=1 enforcing=0`;
  permissive mode does not enforce access denials. Production recovery/OTA
  are not qualified. GPU/BPU
  kernel/runtime integration has started; RenderService GPU buffers/window-system
  adaptation and executable NNRT inference remain incomplete.
  USB camera and codec HDI components are selected; provider HCS, VPU ABI and
  runtime stream tests remain outstanding.
- Wi-Fi association, USB role selection and DRM modeset/fences/hotplug need the real board.
- Audio mute/gain, headset detection, actual playback/capture and routing require
  further work. Bluetooth UART/firmware initialization remains board-specific;
  `bringup/rdkhm-bluetooth-init.sh` provides a guarded probe/attach entrypoint,
  but no UART path, baud rate or controller firmware protocol is asserted.
- WS73 Linux 6.1 modules compile; loading interrupted board connectivity and
  requires serial diagnosis. See `docs/nearlink.md`. SLE is not exposed as
  an IP network or HAP API.
  See `docs/drivers.md` for the per-device integration boundary.

## Earlier bring-up artifact

`out/images/rdkhm-x5-bringup-0.1.img` (516 MiB) is a frozen earlier kernel/shell
image, with no OpenHarmony desktop or services. Its SHA256 is
`d12d770b3b9fe5a1b35718b16ffb775aa1c7f58d5c28b20a3d4e6e5f4cf5d7d8`.
Its embedded kernel predates the current complete-system image.

Details: `docs/system-integration.md`, `docs/kernel-port.md`, `docs/userspace.md`.
Logs: `out/logs/`; exact source revisions: `sources.lock.tsv` and
`out/openharmony-resolved.xml`.
