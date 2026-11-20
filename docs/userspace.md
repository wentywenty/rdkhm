# OpenHarmony userspace work

The pinned 6.0 manifest is synchronized with the default project group into
`sources/oh/openharmony-full`. `out/openharmony-resolved.xml` records exact commits.
The kernel dependency checkouts in `sources/oh/openharmony` remain separate.
The standard-only group omits `third_party/harfbuzz` even though the rich product
inherits its component; the default group includes all 456 pinned projects.

`overlay/vendor/drobotics/rdk_x5` defines an ARM64 standard-system integration
target based on upstream `standard_system.json`, `rich.json`, and
`chipset_common.json`. Generic supplemental components are compared against the
same-release reference product; its `rockchip_products` implementation is not
included. The rich
component baseline is needed because 6.0 core services pull in application and
graphics components. X5 display and Launcher packaging are integrated;
runtime validation remains pending. JS build support is enabled.
The 2D graphics configuration keeps shared GPU interfaces but disables OpenGL
and Vulkan backends for CPU rendering. This configuration is not a verified
software-rendering implementation on X5.
SELinux policy generation is enabled for `rdk_x5`; the development boot script
runs `selinux=1 enforcing=0`. Production enforcing policy and device permissions
still require separate validation and AVC review. Kernel and DTBs continue to be
built outside the OH graph.
The standard build includes updater libraries required by other components;
no updater is included in the separate kernel bring-up image. SD partition and
OTA qualification remains pending; SD partition and mount integration are present.

## HAP builds

`config/build/haps.json` is the app registry. `scripts/build-hap.py` builds,
signs and stages one app; `verified: false` entries require `--force`.
Per-app build fixes are kept under `patches/haps/`, for example
`admin_provisioning-build-config.patch` and `theme-build-config.patch`.
Both apps build, sign and are marked `verified=true`; their HAPs are
`out/haps/admin_provisioning.hap` and `out/haps/theme.hap`.
Image assembly currently injects Settings, Camera, Photos, Launcher, SystemUI,
ScreenLock, Notes and PinTool HAPs; admin_provisioning, theme, contacts and mms
remain build artifacts until their packaging path is changed.

## Settings NearLink page

`patches/settings/0003-nearlink-settings-page.patch` adds a read-only
Settings > 星闪 page. It reports whether the USB module (`ffff:3733`) is
enumerated and whether `SystemCapability.Communication.NearLink` is exported;
it does not provide pairing because no NearLink service or HDI is integrated.

The image packages the prebuilt Settings HAP by default. Run
`./build hap settings` (or `python3 scripts/build-hap.py settings`) to build,
sign and stage `out/settings/Settings.hap`; `make-openharmony-image.sh`
replaces the system HAP when that file exists. `build-settings-hap.sh` remains
a compatibility wrapper around the generic builder. This is a source and
packaging change only, not a board-verified feature.

Other rebuilt HAPs live under `out/haps/` (for example `contacts.hap`,
`mms.hap`). The image builder does not inject them automatically; see
`docs/hap-tasks.md` T12 for the current mapping gap.

## Environment findings

1. The default prebuilt endpoint returned HTTP 403 to the upstream downloader.
   `--tool-repo https://mirrors.huaweicloud.com` successfully downloaded tools.
2. The release pins Node 14.21.1 but `declgen_ts2sts` requested rimraf 6.0.1,
   whose dependency chain failed on a missing `diagnostics_channel.tracingChannel`.
   `patches/ark-runtime/0001-node14-rimraf.patch` pins rimraf 5.0.10. Its npm
   installation and postinstall compilation then completed.
3. The prebuilt Python archive was downloaded correctly but its first extraction
   was incomplete. Upstream schedules the same archive for multiple destinations
   and does not propagate all extraction errors. Re-extracting the verified
   archive restored the missing executable. Archive SHA256:
   `9afb88572822af9bcdfd96b0c9726efed084608723c15a874978e35c67a55d1d` for
   `python-linux-x86-GLIBC2.35-3.11.4_20250807.tar.gz`.
   `prepare-openharmony.sh` now installs this verified archive sequentially in
   both destinations before running the upstream downloader. It targets an
   x86_64 host with glibc 2.35 or newer, matching this machine.
4. `build-openharmony.sh` uses upstream `build.py`, which calls hb, rather than
   the shell wrapper that writes global npm/ohpm configuration under HOME.
5. The device manager unconditionally included a HAP except for a hard-coded
   QEMU product. `patches/device-manager/0001-respect-headless-product.patch`
   also requires `support_jsapi` before adding that HAP and `load_test_config`
   before adding test modules to the service group. The current product keeps
   JS support enabled to satisfy other core components. Neither change
   implements display.
6. libnl's GN-time preparation script attempted `apt-get update/install` and
   failed without root privileges, although autoconf/automake/libtool were
   already installed. `patches/libnl/0001-use-installed-host-tools.patch` checks
   those tools instead of invoking the host package manager.

The wrapper uses `--ninja-args=-j16` (`JOBS` overrides this); upstream ignores the
deprecated `--jobs` argument. Test-target loading is disabled for this initial
system-component build, so it is not a test-suite run.

Logs are under `out/logs/openharmony-*`. The presence of downloaded tools or a
passed product preloader does not imply a completed userspace build.

The final `rdk_x5` configuration builds the full `images` target successfully,
including native init, RenderService, ArkUI and system HAPs. Filesystems are in
`sources/oh/openharmony-full/out/rdk_x5/packages/phone/images`. Upstream startup
guard findings about service jobs, DAC identities and library whitelists remain;
successful compilation does not imply runtime acceptance. SELinux policy
generation is enabled with X5 device labels, but board AVC review and a
dedicated service domain for accelerator access are still required.

## Subsequent integration

See [system-integration.md](system-integration.md) for the new display, HDF,
HDC, HAP and SD packaging integration. Both display VDI libraries now compile.
The complete system build and first SD assembly have succeeded.

## Still needed for the full system

- Runtime validation of ARM64 system/root/vendor mount and init integration.
- Graphics, input, HDC and Launcher/HAP execution on the board.
- SELinux policy, startup-guard findings and recovery/OTA qualification.
- Physical X5 startup, HDMI/input, application launch and reboot validation.

The legacy display allocator is not fully generic: the default-standard
`DrmAllocator::GetPhysicalAddr` calls `DRM_IOCTL_HISILICON_GEM_FD_TO_PHYADDR`.
The new X5 integration instead patches the newer VDI backend for DRM/GEM.
