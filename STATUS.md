# RDKHM status - 2026-11-19

## Current state (2026-11-19)

The 2026-11-19 20:54 image includes the USB HDC and CAN-FD fixes; the source
tree still has uncommitted documentation and HAP work. The sections below are
the 2026-11-17 session and earlier history unless explicitly marked as 2026-11-19.
See [board-validation-20261119.md](docs/board-validation-20261119.md).

### 2026-11-20 SLE userspace probe

- 2026-11-21 Launcher persistence: Beta1 `Launcher_Settings.hap` was copied into
  `/system/app/com.ohos.launcher/` (backup in `/data/local/tmp/*.recovery.old`).
  After reboot `boot_id=07c25a60-5171-4cc0-99f2-d30e6e8b2da7`, `account.ready=true`,
  Launcher bundle registered and Settings opens. Initial cold-boot frame is still
  black because `bootanimation` remains; killing it and restarting Launcher shows
  the desktop. Evidence: `out/board-logs/20261121-launcher-persist/`.
- 2026-11-20 17:22 hmdfs test image: `rdkhm-x5-openharmony-dev.img`
  SHA256 `7948f022b3073c8ec1688c57774dafd512c78572ae8432ec48f16ea8162329c8`;
  `const.distributed_file_property.enabled=true` and current kernel Image
  (`6e6cb22c...`) are inside the image. The vendor partition was manually
  resynced with the current driver bundle. Full verifier currently stops at
  `/system/lib64/libaccountmgr.z.so` because concurrent builds changed the
  packaged artifact after image assembly; image is **not fully verified and
  not flashed**.
- 2026-11-20 13:00 full image: `rdkhm-x5-openharmony-dev.img`
  SHA256 `a8248fa2c812f2b5c6819488587a21d152ca3f1703d4abafcd192e506a83500c`;
  built from the new kernel Image (`15187353...`) and all OH images. Verification
  passed (MBR, four filesystems, 224 artifact comparisons). The final system
  partition contains `/boot/Image` `15187353...`; vendor contains `hmdfs.ko`
  `59f3c5aa...`, autoloaded first. `distributed_file_property.enabled=false`, so
  account activation uses `LocalMount`; hmdfs cold boot is still unverified and
  the image is not flashed.
- 2026-11-20 system_image rebuild: `system_image` completed successfully;
  full image `ead0919e...` passes verification with 224 artifact comparisons.
  `hmdfs.ko` is packaged under `/lib/modules/6.1.83-rdkhm/` and listed first in
  `modules.load`. The image is not flashed; hmdfs cold-boot is unverified.
- 2026-11-20 galcore DMA-BUF panic fix: `galcore` now rejects `ERR_PTR` from
  `dma_buf_attach` / `dma_buf_map_attachment` and cleans up on error. Kernel
  module and driver bundle rebuilt; image `582d2b1e...` passes verification
  (224 comparisons); the final image reuses the signed HAP set because the
  post-deps_guard HAP rebuild hit SDK API mismatches. The image is not flashed; serial cold-boot verification
  is pending. See [galcore panic record](docs/galcore-dmabuf-errptr-20261120.md).
- 2026-11-20 account foreground fallback: `GetForegroundOsAccountLocalId()`
  now falls back to the activated default account when the AMS foreground
  callback is missing. `libaccountmgr` and the image were rebuilt/injected;
  image `5e60512e...` passes verification. Not flashed; board validation
  pending. See [account foreground fallback](docs/account-foreground-fallback-20261120.md).
- All 22 HAPs were rebuilt; 25 image HAPs passed official-key verification and
  were injected. The re-signed allowlist bundles were updated to the official
  leaf fingerprint.
- Image `db0a75bb...` was assembled and verified (215 artifact comparisons);
  the board booted kernel `#6`.
- `open("/dev/hwsle")` and the SLE_OPEN handshake succeed. DLI advertising
  commands return status `0x01` (PENDING); 30 seconds of fd holding produced no
  command-complete, ACB or ICB events. Advertising is not confirmed and no
  second SLE scanner is available. See [nearlink.md](docs/nearlink.md).
- Direct `build-openharmony.sh --build-target images` requires
  `scripts/install-system-sdk-api.sh` first; `./build oh` now performs that
  step.

- Board: `10.43.9.213:5555`, model `D-Robotics RDK X5 V1.0`. The latest boot,
  after the 2026-11-19 20:54 unified image build, reports boot_id
  `9ade3a96-6eb4-4876-a3dc-f407990d6b5e` and kernel `6.1.83-rdkhm`; earlier
  hot-HAP tests used boot_id `00836ef8-c49c-4a6e-8c58-a0bf1da68998`
  (`#5`, 2026-11-19 16:13 CST).
- Board image SHA256 was not captured from the running system. The current
  local `out/images/rdkhm-x5-openharmony-dev.img.sha256` is
  `1e5d24a599d429c43e85b93cbce0cb08c3f0afc7caf3f29f23fd68b870826cf4`;
  earlier `db0a75bb...`, `4368578f...`, `883c8123...` and `8f1f4ea9...`
  references are historical.
- Current 20:54 image boot: display is black; Launcher is not running and BMS
  has no installed bundle information. SystemUI status/navigation windows
  exist, but WindowManager reports `Focus window: 0`. This boot is not yet
  validated.
- USB HDC: TCP `hdcd` works. The source `rdkhm-usb.sh` guards an
  already-mounted configfs and mounts functionfs idempotently. The 20:54
  unified image boot already created the `1d6b:0104` gadget, `ep0/ep1/ep2`,
  a high-speed `configured` UDC and hdcd USB endpoints. Host-side USB
  enumeration is still to be confirmed on the PC connected to the board.
- CAN-FD: TCAN4550 at the DT's 18 MHz SPI returns DEV_ID 0 and `m_can`
  reports `Failed to init module`. `kernel/0018-tcan-spi-max-speed.patch`
  clamps SPI to 10 MHz; classic CAN and CAN-FD loopback pass on the board,
  including a cold boot of the 20:54 image. External bus, termination and a
  second node remain unverified.
- 2026-11-19 multimedia: USB camera preview works on the hot-deployed HAP
  (`camera/0004..0006`); Photos opens an empty gallery with MediaLibraryData
  provider connected, and `/dev/fuse` + media-fuse mount were fixed on the
  board. Camera controls/photo-save are not yet verified. Details:
  [camera-media-photos-20261119.md](docs/camera-media-photos-20261119.md).
  Full patch inventory: [patch-inventory-20261119.md](docs/patch-inventory-20261119.md).
  Image build preparation (not built): [image-build-prep-20261119.md](docs/image-build-prep-20261119.md).
- Power/suspend: the image overlay now includes `rdkhm-powermgr-off`, a boot
  service that stops `powermgr` after boot to avoid suspend/HDC loss. This is
  source-only and not cold-boot tested.
- 2026-11-19 partition build: `system_image` + `vendor_image` succeeded and
  system/vendor partitions were assembled under `out/fastboot/`; a later full
  SD image build produced
  `db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78` and
  passed the image verifier. The board was not flashed. See
  `docs/image-build-prep-20261119.md`.
- HAPs: `admin_provisioning` and `theme` build and are patched under
  `patches/haps/`; `config/build/haps.json` marks them verified. Settings
  builds to `out/settings/Settings.hap`. Image assembly now injects every
  built app with a defined upstream directory through the single `image`
  manifest in `config/build/haps.json` (`scripts/image_haps.py`), including
  SystemUI, ScreenLock, Note, Contacts, MMS, CallUI and FilePicker.
  Injected HAPs must be signed by the official release key or match the
  bundle's preinstall allowlist fingerprint. The `haps` pipeline stage is
  configured to build every app in `image.apps`, plus SystemUI modules and
  PinTool, so a clean `./rdkhm run build` no longer depends on stale
  `out/haps` files. Note uses a local JSON fallback
  because the board RDB open callback does not return; the Web editor is
  unavailable. See [Note validation](docs/board-validation-20261119-note.md).
  The 20:54 image contains the matching Note HAP, but the current boot is black
  and BMS has no Launcher/Note bundles; cold-boot validation is still pending.
- 2026-11-19 HAP fixes: source-built Settings shows the NearLink entry; CallUI
  starts after strict-null/import/exported fixes; Contacts DataAbility and the
  dialer/contacts pages were board-tested. FilePicker still cannot start
  because BMS does not return the `ExternalFileManager` fileAccess extension;
  TEE remains a HiSilicon `tc_ns_client` vs X5 OP-TEE mismatch. Details and
  evidence: [hap-fixes-20261119.md](docs/hap-fixes-20261119.md).
- 2026-11-19 GPIO/PinTool: 6 gpiochips (base 347/379/411/434/466/498);
  `gpio-daemon` runs with `/dev/rdkhm-gpio.sock` and TCP `127.0.0.1:9800`;
  `/rdkhm/gpio list` and `show 7` work; Pin 7 was re-tested on the 20:54
  image with `export/set/dir/get/unexport`, all rc=0. GPIO hardening is in
  source only: CLI rejects non-usable/claimed pins, daemon defaults to socket
  `0660`, TCP off, peer credentials, SELinux `rdkhm_gpio` types and a Pintool
  capability entry. The board still runs the old 0666/TCP daemon until rebuild.
  `PinTool.hap` is present in
  `/system/app/com.rdkhm.pintool/`, but BMS does not register the bundle
  (`bm dump -n com.rdkhm.pintool` fails), so the UI cannot start on the
  current black-screen boot. `gpio-status.sh` `head -100` was fixed in source
  to `head -n 100`.
  See [gpio.md](docs/gpio.md).
- Account activation is blocked by missing `hmdfs`: the image sets
  `const.distributed_file_property.enabled=true`, but the flashed X5 kernel has no
  `hmdfs` driver. `dfs/0001-disable-hmdfs-for-bringup.patch` disables the property
  so StorageDaemon uses `LocalMount`; a rebuilt image and cold boot are required
  to confirm `account.ready=true` and user 100.
- 2026-11-20 HMDFS backport: the 6.6 `fs/hmdfs` source now compiles for 6.1.83;
  `hmdfs.ko` is staged in the driver bundle autoload list. A new kernel Image
  exports `filemap_remove_folio`. The current board is still running the old
  kernel, so `insmod` fails with `Unknown symbol filemap_remove_folio`; mount,
  `account.ready=true`, user 100 and Launcher are **not yet board-verified**.
  See [hmdfs-backport-20261120.md](docs/hmdfs-backport-20261120.md).
- RT: `RDKHM_KERNEL_PROFILE=rt` is an opt-in profile; the default remains
  non-RT and no RT kernel has been built or board-validated.

The previous 2026-11-17 and earlier records follow.

## 2026-11-17 session (historical)

The OpenHarmony 6.0 ARM64 standard-system `images` target builds successfully.
This is an experimental integration, not a board-qualified release.
Kernel #8 survived over 40 minutes before the WS73 loading experiment lost
network access. HDMI presents 800x480; touch reaches SystemUI. The previous
VBlank panic did not recur in the captured interval.

The 2026-11-17 board session (image assembled before the composer-release and
diagnostic fixes) reached HDMI connected/enabled with a 256-byte EDID, running
render_service/composer/Launcher and QDtech MPI5001 event1, but the panel
remained black. HDC TCP worked only after manually starting hdcd. See
[board-validation-20261117.md](docs/board-validation-20261117.md).
The latest image `1e5d24a599d429c43e85b93cbce0cb08c3f0afc7caf3f29f23fd68b870826cf4`
adds the composer service release export and color-gamut answer, the render-service
guards, the BusyBox-safe hardware report, optional-vendor ABI stubs (including
`libtask_controller.z.so`), tracefs mounts, PSI and RTG/QoS compatibility proc entries. It has not been flashed. A temporary live deployment of the new display libs on the running board produced a visible lock screen at 800x480; see `out/board-logs/20261118-live/screen-final.jpeg`.
The first tracing-enabled boot then panicked in `trace_event_eval_update()` while
loading `aic8800_bsp`; `patches/kernel/0008-trace-eval-null-guard.patch` adds
null guards and the kernel/image were rebuilt. The panic log is
`out/board-logs/20261118-panic/boot.log`. The `be7d715d` image booted on
<board-ip> with kernel `#13`, stubs/syscap/tracefs/PSI and audio working; the
lock screen was visible after wake (`out/board-logs/20261118-new-image/screen-lock.jpeg`).
`/proc/thread-self/sched_qos_ctrl` was still missing because `CONFIG_SCHED_DEBUG`
is off; `kernel/0009` makes that proc entry unconditional and the current
image is `1e5d24a5...` (not yet flashed).

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
- Includes 38 kernel modules and 21 pinned firmware assets. Ten modules remain
  manual-only, including WS73, Bluetooth HCI and their dependencies.
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
  descriptors. The NNRT HDI service and HCS host are enabled; the OH NNRT C API
  performs ResNet18 inference on the board (2026-11-20, hot-deployed runtime and
  bind-mounted service/stub). The 2026-11-21 image contains the same artifacts
  byte-for-byte; it has not been flashed. GPU bring-up found that `eglCreateContext`
  failed with `0x3005` because the private runtime omitted the `dlopen`ed
  `libGLSLC.so`; adding it makes offscreen pbuffer and GBM-window contexts pass
  on the current board (`Vivante GC8000L`, `OpenGL ES 3.1`). The staging script
  and asset lock now include it, but the flashed image has not been rebuilt;
  OH RenderService remains on software rendering.
- Assembles CONFIG, system, vendor and userdata partitions into a regular SD file.

Current kernel Image SHA256:
`6dff50179ba7567a892ac0cfca2dcf8f853165cc84ef5e07d167f7bad2f61833`.

## Complete-system development image

`out/images/rdkhm-x5-openharmony-dev.img` (7172 MiB).
Its companion `.img.sha256` records the checksum of the latest assembly.
The current SHA256 is
`1e5d24a599d429c43e85b93cbce0cb08c3f0afc7caf3f29f23fd68b870826cf4`
(run `out/runs/20261118T053124Z-0nkn4n3v`).
Rebuild and inspect with:

```sh
bash scripts/prepare-openharmony.sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/import-driver-firmware.py
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
- The composer release export is packaged; `RegRefreshCallback` and the HDMI
  backlight fallback are in 0002/0004. `graphic2d/0003` splits app/server
  drawable generation and the `render_service` target builds incrementally.
  No visible first frame is proven; connector state is not display acceptance.
- Upstream post-build startup guard reports service start-mode/job, DAC identity
  and init-library whitelist findings despite a successful build exit status.
  These remain to be reviewed against actual service startup.
- SELinux policy generation is enabled with an `rdkhm_accel` service domain,
  X5 galcore/BPU labels and a restricted DRM ioctl allowlist. Board AVC review
  is still required. The development boot script passes `selinux=1 enforcing=0`;
  permissive mode does not enforce access denials. Production recovery/OTA
  are not qualified. GPU/BPU
  kernel/runtime integration has started; RenderService GPU buffers/window-system
  adaptation remain incomplete. NNRT raw-offline inference is proven after a
  hot deployment; image integration is still pending.
  USB camera HDF host registration and the common provider HCS are packaged;
  `/dev/video*` and real stream tests remain board-dependent. Codec HDI/OMX
  libraries are packaged, but no X5 VPU capability table is advertised until
  the vendor userspace ABI is identified and tested.
- Wi-Fi association, USB role selection and DRM modeset/fences/hotplug need the real board.
- Audio mute/gain, headset detection, actual playback/capture and routing require
  further work. Bluetooth UART/firmware initialization remains board-specific;
  `bringup/network/rdkhm-bluetooth-init.sh` provides a guarded probe/attach entrypoint,
  but no UART path, baud rate or controller firmware protocol is asserted.
- WS73 Linux 6.1 modules compile; loading interrupted board connectivity and
  requires serial diagnosis. See `docs/nearlink.md`. SLE is not exposed as
  an IP network or HAP API.
  See `docs/drivers.md` for the per-device integration boundary.
- USB 4G/LTE: `lsusb` finds a SIMCom SIM7600G-H (`1e0e:9001`) on the
  2026-11-19 board session. `option`/`usb_wwan` and `qmi_wwan`/`cdc-wdm`/`usbnet`
  are now selected in `config/kernel/modules.json`, but the current image and
  driver bundle predate that change and were not rebuilt. The modem reported
  `SIM not inserted`; registration, `wwan0` data and RIL integration are unverified.
- Wi-Fi: the 2026-11-19 board session loaded the AIC8800D80 firmware and created
  `wlan0`, but `ifconfig wlan0 up` hit `rwnx_open ... close time out`, then
  `cmd queue crashed` and `add_if: Status Error(255)`. `kernel/0016` adds
  command-queue recovery and open-failure unwinding; it is not built or tested.
  Kernel logs for the first timeout are lost because AVC denials flood the ring.

## Earlier bring-up artifact

`out/images/rdkhm-x5-bringup-0.1.img` (516 MiB) is a frozen earlier kernel/shell
image, with no OpenHarmony desktop or services. Its SHA256 is
`d12d770b3b9fe5a1b35718b16ffb775aa1c7f58d5c28b20a3d4e6e5f4cf5d7d8`.
Its embedded kernel predates the current complete-system image.

Details: `docs/system-integration.md`, `docs/kernel-port.md`, `docs/userspace.md`.
Logs: `out/logs/`; exact source revisions: `config/sources/repo.xml` and
`out/openharmony-resolved.xml`.


The `a788c4d2` image panicked in `of_get_mac_addr()` during `hobot_gmac`
probe because the driver passed a NULL buffer to `of_get_mac_address()`.
`kernel/0011-fix-ethernet-mac-buffer.patch` changes `mac_resource.mac`
to an `ETH_ALEN` array and uses `is_zero_ether_addr()` for the fallback.
The image was rebuilt as `4368578f...`; it has not been board-tested.


The `4368578f` image adds `kernel/0013-wdt-disable-on-suspend.patch`:
`dw_wdt_suspend()` now clears the watchdog enable bit before gating clocks,
preventing a watchdog reset while the userspace watchdog daemon is frozen.
It has not been board-tested.
