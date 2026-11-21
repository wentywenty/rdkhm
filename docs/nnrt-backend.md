# X5 NNRT backend integration

Status of the OpenHarmony Neural Network Runtime (NNRt) path on the X5 BPU.

| Item | State |
| --- | --- |
| Source and patch | present |
| Component build | passed (2026-11-20, ninja) |
| Installed in images | yes: runtime/proxy in system.img, service/stub/driver in vendor.img |
| Image assembly | passed (2026-11-21, `1e5d24a5...`) |
| HDF host enabled | yes on 0021 cold boot (`nnrt_host`) |
| OH NNRT C API | passed (raw `.bin`, 2026-11-20) |
| Board inference | passed via C API and private daemon (ResNet18) |
| ONNX conversion | passed (ResNet18, 2026-11-20) |
| Real X5 models | MobileNetV2 + converted ResNet18 |

The runtime, device nodes and vendor library already load (`NPU_RUNTIME_READY`);
that is a capability result, not inference evidence. See
[accelerators.md](accelerators.md).

## Architecture

```text
OH NNRT core (libneural_network_runtime)
  -> HDI v2.1 INnrtDevice / IPreparedModel
     -> libnnrt_device_service_2.1.z.so        (musl, HDF host)
        -> /dev/unix/socket/rdkhm_accel        (binary protocol + SCM_RIGHTS)
           -> accelerator-daemon               (private glibc runtime)
              -> libdnn.so / hbDNN*            (vendor)
                 -> /dev/bpu, /dev/bpu_core0
```

The HDI service must not link `libdnn.so`: OH services are musl and the vendor
stack is glibc. The daemon keeps the process separation that already exists for
GPU/NPU probes.

## Model path

Only the vendor offline-model path is implemented:

1. `OH_NNCompilation_ConstructWithOfflineModelFile()` or
   `...OfflineModelBuffer()`.
2. NNRT core queries input/output tensor descriptors through
   `INnrtDevice::GetOfflineModelIO()` (vendor extension) so it can create
   executor tensors for a raw model.
3. NNRT core calls `PrepareOfflineModel()` with the model bytes in a
   `SharedBuffer`.
4. The HDI service forwards the fd to the daemon, which calls
   `hbDNNInitializeFromDDR()`.
5. `IPreparedModel::Run()` forwards input/output shared buffers to
   `hbDNNInfer()` + `hbDNNWaitTaskDone()`.

The operator-graph path (`PrepareModel()` with NNRT `Model` nodes) returns
`NNRT_NOT_SUPPORT`; `GetSupportedOperation()` reports every node unsupported.
Supporting arbitrary graphs needs an HBM compiler and is out of scope.

Capability answers are deliberately conservative: no float16, performance mode,
priority, dynamic input or model cache yet.

## Wire protocol

Header: `bringup/probes/accel_wire.h`.

- 24-byte packed header: magic `RDK1`, version, command, session, payload size,
  fd count, flags.
- Commands: `HELLO`, `LOAD`, `INFO`, `RUN`, `RELEASE`.
- Model bytes are inline or passed as one fd; tensor buffers are passed as fds
  with offset/length. Fds travel through `SCM_RIGHTS`.
- Status values match `NNRT_ReturnCode` so the HDI service can pass them through.
- Text probes (`PING`, `GPU_CHECK`, `NPU_CHECK`, `NNRT_BACKEND`) remain on the
  same socket; a frame starting with `RDK1` selects binary mode.
- Sessions live in the daemon, not in the per-call connection.

## Source layout

Added by `patches/nnrt/0001-x5-nnrt-hdi-service.patch` into
`drivers/peripheral/nnrt`:

- `BUILD.gn`, `bundle.json`
- `include/nnrt_device_service.h`, `include/rdkhm_accel_client.h`,
  `include/accel_wire.h`
- `src/nnrt_device_service.cpp`, `src/rdkhm_accel_client.cpp`,
  `src/nnrt_device_driver.cpp`

The raw-offline C API path is added by:

- `patches/nnrt/0002-vendor-offline-model-io.patch` — `drivers/interface`
  `INnrtDevice::GetOfflineModelIO()` IDL method.
- `patches/nnrt/0003-raw-offline-runtime.patch` — `foundation/ai/neural_network_runtime`
  accepts offline path/buffer, queries IO descriptors, and implements the raw
  HDI `PrepareOfflineModel()` / `GetOfflineModelIO()` calls in
  `HDIDeviceV2_1`.

Integration repository:

- `bringup/probes/accelerator-daemon.c` and `bringup/probes/accel_wire.h`
- `scripts/prepare-accelerators.py` (daemon include path)
- `scripts/test-accelerator-socket.py`, `tests/test-nnrt-wire.py`,
  `tests/nnrt-wire-client.cpp`
- `overlay/vendor/drobotics/rdk_x5/config.json` (part in the `hdf` subsystem)
- `overlay/vendor/drobotics/rdk_x5/nnrt/nnrt_device.hcs` (HDF host fragment)
- `config/patches.json` (openharmony collection entry)

`prepare-openharmony.sh` applies the patch; the part is declared by
`bundle.json` and installs to `/vendor/lib64` during a unified build.

## Build

Component-only build, no image assembly. The `build-target.sh` wrapper currently
aborts at the unrelated `deps_guard` check, so the 2026-11-20 build used ninja
directly:

```sh
cd sources/oh/openharmony-full/out/rdk_x5
ninja -w dupbuild=warn libnnrt_stub_2.1 libnnrt_proxy_2.1
ninja -w dupbuild=warn libneural_network_runtime
ninja -w dupbuild=warn libnnrt_device_service_2.1 libnnrt_driver
```

If the notice scripts fail under a `python`/Python-2 shim, prepend a directory
where `python` points to Python 3.

Artifacts:

- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_driver.z.so`
- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_device_service_2.1.z.so`
  (exports `NnrtDeviceImplGetInstance`, `NnrtDeviceImplRelease`)
- `out/rdk_x5/hdf/drivers_interface_nnrt/libnnrt_stub_2.1.z.so`
- `out/rdk_x5/hdf/drivers_interface_nnrt/libnnrt_proxy_2.1.z.so`
- `out/rdk_x5/ai/neural_network_runtime/libneural_network_runtime.so`

Only the service/driver artifacts are installed by the component target; the
runtime is part of the system image in a unified build.

## Enabling on a board

Source enablement is complete:

1. `overlay/vendor/drobotics/rdk_x5/nnrt/nnrt_device.hcs` is merged into
   `overlay/vendor/drobotics/rdk_x5/hdf_config/uhdf/hdf.hcs`.
2. `nnrt.te` and `hdf_service_contexts` cover the host and socket.
3. `drivers_peripheral_nnrt_x5` is part of the product `hdf` subsystem and the
   `nnrt` component builds the service/driver.

The 2026-11-20 board test hot-deployed the new libraries without an image:

```sh
# push runtime, proxy, stub and service to /data/local/tmp/nnrt-sync
mount --bind /data/local/tmp/nnrt-sync/libnnrt_device_service_2.1.z.so \
  /vendor/lib64/libnnrt_device_service_2.1.z.so
mount --bind /data/local/tmp/nnrt-sync/libnnrt_stub_2.1.z.so \
  /vendor/lib64/libnnrt_stub_2.1.z.so
service_control stop nnrt_host
service_control start nnrt_host
LD_LIBRARY_PATH=/data/local/tmp/nnrt-sync:/system/lib64:/system/lib64/platformsdk:/system/lib64/ndk \
  /data/local/tmp/nnrt-capi-test /data/local/tmp/resnet18.bin
```

The bind mounts are not persistent. On 2026-11-21 16:35 the SD image was
reassembled from the OpenHarmony package images, and the four NNRT artifacts in
the final image match the built files byte for byte:

| Artifact | SHA256 |
| --- | --- |
| `system/lib64/ndk/libneural_network_runtime.so` | `5e9bb17e...` |
| `system/lib64/platformsdk/libnnrt_proxy_2.1.z.so` | `7e43f39d...` |
| `vendor/lib64/libnnrt_device_service_2.1.z.so` | `2448c523...` |
| `vendor/lib64/libnnrt_stub_2.1.z.so` | `7ff4affa...` |

Final image: `out/images/rdkhm-x5-openharmony-dev.img`, SHA256
`1e5d24a599d429c43e85b93cbce0cb08c3f0afc7caf3f29f23fd68b870826cf4`.
It is **not flashed**, so the 2026-11-20 board result is still the only
end-to-end NPU evidence. Do not add permissive rules or a global SELinux
exception just to make the host start.

## Verification plan

Already covered offline:

- daemon text probes and fragmented frames;
- binary framing, invalid sessions, empty inline model, empty model fd;
- C++ transport client against the ARM64 daemon under QEMU;
- component build and exported factory symbols.

Board inference through the **private daemon path** and the **OH NNRT C API**
passed on 2026-11-20 with ResNet18. The C API returned the same top-1 result as
the daemon (`top=473 value=3.481126`). See the C API verification section below.

Remaining board test is image-level, not a code path:

1. Build a unified image containing the new runtime/proxy/stub/service.
2. Boot it and confirm `OH_NNDevice_GetAllDevicesID()` still exposes the X5
   device.
3. Run the same `.bin` through `OH_NNCompilation_Build()` + `RunSync()` without
   bind mounts or `LD_LIBRARY_PATH`.
4. Check the daemon stayed alive and the kernel did not log BPU errors.

## Board probe 2026-11-20

Board: `10.43.9.213:5555`, boot_id
`9ade3a96-6eb4-4876-a3dc-f407990d6b5e`, kernel `6.1.83-rdkhm #6`
(2026-11-19 20:36 CST). This boot is newer than the one recorded in
`board-validation-20261119.md`.

- `PING` -> `PONG`, `NPU_CHECK` -> `NPU_RUNTIME_READY`,
  `NNRT_BACKEND` -> `NNRT_BACKEND_RUNTIME_READY`.
- The new daemon and static ARM64 client were pushed to `/data/local/tmp` and
  run on a private socket. `tests/nnrt-wire-client.cpp` passed: `HELLO`
  succeeded against the real `libdnn.so`, and empty/invalid session, model and
  buffer paths returned `NNRT_INVALID_MODEL` without crashing the process.
- `nnrt-worker --describe /dev/null` loaded the vendor runtime
  (`BPU Platform 1.3.6`, `HBRT 3.15.55.0`, `DNN 1.24.5`) and failed cleanly:
  `MODEL LOAD FAILED: -6000001` ("/dev/null is not a file").
- BPU power state before the run: suspended; cumulative active time about 1.1 s.

### Real inference

Precompiled X5 model downloaded from the official model zoo:

- URL: `https://archive.d-robotics.cc/downloads/rdk_model_zoo/rdk_x5/mobilenetv2_224x224_nv12.bin`
- Local: `out/models/mobilenetv2_224x224_nv12.bin`
- SHA256: `3e2b7c46fc3b3a6d07a5326c0b9632fe98fe5ca38835346ab2eedc22ed427158`
- Board: `/data/local/tmp/mobilenetv2.bin`

`tests/nnrt-infer-client.cpp` loaded the model through the new daemon session:

```text
load status=0 session=1
input 0 [1,3,224,224] type=1 format=2 bytes=75264
output 0 [1,1000,1,1] type=13 format=2 bytes=4000
run status=0
output 0 dims=[1,1000,1,1] sum=1.000000 top=892 value=0.073932
PASS: inference run
```

The output is a 1000-class softmax that sums to 1.0, so the BPU executed the
model. This proves the daemon + `libdnn` + BPU path, not the OH NNRT HDI path.

The runtime warned that the model was built with HBRT `3.15.47.0` while the
installed runtime is `3.15.55.0` (`model builder 1.23.5`). Inference still ran,
but production results should use a matching OpenExplorer toolchain.

### Official `hrt_model_exec` cross-check

The aarch64 `hrt_model_exec` from the downloaded OE package was pushed to
`/data/local/tmp/hrt_model_exec` and run through the private loader:

- `model_info`: input `data` NV12 `(1,3,224,224)` 75264 bytes; output `prob`
  F32 `(1,1000,1,1)` 4000 bytes.
- `perf --frame_count 200 --thread_num 1`: average 1.514 ms, 656 FPS
  (another run measured 1.476 ms / 673 FPS).
- `infer` on the same `0x80` NV12 input: class `892`, score `0.0739321`.

The class and score match the private-daemon result exactly (`top=892`,
`value=0.073932`), so the daemon path and the vendor runtime agree. Log:
`out/board-logs/20261120-npu/npu.log`.

This is still the vendor tool plus the private daemon; the OH NNRT HDI service
is not enabled in the flashed image.

### Source enablement

- The `nnrt_host` block is merged into
  `overlay/vendor/drobotics/rdk_x5/hdf_config/uhdf/hdf.hcs`.
- `overlay/vendor/drobotics/rdk_x5/sepolicy/security/public/nnrt.te` defines
  the host and service types, registration and accelerator-socket access.
- `drivers_peripheral_nnrt_x5` is in the product `hdf` subsystem; an `nnrt`
  component and image-verifier checks were added.
- HCS and SELinux policy both compile (`hdf_default.hcb`, `policy.31`).
- `hdf_service_contexts` now maps `nnrt_device_service` to
  `hdf_nnrt_device_service`; the target was regenerated successfully after a
  transient `third_party/libnl/install.sh` race during GN gen.
- `tests/nnrt-capi-test.c` compiles against the NDK and links. On the current
  image it prints `FAIL device list: 0`, as expected before the service is in
  the image.

A `vendor_image` build was run. The target aborted at an unrelated
`deps_guard` check (non-passthrough codec/input/memorytracker/mapper modules),
but the produced `vendor.img` was inspected with `debugfs`:

- `/lib64/libnnrt_driver.z.so` and
  `/lib64/libnnrt_device_service_2.1.z.so` are present (34048 and 13232 bytes).
- `/etc/hdfconfig/hdf_default.hcb` contains `nnrt_host` and
  `nnrt_device_service`.
- `packages/phone/system/etc/selinux/targeted/policy/policy.31` contains
  `nnrt_host` and `hdf_nnrt_device_service`; `hdf_service_contexts` maps
  `nnrt_device_service`.

### Cold boot with kernel 0021

`out/board-logs/20261120-gpu/coldboot-kernel0021.log` shows the NNRT HDF host
starting in userspace:

```text
ServiceStart starting:nnrt_host
ServiceStart started info nnrt_host(pid 754 uid 1000)
Set selinux context 0 for nnrt_host
ServiceExec nnrt_host
```

The host runs as `u:r:nnrt_host:s0`. The capture also showed one permissive
AVC denial for `get` on `sa_device_service_manager`; `nnrt.te` now allows
`samgr:binder call` and `sa_device_service_manager:samgr_class get`. The policy
CIL includes the new rules, but the policy target still aborts at the unrelated
`deps_guard` check.

### OH NNRT C API verification (2026-11-20)

Board: `10.43.9.213:5555`, boot_id
`d39aa3c9-7ac0-4475-8f5e-28d93d73c533`, kernel `#12`
(2026-11-20 16:04 CST). Log:
`out/board-logs/20261120-npu/capi-offline-ok.log`.

The previous run failed inside the OH 6.0 runtime with
`CreateCompiler failed, only support build NN model and NN model cache`.
The three NNRT patches now implement the missing raw-offline path:
accept offline path/buffer, query IO descriptors through the vendor
`GetOfflineModelIO()` HDI method, prepare the raw buffer, and create the
executor with those descriptors.

The C API test now passes end-to-end:

```text
device=11919407101284969601 name=X5-BPU_D-Robotics_v2_1 count=1
inputs=1 outputs=1
input 0 bytes=150528
output 0 bytes=4000
output 0 elements=1000 sum=0.026968 top=473 value=3.481126
PASS: OH NNRT offline model inference
```

`top=473 value=3.481126` matches the private daemon result for the same
ResNet18 `.bin`, so the C API path is executing the same model on the BPU.

This run used hot deployment, not a new image: the new service/stub were
bind-mounted over `/vendor/lib64`, and the runtime/proxy were loaded from
`/data/local/tmp/nnrt-sync` through `LD_LIBRARY_PATH`. The flashed vendor image
still contains the 2026-11-20 12:06 service. A unified image build is required
before the fix survives a reboot.

The `interface token check failed` lines are the v1.0/v2.0 backend probes; the
v2.1 device is registered and named `X5-BPU_D-Robotics_v2_1`.

The `deps_guard` failure is not NNRT-specific.

### ONNX conversion

The runtime only executes compiled models. ONNX -> `.bin` (PTQ) or `.hbm` (QAT)
requires the Horizon `hbdk` / OpenExplorer toolchain plus calibration data for
PTQ. The OE package is installed in `thirdparty/toolchains/oe_x5/venv`, and a
ResNet18 ONNX was converted to `.bin` on 2026-11-20 (3.17 ms / 314 FPS on the
board, no HBRT version warning). See [model-conversion.md](model-conversion.md)
for commands, calibration requirements and the QAT flow.

Temporary board files left for reuse: `/data/local/tmp/accelerator-daemon`,
`/data/local/tmp/nnrt-wire-client`, `/data/local/tmp/nnrt-infer-client`,
`/data/local/tmp/accel-client`, `/data/local/tmp/mobilenetv2.bin`,
`/data/local/tmp/resnet18.bin`, `/data/local/tmp/input_nv12.bin`.

## Limits

- Only precompiled vendor models (`.bin` / `.hbm`) are accepted; ONNX is not accepted at runtime.
- No operator-graph compilation.
- No model cache, dynamic shape, float16, performance or priority settings.
- Board inference is proven through both the OH NNRT C API and the private daemon; the hot-deployed fix is not yet in a flashed image.
- ONNX conversion is proven for ResNet18; robot-policy ONNX files are not converted or validated.
- `bringup/probes/accel_wire.h` and the copy in
  `drivers/peripheral/nnrt/include/accel_wire.h` must stay identical.
