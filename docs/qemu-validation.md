# QEMU validation plan

Status: planned, **not executed**. Written 2026-11-20.
Task split for the three separate paths: [qemu-three-paths-20261120.md](qemu-three-paths-20261120.md).
Scope: use QEMU for every check that does not require X5 hardware. The X5
image itself is not a QEMU target; see "Not verifiable under QEMU".

## Summary

| Layer | QEMU mode | What it proves | Ready now |
| --- | --- | --- | --- |
| L1 | `qemu-aarch64-static` (user mode) | our AArch64 daemons/probes run and speak their protocols | yes |
| L2 | `qemu-system-aarch64/arm -M virt` | generic OpenHarmony boots: init, samgr, IPC, hdc, hilog, framework | needs an OH product build |
| L3 | system QEMU + graphics | Launcher/SystemUI/HAP rendering | **not supported** by the products in this tree |
| — | X5 kernel/driver paths | composer, HDMI, touch, camera, audio, CAN, GPIO, WS73, BPU/GPU | **no** |

L1 gives real coverage of our own binaries. L2 gives coverage of the
OpenHarmony userspace baseline, not of the X5 port. L3 is out of scope until a
new arm64 graphics product exists.

## Host environment

Confirmed on the build host:

```sh
qemu-system-aarch64 --version   # 6.2.0 (>= 5.1 as upstream requires)
qemu-aarch64-static --version   # 6.2.0
```

The OpenHarmony QEMU products use the in-tree `kernel/linux` (5.10/6.6), not
the X5 6.1 kernel. None of `patches/kernel/` is exercised.

## L1: user-mode QEMU (run first, no build)

These use `qemu-aarch64-static` to execute AArch64 binaries from `out/` on the
x86 host with the staged musl loader and libraries.

### L1.1 Offline suite and ABI checks

```sh
./rdkhm check
python3 scripts/check-composer-abi.py
python3 scripts/check-access-token-abi.py
python3 scripts/check-hap-signatures.py
python3 scripts/image_haps.py --check
```

- `./rdkhm check`: 14 host-side tests, patch coverage/format, GPIO daemon
  socket smoke test.
- composer/access-token checks compare our patch surface with the packaged
  provider/consumer ABI; they are host-side, not QEMU, but belong in the same
  gate.
- Expected: all pass; HAP signature check may report only the unused stray
  `out/haps/external_file_manager-exported.hap`.

Prerequisites: built `out/` tree; `thirdparty/` toolchains. No QEMU build.

### L1.2 Accelerator runtime under QEMU

```sh
python3 scripts/prepare-accelerators.py
python3 scripts/test-accelerators.py
python3 scripts/test-accelerator-socket.py
```

`test-accelerators.py` runs `accelerator-probe` and `nnrt-worker` through
`qemu-aarch64-static` with the private musl loader:

- checks all private `DT_NEEDED` libraries resolve inside the staged runtime;
- expects `LIBRARY_CHECK_PASS` and `DNN_VERSION 1.24.5`;
- expects `--invalid` to exit 2 and an invalid model to print
  `MODEL LOAD FAILED` (no device/model is opened).

`test-accelerator-socket.py` starts `accelerator-daemon` under QEMU and
exercises the Unix-socket request/response framing.

Prerequisite: `out/accelerator-runtime/lib64/rdkhm-accelerator/` exists.
`test-accelerators.py` also requires `CONFIG_VERISILICON_X5_SYSCON_BRIDGE=y`
in `out/kernel/obj/.config`.

### L1.3 NearLink SSAP stack under QEMU

```sh
bash scripts/test-nearlink.sh --ohos
```

Without `--ohos`, the same suites run natively on the host. With `--ohos` they
are compiled with the OpenHarmony clang for `aarch64-linux-ohos` against the
X5 musl sysroot and executed with `qemu-aarch64-static -L
$RDKHM_OH_TREE/out/rdk_x5/packages/phone/system`.

Suites: `codec`, `server`, `feature`, `link`. Prerequisite: the X5 userspace
tree and sysroot are already built.

### L1 limits

- No kernel, no HDF, no real device I/O. `/dev/*` access is either mocked or
  expected to fail.
- The socket/daemon tests prove protocol and staging, not BPU/GPU execution.

## L2: system-mode QEMU products

The tree provides these products under
`sources/oh/openharmony-full/vendor/ohemu/`:

| Product | Arch | Contents |
| --- | --- | --- |
| `qemu-arm64-linux-min` | arm64 | minimum standard system, `support_jsapi: false` |
| `qemu-arm-linux-min` | arm | minimum standard system |
| `qemu-arm-linux-headless` | arm | min + appspawn/ability_runtime/bundle_framework/napi, graphics **disabled** (`ability_runtime_graphics=false`, `bundle_framework_graphics=false`) |

There is no arm64 product with graphics or ArkUI in this release.

### L2.0 Preconditions

- No concurrent OpenHarmony build in the same tree. The X5 `vendor_image`
  build and the QEMU product build both write under the OH tree's `out/`.
- Disk space for another `out/qemu-*` tree; the arm/arm64 products share the
  board name `qemu-arm-linux` and therefore the same output directory. Build
  one product at a time and archive its images before switching.
- The QEMU product builds use our patched tree. Our X5-specific patches may
  fail to build or be irrelevant for the minimum product. Record the failure
  point; see "If the patched tree fails".

### L2.1 Build and boot arm64 minimum

```sh
cd sources/oh/openharmony-full
./build.sh --product-name qemu-arm64-linux-min --ccache --jobs 16
```

Images land in `out/qemu-arm-linux/packages/phone/images/` (board name, not
product name). Confirm `zImage-dtb`, `ramdisk.img`, `system.img`, `vendor.img`,
`userdata.img` are present, then archive them, e.g. under
`out/qemu-validation/arm64-min/` in the workspace.

Boot (from the OH tree root):

```sh
mkdir -p /home/robo/rdkhm/out/qemu-validation
timeout 180 ./vendor/ohemu/qemu_arm64_linux_min/qemu_run.sh \
    -e out/qemu-arm-linux/packages/phone/images \
    2>&1 | tee /home/robo/rdkhm/out/qemu-validation/arm64-min-console.log
```

Console is `-nographic`; exit with `Ctrl-A x`, or let `timeout` end it.

Pass criteria (strings in the console log):

- kernel reaches userspace and `init` starts;
- `samgr`, `hdc`, `hilogd`/`hilog` start without repeated crash loops;
- no blocking panic or SELinux denial storm during the run window.

Record: kernel command line, first 200 lines, all `E ` lines, and the final
service state.

### L2.2 Build and boot arm32 headless

```sh
cd sources/oh/openharmony-full
./build.sh --product-name qemu-arm-linux-headless --ccache --jobs 16
# archive the images, then:
timeout 180 ./vendor/ohemu/qemu_arm_linux_headless/qemu_run.sh \
    -e out/qemu-arm-linux/packages/phone/images \
    2>&1 | tee /home/robo/rdkhm/out/qemu-validation/arm32-headless-console.log
```

Additional pass criteria beyond L2.1:

- `appspawn` starts;
- `ability_runtime` and `bundle_framework` services start with
  `*_graphics=false` paths;
- attempt a headless bundle-manager query only if an `hdc` session is
  available; do not expect UI.

This product cannot start Launcher, SystemUI, Settings or any ArkUI page.

### L2.3 Optional: HDC over QEMU user networking

The run scripts accept `-n` (creates `br0`, requires root) or an instance id.
This is optional; serial console evidence is sufficient for the first pass.
If used, verify `hdc list targets` from the host and record the target id.

### If the patched tree fails

Our tree carries 83 OpenHarmony patches, several of them X5-specific. If a
QEMU product fails to build:

1. Capture the failing GN/ninja target and the patch that touched it.
2. Reproduce against HEAD for that one component in a scratch `git worktree`
   (`git -C <repo> worktree add /tmp/... <base>`); do not revert patches in
   the X5 tree.
3. Classify: (a) harmless but broken X5-only patch, (b) patch needed for the
   QEMU product, (c) product genuinely unsupported.
4. Record the classification in the run log. Do not "fix" the X5 tree to
   satisfy QEMU unless the fix is also correct for X5.

A full unpatched OpenHarmony checkout is not planned; it duplicates tens of
GiB and is only needed if per-component worktrees cannot isolate the failure.

## L3: HAP and graphics under QEMU

Not supported by the products in this tree:

- `qemu-arm64-linux-min` has `support_jsapi: false` (no ArkTS/app framework).
- `qemu-arm-linux-headless` is arm32 and disables graphics in
  ability_runtime/bundle_framework/common_event/storage.
- All 22 built HAPs target the X5 `phone` product, and the UI path depends on
  the X5 display composer.

Verifying Launcher/SystemUI/Settings under QEMU would require a new arm64
graphics product (virtio-gpu + ace_engine + window_manager + render_service +
launcher/systemui, plus a matching SDK/product configuration). That is a port,
not a QEMU run of the current artifacts, and is out of scope for this pass.

## Not verifiable under QEMU

- The X5 production kernel/DTB and its board boot chain. A separate X5 6.1
  QEMU-virt profile now boots the kernel to an initramfs shell (see
  [qemu-three-paths-20261120.md](qemu-three-paths-20261120.md), C4); that does
  not validate the X5 DTB, OpenHarmony userspace or X5 hardware.
- HDF drivers and firmware: display composer/DRM, HDMI, touch, camera, audio,
  CAN-FD, WS73, GPIO.
- GPU/BPU/NNRT execution; only the userspace protocol/staging path is covered
  by L1.
- Flash layout, fastboot, uboot, and cold-boot behavior.

## Execution order and evidence

1. L1.1, L1.2, L1.3 in one pass; capture to
   `out/qemu-validation/l1-<date>/`.
2. L2.1 arm64 min; archive images and console log.
3. L2.2 arm32 headless; archive images and console log.
4. Write a short result record with: commands, image checksums, console
   excerpts, pass/fail per criterion, and the patch-conflict classification if
   any.

`out/` is ignored and disposable; do not commit QEMU images or logs.

## Execution record (2026-11-20)

### L1: passed

| Check | Result |
| --- | --- |
| `./rdkhm check` | 14 tests OK, integration checks passed |
| `check-composer-abi.py` (packaged `libdisplay_composer_vdi_impl_default.z.so`) | PASS: 40 mandatory C exports; 22 optional entry points absent |
| `check-access-token-abi.py` | PASS |
| `image_haps.py --check` | 25 entries OK |
| `check-hap-signatures.py` | 32/33 official; only unused `external_file_manager-exported.hap` fails |
| `test-accelerators.py` | PASS: private dependency closure, DNN 1.24.5, GPU/EGL markers, invalid input rejection |
| `test-accelerator-socket.py` | PASS: inherited socket, framing, bounds, timeout, shutdown, invalid fd |
| `test-nearlink.sh --ohos` | PASS: codec, server, feature, link (135 assertions) |

### L2: blocked by upstream product defects

`qemu-arm64-linux-min` cannot build from this release snapshot without upstream
source changes. Failures found, in order:

1. `device/qemu/arm_virt/linux/ohos.build` declares subsystem `device_arm_virt`
   while the build expects `device_qemu-arm-linux` (board name). Fixed locally
   in `device/qemu/arm_virt{,/linux}/ohos.build` and the arm64/headless product
   configs.
2. `build/subsystem_components_whitelist.json` lacks
   `product_qemu-arm64-linux-min` and `product_qemu-arm-linux-headless`. Added
   locally.
3. The arm64 product config lacks `resourceschedule:ffrt` (required by
   `device_manager/utils`) and `thirdparty` components. Added `ffrt`,
   `rust_libc`, and `commonlibrary:ylong_runtime` locally. GN then asked for
   further dependencies (`openssl` etc.); the arm64 product config is far
   behind the arm32 one.
4. Host tool failure: prebuilt clang++ 15 cannot locate C++ standard headers on
   this host (GCC 12 detected, only `c++/9` and `c++/11` installed), so
   `third_party/e2fsprogs` `dac_config.cpp` fails on `<fstream>`. Workaround
   verified:
   `CPLUS_INCLUDE_PATH=/usr/include/c++/11:/usr/include/x86_64-linux-gnu/c++/11`.
5. Switching to `qemu-arm-linux-min` (arm32) gets past GN and into ninja
   (5084/26448 targets), then fails twice:
   - the same host C++ header problem;
   - the kernel step selects `linux-6.6`, but
     `qemu-arm-linux_standard_defconfig` only exists under `linux-5.10`;
     `drivers/hdf/khdf/model/audio/Makefile` also descends into
     `device/board/kaihong/khdvk_3566b/kernel/audio`, which does not exist for
     this product.

Local uncommitted edits made during this attempt (not yet in
`config/patches.json`):

- `device/qemu/arm_virt/ohos.build`
- `device/qemu/arm_virt/linux/ohos.build`
- `vendor/ohemu/qemu_arm64_linux_min/config.json`
- `vendor/ohemu/qemu_arm_linux_headless/config.json`
- `build/subsystem_components_whitelist.json`

To continue L2, choose one of:

- port the arm32 product to `linux-5.10` by overriding `linux_kernel_version`
  and guarding the HDF audio board path (upstream-quality fix, needs patches);
- or use prebuilt upstream QEMU images for this release instead of building
  them from this patched tree.

### L2 progress update (2026-11-20, arm32)

Both arm32 products now pass GN; `qemu-arm-linux-min` builds and boots.

Fixes applied to the tree (uncommitted, not yet in `config/patches.json`):

- `device/qemu/arm_virt{,/linux}/ohos.build`: subsystem `device_arm_virt` →
  `device_qemu-arm-linux`.
- `build/subsystem_components_whitelist.json`: add
  `product_qemu-arm64-linux-min`, `product_qemu-arm-linux-headless`.
- `vendor/ohemu/qemu_arm_linux_min/config.json`: `customization:config_policy`.
- `drivers/hdf_core/adapter/khdf/linux/model/audio/Makefile`: guard the
  kaihong board audio directory with `wildcard`.
- `foundation/systemabilitymgr/samgr/interfaces/innerkits/common/BUILD.gn`:
  add `install_images = [ system_base_dir, updater_base_dir ]`; without it
  `libsamgr_common.z.so` is built but never packaged and `samgr` exits 127.
- `third_party/ffmpeg/ohos_config.sh`: add `--disable-vulkan` to the
  non-aarch64 branch; the GN source list has no `hwcontext_vulkan.c`.
- Host toolchain: symlinks for GCC 12 C++ headers and static libstdc++
  (`libstdc++.a`, `libstdc++.so`, `libstdc++fs.a` -> GCC 11 versions); the
  prebuilt clang 15 otherwise cannot find `<fstream>` or `-lstdc++`.
- Build invocation: `--gn-args 'linux_kernel_version="linux-5.10"
  load_test_config=false'`; `--load-test-config=false` only affects the
  loader, the GN variable defaults to true and keeps pulling test targets.
- `device/qemu/arm_virt/linux/rootfs`: empty `foundation.json` installed to
  `/system/profile` (kept for completeness).
- `vendor/ohemu/qemu_arm_linux_headless/config.json`: removed stale
  `appexecfwk` subsystem, `hicollie_native`, `permission_standard`,
  `ability_tools`, `bundlemanager:appexecfwk_core`, `distributedfilejs`,
  `native_appdatamgr`, `procrank`; added the component closure GN requested
  (thirdparty, sdk, asset, certificate_manager, code_signature,
  security_guard, tee_client, sensors, powermgr, graphic_surface,
  graphic_2d, graphics_effect, vulkan, useriam, hdf interfaces, grpc, wifi,
  memory_utils, frame_aware_sched, …); `appspawn_support_nweb=false`.

Boot result for `qemu-arm-linux-min` (arm32, Linux 5.10.210):

- kernel boots, `init` mounts system at `/usr`, switch_root succeeds;
- `samgr` starts and reports `SAMGR: set samgr ready ret : succeed`;
- `hilogd`, `hdcd`, `softbus_server` start;
- `foundation` (`/system/bin/sa_main /system/profile/foundation.json`) exits 0
  immediately: the minimal product has no component that contributes a
  foundation-process SA, so no merged profile exists. An empty profile does
  not keep `sa_main` resident. Removing `safwk` is not possible because
  `device_security_level` depends on `safwk:system_ability_fwk`;
- init restarts `foundation` four times and triggers
  `Kernel panic - not syncing: sysrq triggered crash`.

`qemu-arm-linux-headless` passes GN and reaches ninja (10k+/38k targets), then
fails compiling `foundation/arkui/ace_engine` (`theme_constants_defines.h`,
`form_mgr.h` not found). The headless product config is from an older release;
with the 6.0 component tree it pulls ArkUI without the corresponding product
graphics configuration. Completing it is a graphics-product port, not a
dependency fix.

Conclusion for this pass: the arm32 minimal image boots the OpenHarmony
userspace core under QEMU; a full headless/app-framework image needs the
product converted to a proper 6.0 graphics configuration (or an upstream
prebuilt image). The X5 image itself remains non-bootable under QEMU.

## Do not

- Do not flash, reboot or otherwise touch the board for this plan.
- Do not run QEMU and an OpenHarmony build concurrently in the same tree.
- Do not treat L1/L2 success as X5 board validation.
