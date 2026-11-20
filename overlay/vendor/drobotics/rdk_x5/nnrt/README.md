# X5 NNRT HDI service

Full design and status: `docs/nnrt-backend.md`.

Source lives in `patches/nnrt/0001-x5-nnrt-hdi-service.patch`; `prepare-openharmony.sh`
applies it into `drivers/peripheral/nnrt`. This directory keeps only the
product-side HCS fragment and these notes.

## Build result

Built successfully with a component build, not a full image:

```sh
scripts/build-target.sh drivers/peripheral/nnrt:libnnrt_driver
```

Artifacts:

- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_driver.z.so`
- `out/rdk_x5/hdf/drivers_peripheral_nnrt_x5/libnnrt_device_service_2.1.z.so`
  (exports `NnrtDeviceImplGetInstance` and `NnrtDeviceImplRelease`)

`drivers_peripheral_nnrt_x5` is declared in `bundle.json`.
`overlay/vendor/drobotics/rdk_x5/config.json` adds it to the `hdf` subsystem.

## Design

- HDI service: `ohos.hdi.nnrt.v2_1.INnrtDevice` + `IPreparedModel`.
- The service is musl-linked and never loads `libdnn.so`. It forwards model
  bytes and tensor buffers over `/dev/unix/socket/rdkhm_accel` to the private
  glibc `accelerator-daemon`, which owns `hbDNN*`.
- Only the vendor offline-model path is supported:
  `OH_NNCompilation_ConstructWithOfflineModelFile/Buffer` →
  `PrepareOfflineModel()` → daemon `hbDNNInitializeFromDDR()`.
- `PrepareModel()` (operator graph) returns `NNRT_NOT_SUPPORT`;
  `GetSupportedOperation()` reports all nodes unsupported.

## Still required before use

1. Merge `nnrt_device.hcs` into
   `overlay/vendor/drobotics/rdk_x5/hdf_config/uhdf/hdf.hcs`.
2. Add SELinux rules for the HDF host to connect to the accelerator socket and
   access `/dev/bpu*` as needed.
3. Build an image and verify that
   `/vendor/lib64/libnnrt_driver.z.so` and
   `/vendor/lib64/libnnrt_device_service_2.1.z.so` are installed.
4. Run a real Horizon `.hbm` model through
   `OH_NNCompilation_ConstructWithOfflineModelFile()` and verify output.

No HBM inference has been run on hardware.
