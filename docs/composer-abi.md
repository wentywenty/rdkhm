# Composer VDI ABI correction

The serial hilog capture on 2026-11-16 shows `LoadVdiAdapter:113` failing at
31.163 seconds because `RegHotPlugCallback` is null. At 37.191 seconds the
partially initialized composer service rejects `InitCmdRequest`. The client
cannot create HdiDevice, RSScreenManager initialization fails, and RenderService
returns -1 (exit status 255). Its configured restart job resets foundation,
allocator_host and composer_host. Repeated foundation resets reach its critical
service threshold and init deliberately triggers a panic reboot.

The service loads `libdisplay_composer_vdi_impl_default.z.so` and calls dlsym
for independent C exports. The default implementation previously exposed
`CreateComposerVdi`, `DestroyComposerVdi` and C++ methods, with no matching C
entry points. This is independent of whether the kernel DRM driver probes.

Patch `patches/display/0002-composer-c-entrypoints.patch` adds the 38 mandatory
C entry points to the default VDI, forwarding to the existing implementation.
A function-local static instance follows the library lifetime. Every wrapper
has a static_assert against DisplayComposerVdiAdapter's function pointer type.
Existing factory exports remain available. Patch 0002 also exports the v1.1
`RegRefreshCallback` and triggers it after a successful power-on; other v1.1
operations retain the existing HDF_ERR_NOT_SUPPORT return.

Patch `patches/display/0007-composer-release-entrypoint.patch` adds the
`DisplayComposerImplRelease` export for the service lifetime; the image verifier
now checks both `DisplayComposerImplGetInstance` and `DisplayComposerImplRelease`
in the packaged `libdisplay_composer_service_1.3.z.so`.

`scripts/check-composer-abi.py` derives the required exports from LoadVdiAdapter
and checks defined public function symbols in the packaged ELF. It rejects the
old library. The SD image verifier runs this check on the extracted VDI library,
in addition to checking that it matches the userspace build output. The patch
is applied by prepare-openharmony.sh after the existing software DRM patch.

Build and symbol verification do not establish DRM modesetting, buffer transfer,
HDMI output or desktop launch. Automatic hilog capture remains enabled for the
next board boot; service restart protections are unchanged.

## Known gap: v1.1/v1.2 entry points

The service `dlsym`s 62 entry points across `LoadVdiFuncPart1/2/3`. Patch 0002
covers the 38 v1.0 functions plus `RegRefreshCallback`. The default VDI still
lacks 22 later entries,
including `RegDisplayVBlankIdleCallback`,
`GetDisplaySupportedModesExt`, `SetDisplayModeAsync`, the per-frame parameter
functions, hardware-cursor functions and `FastPresent`. The 2026-11-17 board log
recorded `RegRefreshCallback` returning not-support on the older image. The
current patch exports and invokes it, and exports `GetDisplaySupportedColorGamuts`
with an sRGB answer so `RSScreen::GetScreenColorGamut` stops failing. `check-composer-abi.py` now enforces the
Part1 set plus `RegRefreshCallback` and `GetDisplaySupportedColorGamuts` and
reports the remaining 22 optional
entries as a warning; implementing those callbacks remains follow-up work.

Validation on 2026-11-16: the full `images` build completed successfully. The
packaged library and the library extracted from the SD image both passed all
38 required export checks. Image verification passed MBR, checksum, all four
filesystems and 134 packaged artifact comparisons. Logs are retained in
`out/logs/build-composer-abi.log` and `out/logs/image-composer-abi.log`.
The rebuilt `out/images/rdkhm-x5-openharmony-dev.img` SHA256 is
`0e500a5ae1947ece517a57d940c4fe2bfe1df9187205f44cadbc4c37f45a7e31`.
