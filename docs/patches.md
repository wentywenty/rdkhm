# Patch inventory

Generated from `config/patches.json`.

2026-11-19 reconcile（`out/patch-*` + 历史会话）结果见
[patches-reconcile-20261119.md](patches-reconcile-20261119.md)。
`out/patch-*` 的 248 个文件是历史快照/重复内容，不等于 active 123。

| Collection | Count |
| --- | --- |
| `kernel` | 22 |
| `kernel-rt` | 1 |
| `openharmony` | 97 |

All files are registered, and `check-patch-format.py` / `check-patch-coverage.py` pass. 2026-11-19 adds launcher/0004, screenlock/0003 and settings/0004; 2026-11-20 adds qemu/0004 and hdc/0001; current manifest is 120 listed / 123 files. The `kernel-rt` entry is optional (PREEMPT_RT) and is applied only when `RDKHM_KERNEL_PROFILE=rt`.

## Kernel

| Patch | Purpose |
| --- | --- |
| `kernel/0001-openharmony-core.patch` | openharmony core |
| `kernel/0002-builtin-display-bridge.patch` | builtin display bridge |
| `kernel/0003-display-deferred-probe-devres.patch` | display deferred probe devres |
| `kernel/0004-rdk-direct-scanout.patch` | rdk direct scanout |
| `kernel/0005-display-object-list-lifetime.patch` | display object list lifetime |
| `kernel/0006-accesstoken-ioctl-noise.patch` | accesstoken ioctl noise |
| `kernel/0007-rtg-qos-proc.patch` | rtg qos proc |
| `kernel/0008-trace-eval-null-guard.patch` | trace eval null guard |
| `kernel/0009-qos-proc-unconditional.patch` | qos proc unconditional |
| `kernel/0010-fixed-mac.patch` | fixed mac |
| `kernel/0011-fix-ethernet-mac-buffer.patch` | fix ethernet mac buffer |
| `kernel/0012-rtg-ioctl-compat.patch` | rtg ioctl compat |
| `kernel/0013-wdt-disable-on-suspend.patch` | wdt disable on suspend |
| `kernel/0014-wdt-force-disable.patch` | wdt force disable |
| `kernel/0015-vs-drm-runtime-pm-balance.patch` | vs drm runtime pm balance |
| `kernel/0016-aic8800-cmd-recovery.patch` | aic8800 cmd recovery |
| `kernel/0017-aic8800-sdio-power-toggle.patch` | aic8800 sdio power toggle |
| `kernel/0018-tcan-spi-max-speed.patch` | tcan spi max speed |
| `kernel/hdf-core/0001-arm64-kernel-build.patch` | arm64 kernel build |

## OpenHarmony

### ability-runtime (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `ability-runtime/0001-dialog-want-import.patch` | `ability_runtime` | dialog want import |

### account (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `account/0001-empty-index-object.patch` | `os_account` | empty index object |

### ace-engine (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `ace-engine/0001-pixelmap-ani-dependency.patch` | `ace_engine` | pixelmap ani dependency |

### ace-ets2bundle (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `ace-ets2bundle/0001-host-gcc.patch` | `ace_ets2bundle` | host gcc |

### ark-runtime (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `ark-runtime/0001-node14-rimraf.patch` | `runtime_core` | node14 rimraf |

### audio (5)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `audio/0001-x5-alsa-integration.patch` | `peripheral` | x5 alsa integration |
| `audio/0002-optional-sink-aux.patch` | `audio_framework` | optional sink aux |
| `audio/0003-default-effect-channel.patch` | `audio_framework` | default effect channel |
| `audio/0004-optional-running-lock.patch` | `audio_framework` | optional running lock |
| `audio/0005-running-lock-optional.patch` | `audio_framework` | running lock optional |

### build-host (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `build-host/0001-select-host-gcc.patch` | `build` | select host gcc |
| `build-host/0002-hvigor-nodejs18.patch` | `build` | build: use Node 18 for hvigor |
| `build-host/0003-compile-app-hvigor26.patch` | `build` | build: compile apps with hvigor 26 |

### bundlemanager (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `bundlemanager/0001-optional-bms-extension.patch` | `bundle_framework` | optional bms extension |

### calendardata (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `calendardata/0001-calendar-month-page.patch` | `calendardata` | calendar month page |

### call (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `call/0001-strict-null.patch` | `call` | call: fix strict-null and TS/ArkTS import errors |

### camera (6)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `camera/0001-lazy-save-asset.patch` | `camera` | camera: lazy-init media asset to avoid startup freeze |
| `camera/0002-vdi-basic-stream-config.patch` | `peripheral` | camera: emit valid UVC basic stream configurations |
| `camera/0003-init-race.patch` | `camera` | camera: wait for first init before publishing capability |
| `camera/0004-bringup-permission-gate.patch` | `camera` | bringup permission gate |
| `camera/0005-open-without-await.patch` | `camera` | open without await |
| `camera/0006-session-commit-timeout.patch` | `camera` | session commit timeout |

### contacts (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `contacts/0001-bringup-permission-gate.patch` | `contacts` | contacts: render UI when permissions are already granted |

### contacts-data (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `contacts-data/0001-allow-unverified-account.patch` | `contacts_data` | contacts_data: allow data ability without verified account |

### device-manager (2)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `device-manager/0002-optional-resident-log.patch` | `device_manager` | optional resident log |
| `device-manager/0001-respect-headless-product.patch` | `device_manager` | respect headless product |

### device-profile (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `device-profile/0001-optional-sync-adapter.patch` | `device_info_manager` | optional sync adapter |

### display (8)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `display/0001-x5-software-drm.patch` | `peripheral` | x5 software drm |
| `display/0002-composer-c-entrypoints.patch` | `peripheral` | composer c entrypoints |
| `display/0003-crtc-mask-selection.patch` | `peripheral` | crtc mask selection |
| `display/0004-drm-power-and-present.patch` | `peripheral` | drm power and present |
| `display/0005-primary-plane-zpos.patch` | `peripheral` | primary plane zpos |
| `display/0006-primary-plane-format.patch` | `peripheral` | primary plane format |
| `display/0007-composer-release-entrypoint.patch` | `peripheral` | composer release entrypoint |
| `display/0008-display-buffer-metadata-noop.patch` | `peripheral` | display buffer metadata noop |

### dsoftbus (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `dsoftbus/0001-optional-client-plugin.patch` | `dsoftbus` | optional client plugin |

### ets-frontend (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `ets-frontend/0001-node14-rimraf.patch` | `ets_frontend` | node14 rimraf |

### filemanager (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `filemanager/0001-fileaccess-extension-exported.patch` | `user_file_service` | filemanager: export FileExtensionAbility for picker discovery |

### graphic2d (4)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `graphic2d/0001-software-render-build.patch` | `graphic_2d` | software render build |
| `graphic2d/0002-render-service-image-manager-guards.patch` | `graphic_2d` | render service image manager guards |
| `graphic2d/0003-app-server-drawable-split.patch` | `graphic_2d` | app server drawable split |
| `graphic2d/0004-client-drawable-guards.patch` | `graphic_2d` | client drawable guards |

### graphic3d (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `graphic3d/0001-host-shader-toolchain.patch` | `graphic_3d` | host shader toolchain |

### haps (12)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `haps/applications_auth_widget-null-guards.patch` | `applications_auth_widget` | applications_auth_widget null guards |
| `haps/call-build-config.patch` | `call` | haps: call build configuration |
| `haps/theme-build-config.patch` | `theme` | theme build config |
| `haps/printspooler-build-config.patch` | `printspooler` | printspooler build config |
| `haps/admin_provisioning-build-config.patch` | `admin_provisioning` | admin_provisioning build config |
| `haps/camera-build-config.patch` | `camera` | camera build config |
| `haps/systemui-build-config.patch` | `systemui` | systemui build config |
| `haps/systemui-resource-manager.patch` | `systemui` | systemui resource manager |
| `haps/notes-resources.patch` | `notes` | notes: add missing shared resources |
| `haps/notes-db-init.patch` | `notes` | notes: add local persistence fallback when rdb is unavailable |
| `haps/contacts-arkts-worker-migration.patch` | `contacts` | contacts: migrate workers and mark singleton |
| `haps/mms-arkts-worker-migration.patch` | `mms` | mms: migrate workers and mark singleton |

### input (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `input/0001-evdev-touch-capabilities.patch` | `peripheral` | evdev touch capabilities |

### launcher (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `launcher/0001-create-window-before-rdb.patch` | `launcher` | create window before rdb |
| `launcher/0002-rdk-desktop-experiment.patch` | `launcher` | rdk desktop experiment |
| `launcher/0003-style-config-fallback.patch` | `launcher` | launcher: fall back to default desktop style config |
| `launcher/0004-bringup-desktop-fallbacks.patch` | `launcher` | launcher: remaining bring-up fallbacks |

### libnl (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `libnl/0001-use-installed-host-tools.patch` | `libnl` | use installed host tools |

### media-foundation (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `media-foundation/0001-avbuffer-default-memory-type.patch` | `media_foundation` | avbuffer default memory type |

### media-library (2)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `media-library/0001-skip-user-unlock-check.patch` | `media_library` | skip user unlock check |
| `media-library/0002-datashare-config.patch` | `media_library` | datashare config |

### nnrt (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `nnrt/0001-x5-nnrt-hdi-service.patch` | `peripheral` | x5 nnrt hdi service |
| `nnrt/0002-vendor-offline-model-io.patch` | `interface` | vendor offline model IO descriptors |
| `nnrt/0003-raw-offline-runtime.patch` | `neural_network_runtime` | raw offline model runtime support |

### photos (2)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `photos/0001-photos-resources.patch` | `photos` | photos resources |
| `photos/0002-defer-media-library.patch` | `photos` | photos: defer media library init until after UI |

### resourceschedule (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `resourceschedule/0001-pin-auth-secon.patch` | `resource_schedule_service` | pin auth secon |
| `resourceschedule/0002-bundle-active-optional.patch` | `device_usage_statistics` | bundle active optional |
| `resourceschedule/0003-pin-auth-hdf-args.patch` | `resource_schedule_service` | pin auth hdf args |

### screenlock (2)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `screenlock/0001-unlock-without-account.patch` | `screenlock` | unlock without account |
| `screenlock/0002-default-unlocked.patch` | `screenlock_mgr` | default unlocked |
| `screenlock/0003-auto-unlock-fallbacks.patch` | `screenlock` | screenlock: auto-unlock/resource fallbacks |

### security-component (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `security-component/0001-optional-enhance-log.patch` | `security_component_manager` | optional enhance log |
| `security-component/0002-device-auth-syscap.patch` | `device_auth` | device auth syscap |
| `security-component/0003-deviceauth-sandbox.patch` | `device_auth` | deviceauth sandbox |

### settings (3)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `settings/0001-storage-statvfs.patch` | `settings` | storage statvfs |
| `settings/0002-storage-uri.patch` | `settings` | storage uri |
| `settings/0003-nearlink-settings-page.patch` | `settings` | nearlink settings page |
| `settings/0004-module-config.patch` | `settings` | settings: remove home skill from module config |

### tee (1)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `tee/0001-teecd-device-ownership.patch` | `tee_client` | teecd device ownership |

### window-manager (2)

| Patch | Repository | Purpose |
| --- | --- | --- |
| `window-manager/0001-input-window-display-id.patch` | `window_manager` | input window display id |
| `window-manager/0002-input-display-binding-test.patch` | `window_manager` | input display binding test |

## QEMU product support (2026-11-20)

These patches make the in-tree QEMU products buildable with the 6.0 component
tree. They are not used by the X5 image.

| Patch | Repo | Purpose |
| --- | --- | --- |
| `qemu/0001-device-subsystem-and-foundation-profile.patch` | `device/qemu` | align the device subsystem name with the board, add the minimal foundation profile |
| `qemu/0002-product-configs.patch` | `vendor/ohemu` | align min/arm64/headless product configs with 6.0 components |
| `qemu/0003-qemu-min-no-foundation.patch` | `foundation/systemabilitymgr/safwk` | disable foundation critical service in minimal QEMU products |
| `qemu/0004-hdc-tcp-init.patch` | `device/qemu` | start HDC TCP in arm virt; install init and para files |
| `hdc/0001-hdcd-root-tcp.patch` | `developtools/hdc` | add `-t` to the root hdcd service |
| `build-host/0004-qemu-product-whitelist.patch` | `build` | whitelist `product_qemu-arm64-linux-min` and `product_qemu-arm-linux-headless` |
| `hdf-core/0001-optional-rk3566-audio.patch` | `drivers/hdf_core` | only descend into the kaihong audio dir when it exists |
| `samgr/0001-install-samgr-common.patch` | `foundation/systemabilitymgr/samgr` | install `libsamgr_common.z.so` into the image |
| `ffmpeg/0001-disable-vulkan-cplat.patch` | `third_party/ffmpeg` | disable Vulkan in the non-aarch64 configuration |

Build-time settings that are not patches:

- `--gn-args 'linux_kernel_version="linux-5.10" load_test_config=false'`
- host GCC 12 C++ header/static-libstdc++ symlinks for the prebuilt clang.

## Globbed and optional

- `nearlink-bsp` → `sources/rdk/ws73-bsp-94a02d3a`
- `nearlink-ssap` → `sources/oh/nearlink-ssap`
- `optional/preempt-rt/patch-6.1.83-rt28.patch` (not applied in the default profile)

## Working-tree changes not covered by the manifest

2026-11-19: launcher/screenlock/settings 的剩余源码已捕获到
`launcher/0004`、`screenlock/0003`、`settings/0004`，且已在干净 worktree 验证；
下面列表保留为历史记录。生成型文件仍不应进入 patch：

| App | Files |
| --- | --- |
| launcher | `product/phone/src/main/ets/MainAbility/MainAbility.ts`, `common/src/main/ets/default/manager/ResourceManager.ts`, `common/src/main/ets/default/layoutconfig/PageDesktopLayoutConfig.ts`, `common/src/main/ets/default/layoutconfig/PageDesktopAppModeConfig.ts`, `common/src/main/ets/default/manager/LauncherAbilityManager.ts` |
| screenlock | `product/phone/src/main/ets/pages/slidescreenlock.ets`, `product/phone/src/main/resources/base/element/float.json` |
| settings | `product/phone/src/main/module.json5` |

Before building a fresh image or handing the tree to another machine, generate patches for these files (or intentionally drop them) and run `apply-patches.py --record` after verifying the apply state.

## Notes

- `out/patches-state/` records the last explicit `--record`; the state may be stale after parallel patch edits. Verify with `git -C <repo> apply --reverse --check <patch>` or re-record only after confirming.
- `apply-patches.py --only openharmony --dry-run` can fail while another worker has an incomplete patch; validate a single patch against its own repo.
