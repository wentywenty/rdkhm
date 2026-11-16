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

Exact revisions are pinned in `config/accelerator-sources.json`. Library bytes,
the Ubuntu ARM64 libdrm package and copied cross-sysroot glibc/C++ libraries are
pinned in `config/accelerator-assets-lock.json`. Re-preparation rejects changed
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
command reports `NNRT_BACKEND_UNAVAILABLE`; model descriptors are only exposed
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
/vendor/bin/rdkhm-accelerator --models /data/model.bin
/vendor/bin/rdkhm-accelerator --describe /data/model.bin
```

`--check` loads the actual vendor libraries with immediate symbol resolution and
reads the DNN version. `--gpu` opens the selected DRM node, creates a vendor GBM
display and GLES2 pbuffer, clears it, then checks a read-back pixel. It does not
change display modes. Unsupported pbuffer/GBM combinations fail visibly.
`--models` loads a real vendor-format model pack and lists model names; it does
not execute inference and is not a general ONNX importer. `--describe` resolves
each model handle and prints input/output tensor shapes, types, layouts and
aligned byte sizes. This is the tensor contract needed before an OH NNRT
adapter can be enabled; it still does not execute inference.

Offline `scripts/test-accelerators.py` checks private DT_NEEDED closure, runs
`--check` under QEMU, confirms version 1.24.5 and tests rejection of an unknown
command. It deliberately does not execute the GPU or model commands on the host.

## Rebuild

```sh
python3 scripts/prepare-accelerators.py
JOBS=64 bash scripts/build-kernel.sh Image
JOBS=64 bash scripts/build-kernel.sh modules
bash scripts/build-accelerator-modules.sh
python3 scripts/test-accelerators.py
python3 scripts/prepare-driver-bundle.py
JOBS=64 bash scripts/build-openharmony.sh --build-target images
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

The private probes use the installed AArch64 GNU compiler/sysroot; the OH system
still uses its own Clang/musl toolchain. The image injector preserves executable
permissions for the loader, probes and wrapper and verifies all bundled hashes.

## Next integration

GPU: validate galcore/DRM/GBM on X5, then connect the service's bounded GPU check
to the OH native-window/buffer contract using a compatible vendor userspace build.
The current software RenderService path stays enabled until that board proof.

BPU: validate memory allocation and a known model on X5, then extend the service
protocol from capability checks to bounded inference requests and register
an OH NNRT backend for supported model formats/operators. No inference capability
is advertised by the current `NNRT_BACKEND` response.
