# X5 NNRT backend integration

Status of the OpenHarmony Neural Network Runtime (NNRt) path on the X5 BPU.

| Item | State |
| --- | --- |
| Source and patch | present |
| Component build | passed (2026-11-19) |
| Installed in an image | not yet |
| HDF host enabled | no |
| Board inference | passed via private daemon (MobileNetV2, 2026-11-20) |
| Real X5 model | `mobilenetv2_224x224_nv12.bin` downloaded |

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
2. NNRT core calls `PrepareOfflineModel()` with the model bytes in a
   `SharedBuffer`.
3. The HDI service forwards the fd to the daemon, which calls
   `hbDNNInitializeFromDDR()`.
4. `IPreparedModel::Run()` forwards input/output shared buffers to
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

Component-only build, no image assembly:

```sh
scripts/build-target.sh drivers/peripheral/nnrt:libnnrt_driver
```

Observed on 2026-11-19: `rdk_x5 build success`, about one minute.

Artifacts:

- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_driver.z.so`
- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_device_service_2.1.z.so`
  (exports `NnrtDeviceImplGetInstance`, `NnrtDeviceImplRelease`)

Neither artifact is installed into `packages/phone` by the component target;
that happens on a unified image build.

## Enabling on a board

The libraries are intentionally not activated yet:

1. Merge `overlay/vendor/drobotics/rdk_x5/nnrt/nnrt_device.hcs` into
   `overlay/vendor/drobotics/rdk_x5/hdf_config/uhdf/hdf.hcs`.
2. Add SELinux rules for the NNRT HDF host to connect to
   `/dev/unix/socket/rdkhm_accel`. Check the actual host domain and socket label
   from `dmesg`/AVC logs before adding broad rules.
3. Build an image and confirm both `.so` files are in `/vendor/lib64`.
4. Push a real `.hbm` model and run the NNRT C API test described below.

Do not add permissive rules or a global SELinux exception just to make the host
start.

## Verification plan

Already covered offline:

- daemon text probes and fragmented frames;
- binary framing, invalid sessions, empty inline model, empty model fd;
- C++ transport client against the ARM64 daemon under QEMU;
- component build and exported factory symbols.

Board inference through the **private daemon path** passed on 2026-11-20 with
MobileNetV2; see the board probe below. The **OH NNRT HDI/API path** is still
untested because the service is not enabled in an image.

Remaining board test:

1. `OH_NNDevice_GetAllDevicesID()` exposes the X5 device.
2. `OH_NNCompilation_ConstructWithOfflineModelFile("/data/mobilenetv2.bin")`.
3. `OH_NNCompilation_SetDevice()` + `OH_NNCompilation_Build()`.
4. Allocate input/output tensors, run, compare the output against the private
   daemon result.
5. Check the daemon stayed alive and the kernel did not log BPU errors.

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
is not enabled in an image.

### ONNX conversion

The runtime only executes compiled models. ONNX -> `.bin` (PTQ) or `.hbm` (QAT)
requires the Horizon `hbdk` / OpenExplorer toolchain plus calibration data for
PTQ. The official X5 OE package is downloaded and extracted under
`thirdparty/toolchains/oe_x5/`; its wheels are not installed yet, and no ONNX
has been converted. See [model-conversion.md](model-conversion.md) for the
toolchain contents, install steps, PTQ/QAT flow, and precompiled model sources.

Temporary board files left for reuse: `/data/local/tmp/accelerator-daemon`,
`/data/local/tmp/nnrt-wire-client`, `/data/local/tmp/nnrt-infer-client`,
`/data/local/tmp/accel-client`, `/data/local/tmp/mobilenetv2.bin`.

## Limits

- Only `.hbm` offline models are accepted.
- No operator-graph compilation.
- No model cache, dynamic shape, float16, performance or priority settings.
- Board inference is proven only through the private daemon; the OH NNRT HDI/API path is still untested.
- ONNX conversion has the OE toolchain downloaded but not installed; see model-conversion.md.
- `bringup/probes/accel_wire.h` and the copy in
  `drivers/peripheral/nnrt/include/accel_wire.h` must stay identical.
