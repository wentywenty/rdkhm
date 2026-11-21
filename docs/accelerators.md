# X5 GPU and BPU integration

All hardware behavior remains untested. The SD image now contains the kernel
drivers and a private native runtime, not an accelerated OpenHarmony desktop or
a registered NNRT backend.

## Kernel

The retained X5 kernel already builds `galcore.ko` from
`drivers/misc/verisilicon/gc8000l`, plus `bpu_framework`, `bpu_governor` and
`bpu_cores`. All four are now selected for dependency-ordered boot loading.
`CONFIG_ION` and `CONFIG_ION_HOBOT` are built in; the vendor memory library may
use the board's ION interface. Device allocation/ioctl behavior still needs X5.

The display driver previously called `request_module("vs_x5_syscon_bridge")`
unconditionally and returned the helper error during early kernel probing.
This bootstrap does not yet have a userspace module loader at that stage.
The bridge is now built in, and a scoped kernel patch skips that request for
built-in configurations. The rebuilt DRM object has no `request_module` reference;
the bridge is recorded in modules.builtin. Actual DRM probing remains untested.

The official `x5-hobot-drivers` package supplies `bpu_hw_io_x5.o_shipped`.
It links against the current 6.1.83-rdkhm kernel with no unresolved modpost symbols,
and the bundle passes depmod against System.map. The module declares a proprietary
license. Re-linking generates the current vermagic but does not prove the binary
object's structure layouts, callbacks or hardware behavior match this kernel.
That ABI boundary must be validated on board. The vendor object is not rewritten.

The kernel GPU version is `6.4.14.9.674707`; the fetched `libGAL.so` contains
`$VERSION$6.4.14:674707$`. The offline test checks those version markers.
Matching markers are necessary evidence, not a successful render test.

## Runtime boundary

Official libraries were obtained from:

- https://github.com/D-Robotics/x5-hobot-drivers
- https://github.com/D-Robotics/x5-hobot-dnn
- https://github.com/D-Robotics/x5-hobot-multimedia

Exact revisions are pinned in `config/accelerators/sources.json`. Library bytes,
the Ubuntu ARM64 libdrm package and copied cross-sysroot glibc/C++ libraries are
pinned in `config/accelerators/assets-lock.json`. Re-preparation rejects changed
library hashes. These remain upstream binary artifacts with their original terms.

`libdnn.so` requires glibc, libstdc++, HBRT, libcnn_intf, libhbmem and libalog.
EGL/GLES require the vendor GAL/GBM/DRM stack and glibc. They cannot simply be
installed as replacements for OpenHarmony's musl-linked graphics libraries.

The dependency closure lives only in `/vendor/lib64/rdkhm-accelerator`.
`/vendor/bin/rdkhm-accelerator` explicitly invokes that directory's glibc loader
with a private library path and no loader cache. No global symlinks, linker search
path changes, OH service preload or libc replacement is made. This is process
separation, not a security sandbox. The image now starts a dedicated
`rdkhm-accelerator` service in its own `rdkhm_accel` SELinux domain. Its bounded
UNIX socket accepts `PING`, `GPU_CHECK`, `NPU_CHECK` and `NNRT_BACKEND`; the last
command reports `NNRT_BACKEND_RUNTIME_READY` only when `libdnn.so` loads. This is
a library capability result, not a registered OpenHarmony NNRT backend; model descriptors are only exposed
by the separate manual worker. The
daemon consumes the init-provided `OHOS_SOCKET_rdkhm_accel` listener fd, so init
owns socket creation, mode and SELinux labeling. Device access is limited to
the accelerator domain and a small DRM ioctl allowlist.
Board AVC logs are still required before expanding those rules.

Requests are newline-terminated, limited to 127 bytes before the newline and
subject to a two-second receive deadline. Invalid init descriptors fail closed;
only explicit `--socket` test mode creates a private socket. Test with
`python3 scripts/test-accelerator-socket.py` (the staged ARM64 binary under QEMU).
Library loading itself is not isolated by a worker timeout yet.

## Probes

After a board is available, run manually as root:

```sh
/vendor/bin/rdkhm-accelerator --check
/vendor/bin/rdkhm-accelerator --gpu /dev/dri/card0
/vendor/bin/rdkhm-accelerator --gpu-diag /dev/dri/card0
/vendor/bin/rdkhm-accelerator --gpu-compose /dev/dri/card0
/vendor/bin/rdkhm-accelerator --models /data/model.bin
/vendor/bin/rdkhm-accelerator --describe /data/model.bin
```

`--check` loads the actual vendor libraries with immediate symbol resolution and
reads the DNN version. `--gpu` opens the selected DRM node, creates a vendor GBM
display and GLES2 pbuffer, clears it, then checks a read-back pixel. It does not
change display modes. Unsupported pbuffer/GBM combinations fail visibly.
`--gpu-diag` prints every EGL step and the first usable config instead of only
the final error; it uses the same offscreen path. `--gpu-compose` runs the
two-layer dma-buf composition probe described in
[hardware-composition.md](hardware-composition.md). It is packaged in the
source runtime but not yet in the flashed image.
`--models` loads a real vendor-format model pack and lists model names; it does
not execute inference and is not a general ONNX importer. `--describe` resolves
each model handle and prints input/output tensor shapes, types, layouts and
aligned byte sizes. This is the tensor contract needed before an OH NNRT
adapter can be enabled; it still does not execute inference.

Offline `scripts/test-accelerators.py` checks private DT_NEEDED closure, runs
`--check` under QEMU, confirms version 1.24.5 and tests rejection of an unknown
command. It deliberately does not execute the GPU or model commands on the host.

## Rebuild

Run after the kernel `Image`/DTBs, `prepare-openharmony.sh` and the userspace
`images` target already exist:

```sh
python3 scripts/prepare-accelerators.py
JOBS=64 bash scripts/build-kernel.sh modules
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/import-driver-firmware.py
python3 scripts/test-accelerators.py
python3 scripts/prepare-driver-bundle.py
bash scripts/build-bringup-userspace.sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

The private probes use the installed AArch64 GNU compiler/sysroot; the OH system
still uses its own Clang/musl toolchain. The image injector preserves executable
permissions for the loader, probes and wrapper and verifies all bundled hashes.

## Board probe 2026-11-19

Logs: `out/board-logs/20261119-gpu-probe/` (`probe.log`,
`step-diag-20261119.log`, `glslc-fix-20261119.log`).

Current session: `<board-ip>:5555`, boot_id
`00836ef8-c49c-4a6e-8c58-a0bf1da68998`, kernel `6.1.83-rdkhm`.

- `galcore`, `bpu_framework`, `bpu_governor`, `bpu_cores` and
  `bpu_hw_io_x5` are loaded; `/dev/galcore` and `/dev/dri/card0` exist. The
  private runtime is version `6.4.14:674707`, matching the kernel `galcore`,
  and now contains the unversioned `libEGL.so`/`libGLESv2.so` symlinks.
- `rdkhm-accelerator --check` passes (DNN `1.24.5_(3.15.55 HBRT)`, EGL and
  GLESv2 load).
- Step-by-step EGL probe: `eglGetPlatformDisplay` and `eglInitialize`
  succeed (1.5, vendor `Vivante Corporation`, client API `OpenGL_ES`);
  `eglBindAPI` succeeds; `eglChooseConfig` matches 10 configs and
  `eglGetConfigs` reports 40. `eglCreateContext` returns `0x3005`
  (EGL_BAD_CONFIG) for all 40 configs.
- `--gpu` reports `EGL error=0x3000`. This is a probe reporting artifact:
  `gpu-probe` creates a pbuffer surface after the failed context creation,
  which clears `eglGetError()`. The actual failure is `0x3005` at context
  creation.
- Enabling `galcore` `debugLevel=3` around the probe produced no kernel
  errors, only permissive SELinux `avc` denials; `debugLevel` was restored
  to 0. Device permissions and DRM/GBM setup are not the blocker.
- `galcore` parameters: `contiguousSize=4194304`, `physSize=0`, `mmu=1`,
  `processPageTable=1`.
- Historical session (boot `49dd3d69-3264-446e-80f7-aa67193d9af9`): the
  original failure was `0x300c` (EGL_BAD_PARAMETER) because `libEGL`
  dlopens the unversioned `libGLESv2.so`; installing the vendor symlinks
  fixed that. The remaining `0x3005` was unchanged.
- Earlier direct GAL checks in that session: the DT node is `okay`,
  `gcoHAL_QueryChipIdentity` reports model `0x8000` (GC8000L) revision
  `0x6214`, and `gcoHAL_QueryTargetCaps`, `gco3D_Construct`,
  `gco3D_SetAPI` and `gco3D_SetAlphaTest` succeed. The vendor EGL maps the
  failed client-API create-context return to `EGL_BAD_CONFIG`, so EGL's
  generic error text is misleading.
- Root cause of `0x3005`: the private runtime omitted `libGLSLC.so`.
  `libGAL`/`libGLESv2` load the GLSL compiler with `dlopen` when the first GL
  context is created, so `--check` and `eglInitialize` succeed even when the
  library is absent. With the vendor `libGLSLC.so` on the loader path,
  `eglCreateContext`, `eglMakeCurrent`, the clear and the pixel read-back all
  pass for both a pbuffer and a GBM window surface:
  `GL_RENDERER=Vivante GC8000L`, `GL_VERSION=OpenGL ES 3.1 V6.4.14.9.674707`.
  Log: `out/board-logs/20261119-gpu-probe/glslc-fix-20261119.log`.
- `scripts/prepare-accelerators.py` now stages `libGLSLC.so` (19 private
  libraries, hash pinned in `config/accelerators/assets-lock.json`). The
  currently flashed image still lacks it; the board pass above used a copy in
  `/data/local/tmp` on the loader path. A new image has not been built.

Offscreen GPU rendering is proven with the corrected private runtime.
OpenHarmony RenderService is still on the software composition path; no
hardware-rendered OH buffer or desktop has been demonstrated.

## Board probe 2026-11-20

The rebuilt image (`out/images/rdkhm-x5-openharmony-dev.img`, sha256
`db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78`,
root PARTUUID `38b083ac-02`) was booted on `<board-ip>:5555`, boot_id
`9ade3a96-6eb4-4876-a3dc-f407990d6b5e`, kernel `6.1.83-rdkhm`. Log:
`out/board-logs/20261120-gpu/gpu-test-20261120.log`.

- `/vendor/lib64/rdkhm-accelerator/libGLSLC.so` is present with the pinned
  sha256 `3a69f38…0517`; `gpu-probe` is the stepped/reporting version.
- `rdkhm-accelerator --check` passes.
- `rdkhm-accelerator --gpu /dev/dri/card0` passes:
  `EGL 1.5`, `GL_RENDERER=Vivante GC8000L`,
  `GL_VERSION=OpenGL ES 3.1 V6.4.14.9.674707`, `GPU_OFFSCREEN_PASS`.
- `--gpu-diag`: EGL 1.5, 40 configs, first usable config index 0, no EGL error.
- Additional GLES2 shader diagnostic (temporary binary): shader compile and
  program link succeed, a triangle renders green at the center and black at
  the corner, `GL_SHADING_LANGUAGE_VERSION=OpenGL ES GLSL ES 3.10`,
  `GPU_SHADER_PASS`.
- RenderService (`render_service`, pid 959) still has only `/dev/dri/card0`
  descriptors and no `/dev/galcore` descriptor; OpenHarmony rendering remains
  on the software composition path.

## NNRT integration

Source, wire protocol, build result and board-enable steps are documented in
[nnrt-backend.md](nnrt-backend.md). Current state: the HDI service, HCS host and
SELinux rules are present; the OH NNRT C API now runs a ResNet18 `.bin` end to
end on the board (2026-11-20, `top=473 value=3.481126`), matching the private
daemon. That board run used a hot-deployed runtime/proxy and bind-mounted
service/stub. The 2026-11-21 SD image now contains the same four artifacts,
verified byte-for-byte, but it has not been flashed. Only the vendor
offline-`.bin`/`.hbm` path is supported; the operator-graph `PrepareModel()`
path returns `NNRT_NOT_SUPPORT`.

## Next integration

GPU: offscreen rendering passes once the private runtime includes
`libGLSLC.so`. Next is connecting the service's bounded GPU check to the OH
native-window/buffer contract using a compatible vendor userspace build. The
current software RenderService path stays enabled until a hardware-rendered OH
frame is shown. Feasibility and the proposed out-of-process compositor are
documented in [hardware-composition.md](hardware-composition.md). The
composer-side `COMPOSE` path is implemented in `display/0009` and builds, but
is disabled by default after the 2026-11-20 dma-buf sg_table kernel panic;
enable it only after `kernel/0021-dmabuf-sgtable-guard.patch` is flashed.

BPU: the OH NNRT C API path is working for raw offline models. Remaining work is
to bake the runtime/HDI patches into a flashed image, add model-cache/dynamic
shape support if needed, and keep the operator-graph path explicitly
unsupported until an HBM compiler is integrated.
