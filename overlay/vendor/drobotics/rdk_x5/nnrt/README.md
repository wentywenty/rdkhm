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

## Enablement state

Source enablement is complete:

- the `nnrt_host` block is merged into `hdf_config/uhdf/hdf.hcs`;
- `sepolicy/security/public/nnrt.te` and `hdf_service_contexts` are present;
- `drivers_peripheral_nnrt_x5` is part of the product `hdf` subsystem;
- an `nnrt` component and image-verifier checks exist.

The HCS, SELinux policy and `hdf_service_contexts` generation all pass. A
`vendor_image` build aborted at an unrelated `deps_guard` check, but the
produced vendor image contains both NNRT libraries and the `nnrt_host` HCB
block; the system policy contains the NNRT types. The remaining step is a
successful unified image build and flash, then
`OH_NNCompilation_ConstructWithOfflineModelFile()` with a real model.
`tests/nnrt-capi-test.c` is ready; on the current image it reports zero
devices.
