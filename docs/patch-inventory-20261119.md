# Patch inventory — 2026-11-19

本页是 `config/patches.json` 与 `patches/` 的完整盘点。**镜像和板端状态不能由 patch 清单替代**；最近的多媒体结论见 [camera-media-photos-20261119.md](camera-media-photos-20261119.md)。

## 计数

- manifest 显式列出：**120** 个 patch
  - `kernel`: 22
  - `kernel-rt`: 1（optional，仅 RT profile）
  - `openharmony`: 97
- `patches/` 实际 `.patch` 文件：**123** 个
- glob 管理的额外 patch：**3** 个（`nearlink-bsp` 2、`nearlink-ssap` 1；不在 openharmony 显式列表中）
- `./rdkhm check` 当前报告 120 listed / 123 files present；glob/optional 文件由 coverage 脚本按规则处理。
- 所有 patch 统一使用 `From/Subject/Signed-off-by` 头；`check-patch-format.py` 最近一次为 0 failure。

### 2026-11-20 增量

| Patch | Repo | 用途 |
| --- | --- | --- |
| `qemu/0004-hdc-tcp-init.patch` | `device/qemu` | QEMU arm virt 启动 HDC TCP，安装 init/para |
| `hdc/0001-hdcd-root-tcp.patch` | `developtools/hdc` | root `hdcd` service 增加 `-t` |

下方按领域表格是 2026-11-19 快照，不重排编号；当前计数以上方为准。

## 按领域计数

| 领域 | 数量 | 说明 |
| --- | ---: | --- |
| `ability-runtime` | 1 | Dialog want import |
| `account` | 1 | 空账号索引对象 |
| `ace-engine` | 1 | PixelMap ANI 依赖 |
| `ace-ets2bundle` | 1 | host GCC/ArkTS bundle |
| `ark-runtime` | 1 | Node14 rimraf |
| `audio` | 5 | X5 ALSA、可选 sink、effect、running lock |
| `build-host` | 3 | Host GCC、hvigor Node18、hvigor26 编译 |
| `bundlemanager` | 1 | 可选 BMS extension |
| `calendardata` | 1 | 日历数据页 |
| `call` | 1 | CallUI strict-null/ArkTS/可见性 |
| `camera` | 6 | 相机启动、VDI、init、权限、session |
| `contacts` | 1 | Contacts 权限门禁 |
| `contacts-data` | 1 | Contacts DataAbility 账号校验 |
| `device-manager` | 2 | headless/serial log |
| `device-profile` | 1 | 可选 sync adapter |
| `display` | 8 | X5 软件 DRM、composer VDI、plane/format/power |
| `dsoftbus` | 1 | 可选 client plugin |
| `ets-frontend` | 1 | Node14 rimraf |
| `filemanager` | 1 | FileExtensionAbility exported |
| `graphic2d` | 4 | 软件渲染 build、RenderService/drawable guards |
| `graphic3d` | 1 | host shader toolchain |
| `haps` | 12 | 系统 HAP 构建配置/资源/ArkTS worker 迁移 |
| `input` | 1 | evdev 触摸能力 |
| `kernel` | 19 | X5 Linux 6.1 补丁：Binder/Ashmem/AccessToken、DRM/HDMI、输入、音频、MAC、WDT、Wi-Fi、TCAN |
| `launcher` | 4 | Launcher 启动顺序、桌面实验、style config 兜底 |
| `libnl` | 1 | host tools |
| `media-foundation` | 1 | AVBuffer 默认内存类型 |
| `media-library` | 2 | MediaLibraryData 解锁检查与 DataShare 配置 |
| `nearlink-bsp` | 2 | WS73 BSP Linux 6.1/firmware 参数（glob） |
| `nearlink-ssap` | 1 | WS73 SSAP OHOS clang 兼容（glob） |
| `nnrt` | 1 | X5 NNRT HDI service |
| `optional` | 1 | PREEMPT_RT 6.1.83-rt28（`kernel-rt` collection） |
| `photos` | 2 | Photos 资源与媒体库延迟 |
| `resourceschedule` | 3 | pin_auth、bundle_active 可选依赖 |
| `screenlock` | 3 | 无账号/默认解锁相关屏幕锁行为 |
| `security-component` | 3 | 可选 enhance log、device-auth syscap/sandbox |
| `settings` | 4 | Settings 存储、星闪页面 |
| `tee` | 1 | teecd 设备 ownership |
| `window-manager` | 2 | 输入窗口 displayId 绑定 |

## 全部 patch

| # | 领域 | Patch | 仓库 | 摘要 |
| ---: | --- | --- | --- | --- |
| 1 | `kernel` | `kernel/0001-openharmony-core.patch` | `rdk/x5-kernel` | openharmony core |
| 2 | `kernel` | `kernel/0002-builtin-display-bridge.patch` | `rdk/x5-kernel` | builtin display bridge |
| 3 | `kernel` | `kernel/0003-display-deferred-probe-devres.patch` | `rdk/x5-kernel` | display deferred probe devres |
| 4 | `kernel` | `kernel/0004-rdk-direct-scanout.patch` | `rdk/x5-kernel` | rdk direct scanout |
| 5 | `kernel` | `kernel/0005-display-object-list-lifetime.patch` | `rdk/x5-kernel` | display object list lifetime |
| 6 | `kernel` | `kernel/0006-accesstoken-ioctl-noise.patch` | `rdk/x5-kernel` | accesstoken ioctl noise |
| 7 | `kernel` | `kernel/0007-rtg-qos-proc.patch` | `rdk/x5-kernel` | rtg qos proc |
| 8 | `kernel` | `kernel/0008-trace-eval-null-guard.patch` | `rdk/x5-kernel` | trace eval null guard |
| 9 | `kernel` | `kernel/0009-qos-proc-unconditional.patch` | `rdk/x5-kernel` | qos proc unconditional |
| 10 | `kernel` | `kernel/0010-fixed-mac.patch` | `rdk/x5-kernel` | fixed mac |
| 11 | `kernel` | `kernel/0011-fix-ethernet-mac-buffer.patch` | `rdk/x5-kernel` | fix ethernet mac buffer |
| 12 | `kernel` | `kernel/0012-rtg-ioctl-compat.patch` | `rdk/x5-kernel` | rtg ioctl compat |
| 13 | `kernel` | `kernel/0013-wdt-disable-on-suspend.patch` | `rdk/x5-kernel` | wdt disable on suspend |
| 14 | `kernel` | `kernel/0014-wdt-force-disable.patch` | `rdk/x5-kernel` | wdt force disable |
| 15 | `kernel` | `kernel/0015-vs-drm-runtime-pm-balance.patch` | `rdk/x5-kernel` | vs drm runtime pm balance |
| 16 | `kernel` | `kernel/0016-aic8800-cmd-recovery.patch` | `rdk/x5-kernel` | aic8800 cmd recovery |
| 17 | `kernel` | `kernel/0017-aic8800-sdio-power-toggle.patch` | `rdk/x5-kernel` | aic8800 sdio power toggle |
| 18 | `kernel` | `kernel/0018-tcan-spi-max-speed.patch` | `rdk/x5-kernel` | tcan spi max speed |
| 19 | `kernel` | `kernel/hdf-core/0001-arm64-kernel-build.patch` | `oh/openharmony/drivers/hdf_core` | arm64 kernel build |
| 20 | `optional` | `optional/preempt-rt/patch-6.1.83-rt28.patch` | `rdk/x5-kernel` | patch 6.1.83 rt28 |
| 21 | `screenlock` | `screenlock/0001-unlock-without-account.patch` | `oh/openharmony-full/applications/standard/screenlock` | 未激活账号时仍执行解锁动画 |
| 22 | `screenlock` | `screenlock/0002-default-unlocked.patch` | `oh/openharmony-full/base/theme/screenlock_mgr` | 无锁屏记录时默认 unlocked |
| 23 | `launcher` | `launcher/0001-create-window-before-rdb.patch` | `oh/openharmony-full/applications/standard/launcher` | 先创建窗口再初始化 RDB，避免 Launcher 启动卡死 |
| 24 | `launcher` | `launcher/0002-rdk-desktop-experiment.patch` | `oh/openharmony-full/applications/standard/launcher` | RDK 桌面/布局实验集合 |
| 25 | `launcher` | `launcher/0003-style-config-fallback.patch` | `oh/openharmony-full/applications/standard/launcher` | desktop style config 为空时回退默认配置 |
| 26 | `settings` | `settings/0001-storage-statvfs.patch` | `oh/openharmony-full/applications/standard/settings` | Settings 存储统计改用 statvfs |
| 27 | `settings` | `settings/0002-storage-uri.patch` | `oh/openharmony-full/applications/standard/settings` | Settings 存储 URI 修正 |
| 28 | `settings` | `settings/0003-nearlink-settings-page.patch` | `oh/openharmony-full/applications/standard/settings` | Settings 增加星闪页面并修复 @Link JsCrash |
| 29 | `calendardata` | `calendardata/0001-calendar-month-page.patch` | `oh/openharmony-full/applications/standard/calendardata` | calendar month page |
| 30 | `call` | `call/0001-strict-null.patch` | `oh/openharmony-full/applications/standard/call` | CallUI strict-null、TS/ArkTS 导入和 exported 修复 |
| 31 | `contacts-data` | `contacts-data/0001-allow-unverified-account.patch` | `oh/openharmony-full/applications/standard/contacts_data` | Contacts DataAbility 允许未验证账号 |
| 32 | `contacts` | `contacts/0001-bringup-permission-gate.patch` | `oh/openharmony-full/applications/standard/contacts` | Contacts 首帧权限门禁放开 |
| 33 | `filemanager` | `filemanager/0001-fileaccess-extension-exported.patch` | `oh/openharmony-full/foundation/filemanagement/user_file_service` | FileExtensionAbility 增加 exported，尝试修复 picker 发现 |
| 34 | `photos` | `photos/0001-photos-resources.patch` | `oh/openharmony-full/applications/standard/photos` | 补 Photos 资源文件，保证图库页面可加载 |
| 35 | `photos` | `photos/0002-defer-media-library.patch` | `oh/openharmony-full/applications/standard/photos` | 把媒体库初始化延迟到 UI 之后，消除 lifecycle freeze |
| 36 | `media-library` | `media-library/0001-skip-user-unlock-check.patch` | `oh/openharmony-full/foundation/multimedia/media_library` | 未验证 account 100 时不再让 MediaLibraryData 自杀 |
| 37 | `media-library` | `media-library/0002-datashare-config.patch` | `oh/openharmony-full/foundation/multimedia/media_library` | MediaLibraryData DataShare metadata + data_share_config |
| 38 | `display` | `display/0001-x5-software-drm.patch` | `oh/openharmony-full/drivers/peripheral` | x5 software drm |
| 39 | `display` | `display/0002-composer-c-entrypoints.patch` | `oh/openharmony-full/drivers/peripheral` | composer c entrypoints |
| 40 | `display` | `display/0003-crtc-mask-selection.patch` | `oh/openharmony-full/drivers/peripheral` | crtc mask selection |
| 41 | `display` | `display/0004-drm-power-and-present.patch` | `oh/openharmony-full/drivers/peripheral` | drm power and present |
| 42 | `display` | `display/0005-primary-plane-zpos.patch` | `oh/openharmony-full/drivers/peripheral` | primary plane zpos |
| 43 | `display` | `display/0006-primary-plane-format.patch` | `oh/openharmony-full/drivers/peripheral` | primary plane format |
| 44 | `display` | `display/0007-composer-release-entrypoint.patch` | `oh/openharmony-full/drivers/peripheral` | composer release entrypoint |
| 45 | `display` | `display/0008-display-buffer-metadata-noop.patch` | `oh/openharmony-full/drivers/peripheral` | display buffer metadata noop |
| 46 | `input` | `input/0001-evdev-touch-capabilities.patch` | `oh/openharmony-full/drivers/peripheral` | evdev touch capabilities |
| 47 | `audio` | `audio/0001-x5-alsa-integration.patch` | `oh/openharmony-full/drivers/peripheral` | x5 alsa integration |
| 48 | `audio` | `audio/0002-optional-sink-aux.patch` | `oh/openharmony-full/foundation/multimedia/audio_framework` | optional sink aux |
| 49 | `audio` | `audio/0003-default-effect-channel.patch` | `oh/openharmony-full/foundation/multimedia/audio_framework` | default effect channel |
| 50 | `audio` | `audio/0004-optional-running-lock.patch` | `oh/openharmony-full/foundation/multimedia/audio_framework` | optional running lock |
| 51 | `audio` | `audio/0005-running-lock-optional.patch` | `oh/openharmony-full/foundation/multimedia/audio_framework` | running lock optional |
| 52 | `media-foundation` | `media-foundation/0001-avbuffer-default-memory-type.patch` | `oh/openharmony-full/foundation/multimedia/media_foundation` | avbuffer default memory type |
| 53 | `account` | `account/0001-empty-index-object.patch` | `oh/openharmony-full/base/account/os_account` | empty index object |
| 54 | `build-host` | `build-host/0001-select-host-gcc.patch` | `oh/openharmony-full/build` | select host gcc |
| 55 | `build-host` | `build-host/0002-hvigor-nodejs18.patch` | `oh/openharmony-full/build` | hvigor nodejs18 |
| 56 | `build-host` | `build-host/0003-compile-app-hvigor26.patch` | `oh/openharmony-full/build` | compile app hvigor26 |
| 57 | `ets-frontend` | `ets-frontend/0001-node14-rimraf.patch` | `oh/openharmony-full/arkcompiler/ets_frontend` | node14 rimraf |
| 58 | `ace-ets2bundle` | `ace-ets2bundle/0001-host-gcc.patch` | `oh/openharmony-full/developtools/ace_ets2bundle` | host gcc |
| 59 | `ability-runtime` | `ability-runtime/0001-dialog-want-import.patch` | `oh/openharmony-full/foundation/ability/ability_runtime` | dialog want import |
| 60 | `ace-engine` | `ace-engine/0001-pixelmap-ani-dependency.patch` | `oh/openharmony-full/foundation/arkui/ace_engine` | pixelmap ani dependency |
| 61 | `graphic3d` | `graphic3d/0001-host-shader-toolchain.patch` | `oh/openharmony-full/foundation/graphic/graphic_3d` | host shader toolchain |
| 62 | `graphic2d` | `graphic2d/0001-software-render-build.patch` | `oh/openharmony-full/foundation/graphic/graphic_2d` | software render build |
| 63 | `graphic2d` | `graphic2d/0002-render-service-image-manager-guards.patch` | `oh/openharmony-full/foundation/graphic/graphic_2d` | render service image manager guards |
| 64 | `graphic2d` | `graphic2d/0003-app-server-drawable-split.patch` | `oh/openharmony-full/foundation/graphic/graphic_2d` | app server drawable split |
| 65 | `graphic2d` | `graphic2d/0004-client-drawable-guards.patch` | `oh/openharmony-full/foundation/graphic/graphic_2d` | client drawable guards |
| 66 | `window-manager` | `window-manager/0001-input-window-display-id.patch` | `oh/openharmony-full/foundation/window/window_manager` | input window display id |
| 67 | `window-manager` | `window-manager/0002-input-display-binding-test.patch` | `oh/openharmony-full/foundation/window/window_manager` | input display binding test |
| 68 | `bundlemanager` | `bundlemanager/0001-optional-bms-extension.patch` | `oh/openharmony-full/foundation/bundlemanager/bundle_framework` | optional bms extension |
| 69 | `resourceschedule` | `resourceschedule/0001-pin-auth-secon.patch` | `oh/openharmony-full/foundation/resourceschedule/resource_schedule_service` | pin auth secon |
| 70 | `resourceschedule` | `resourceschedule/0002-bundle-active-optional.patch` | `oh/openharmony-full/foundation/resourceschedule/device_usage_statistics` | bundle active optional |
| 71 | `resourceschedule` | `resourceschedule/0003-pin-auth-hdf-args.patch` | `oh/openharmony-full/foundation/resourceschedule/resource_schedule_service` | pin auth hdf args |
| 72 | `dsoftbus` | `dsoftbus/0001-optional-client-plugin.patch` | `oh/openharmony-full/foundation/communication/dsoftbus` | optional client plugin |
| 73 | `device-manager` | `device-manager/0002-optional-resident-log.patch` | `oh/openharmony-full/foundation/distributedhardware/device_manager` | optional resident log |
| 74 | `device-profile` | `device-profile/0001-optional-sync-adapter.patch` | `oh/openharmony-full/foundation/deviceprofile/device_info_manager` | optional sync adapter |
| 75 | `security-component` | `security-component/0001-optional-enhance-log.patch` | `oh/openharmony-full/base/security/security_component_manager` | optional enhance log |
| 76 | `security-component` | `security-component/0002-device-auth-syscap.patch` | `oh/openharmony-full/base/security/device_auth` | device auth syscap |
| 77 | `tee` | `tee/0001-teecd-device-ownership.patch` | `oh/openharmony-full/base/tee/tee_client` | teecd device ownership |
| 78 | `security-component` | `security-component/0003-deviceauth-sandbox.patch` | `oh/openharmony-full/base/security/device_auth` | deviceauth sandbox |
| 79 | `ark-runtime` | `ark-runtime/0001-node14-rimraf.patch` | `oh/openharmony-full/arkcompiler/runtime_core` | node14 rimraf |
| 80 | `device-manager` | `device-manager/0001-respect-headless-product.patch` | `oh/openharmony-full/foundation/distributedhardware/device_manager` | respect headless product |
| 81 | `libnl` | `libnl/0001-use-installed-host-tools.patch` | `oh/openharmony-full/third_party/libnl` | use installed host tools |
| 82 | `haps` | `haps/applications_auth_widget-null-guards.patch` | `oh/openharmony-full/applications/standard/applications_auth_widget` | applications_auth_widget null guards |
| 83 | `haps` | `haps/call-build-config.patch` | `oh/openharmony-full/applications/standard/call` | call build config |
| 84 | `haps` | `haps/theme-build-config.patch` | `oh/openharmony-full/applications/standard/theme` | theme build config |
| 85 | `haps` | `haps/printspooler-build-config.patch` | `oh/openharmony-full/applications/standard/printspooler` | printspooler build config |
| 86 | `haps` | `haps/admin_provisioning-build-config.patch` | `oh/openharmony-full/applications/standard/admin_provisioning` | admin_provisioning build config |
| 87 | `haps` | `haps/camera-build-config.patch` | `oh/openharmony-full/applications/standard/camera` | camera build config |
| 88 | `camera` | `camera/0001-lazy-save-asset.patch` | `oh/openharmony-full/applications/standard/camera` | camera 启动时懒初始化 SaveCameraAsset，避免 DataShare 阻塞首帧 |
| 89 | `camera` | `camera/0002-vdi-basic-stream-config.patch` | `oh/openharmony-full/drivers/peripheral` | USB V4L2 VDI 输出有效 UVC basic stream config |
| 90 | `camera` | `camera/0003-init-race.patch` | `oh/openharmony-full/applications/standard/camera` | 首次 init 未完成时等待，不发布零 camera count |
| 91 | `camera` | `camera/0004-bringup-permission-gate.patch` | `oh/openharmony-full/applications/standard/camera` | bring-up 权限门禁放开，避免相机权限对话框阻塞 |
| 92 | `camera` | `camera/0005-open-without-await.patch` | `oh/openharmony-full/applications/standard/camera` | camera input open 不再阻塞 JS 初始化 |
| 93 | `camera` | `camera/0006-session-commit-timeout.patch` | `oh/openharmony-full/applications/standard/camera` | session commit 加超时兜底，继续 start preview |
| 94 | `haps` | `haps/systemui-build-config.patch` | `oh/openharmony-full/applications/standard/systemui` | systemui build config |
| 95 | `haps` | `haps/systemui-resource-manager.patch` | `oh/openharmony-full/applications/standard/systemui` | systemui resource manager |
| 96 | `haps` | `haps/notes-resources.patch` | `oh/openharmony-full/applications/standard/notes` | notes resources |
| 97 | `haps` | `haps/notes-db-init.patch` | `oh/openharmony-full/applications/standard/notes` | notes db init |
| 98 | `haps` | `haps/contacts-arkts-worker-migration.patch` | `oh/openharmony-full/applications/standard/contacts` | contacts arkts worker migration |
| 99 | `haps` | `haps/mms-arkts-worker-migration.patch` | `oh/openharmony-full/applications/standard/mms` | mms arkts worker migration |
| 100 | `nnrt` | `nnrt/0001-x5-nnrt-hdi-service.patch` | `oh/openharmony-full/drivers/peripheral` | x5 nnrt hdi service |
| 101 | `nearlink-bsp` | `nearlink-bsp/0001-x5-linux-6.1.patch` | `rdk/ws73-bsp-94a02d3a` | x5 linux 6.1 |
| 102 | `nearlink-bsp` | `nearlink-bsp/0002-firmware-para-len.patch` | `rdk/ws73-bsp-94a02d3a` | firmware para len |
| 103 | `nearlink-ssap` | `nearlink-ssap/0001-ohos-clang-compatibility.patch` | `oh/nearlink-ssap` | ohos clang compatibility |
| 104 | `launcher` | `launcher/0004-bringup-desktop-fallbacks.patch` | `oh/openharmony-full/applications/standard/launcher` | 补齐 launcher 工作树的 fallback/旋转/MainAbility 改动 |
| 105 | `screenlock` | `screenlock/0003-auto-unlock-fallbacks.patch` | `oh/openharmony-full/applications/standard/screenlock` | 捕获 lockScreen 禁用、slidescreenlock 自动解锁和 float 资源 |
| 106 | `settings` | `settings/0004-module-config.patch` | `oh/openharmony-full/applications/standard/settings` | 移除 Settings 的 home skill |

## 最近板端验证的重点 patch

| Patch | 板端证据 |
| --- | --- |
| `camera/0001..0006` | Camera 可启动到真实预览；当前控制栏/快门布局仍未完成。HAP `b4895d43...`，截图 `out/board-logs/camera-20261119/camera-session.jpeg` |
| `photos/0001..0002` | Photos 空图库页面正常，不再 lifecycle freeze；截图 `photos-fuse2.jpeg` |
| `media-library/0001..0002` | MediaLibraryData provider 可启动并完成 `OnConnect`；DataShare 不再自杀 |
| `screenlock/0001..0002`、`launcher/0003`、`settings/0003` | 解锁、Launcher、Settings 已做过板端验证（此前记录） |
| `launcher/0004`、`screenlock/0003`、`settings/0004` | 2026-11-19 从当前工作树捕获的补充 patch；已在干净 worktree 验证可应用 |

## 不在 patch 清单内的运行态修复

- `/dev/fuse` 从 `660 root:root` 改为 `666`。
- 创建 `/mnt/data/100/media_fuse`、`/storage/media/100`、`/storage/cloud/100/files` 等目录。
- 这些已写入 `overlay/vendor/drobotics/rdk_x5/{ueventd.config,init.rdk_x5.cfg}` 作为镜像准备；板端运行态与源码/镜像仍分开记录。

