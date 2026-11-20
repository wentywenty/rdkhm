# 镜像构建准备（2026-11-19）

2026-11-19 已按批准 scope 执行 **system_image + vendor_image + 仅 system/vendor
分区组装**；没有执行完整 `images`、没有生成整盘镜像、没有刷写。构建结果见本页
末尾“本轮分区构建结果”。

## 本轮准备范围

- 默认内核 profile：非 RT，沿用 `hobot_x5_rdk_ubuntu_defconfig`。
  RT 仍为 opt-in，不在本次默认镜像 scope。
- OpenHarmony：应用 `config/patches.json` 中当前 103 个显式 patch；
  `nearlink-bsp` / `nearlink-ssap` 的 3 个 glob patch 按既有同步流程处理。
- HAP：`settings`、`camera`、`photos`、`launcher`、`systemui`、
  `screenlock`、`notes`、`pintool` 由源码构建并准备注入。
- 电源：overlay 新增 `rdkhm-powermgr-off` boot 服务，启动后停止 `powermgr`，
  防止 suspend/HDC 丢失；与板端手动 `service_control stop powermgr` 对齐。
- 镜像：system/vendor/userdata 组装到
  `out/images/rdkhm-x5-openharmony-dev.img`，最后跑 verifier。

## 本轮新增的构建准备改动

### 1. HAP 构建流水线

`config/build/pipeline.json` 的 `haps` stage 增加：

```text
scripts/build-hap.py camera
scripts/build-hap.py photos
```

这样 `./rdkhm run build` 会生成 `out/haps/camera.hap` 和
`out/haps/photos.hap`，而不是继续使用不含本轮 patch 的 prebuilt HAP。

### 2. 镜像 HAP 注入

`scripts/make-openharmony-image.sh` 增加：

- `out/haps/camera.hap` → `/system/app/com.ohos.camera/Camera.hap`
- `out/haps/photos.hap` → `/system/app/com.ohos.photos/Photos.hap`

这两个路径对应 `applications/standard/hap/BUILD.gn` 中的 prebuilt 安装路径；
脚本会先删除旧 HAP，再注入新 HAP 并做字节比较。

`scripts/verify-openharmony-image.py` 同步增加这两个 HAP 的映射，镜像 verifier
会检查 system.img 中实际内容。

### 3. powermgr 休眠服务

`overlay/vendor/drobotics/rdk_x5/init.rdk_x5.cfg` 增加：

```text
rdkhm-powermgr-off: boot, once, sleep 10; service_control stop powermgr
```

原因：`powermgr` 的 suspend 路径会在 HDMI/HDC 场景触发复位；板端已有证据表明
`service_control stop powermgr` 可以避免。这里选择在 bootevent 建立后再 stop，
而不是把服务从配置中删除，以免影响 bootevent/依赖服务。镜像冷启动效果未验证。

### 4. media fuse 运行态前置条件

已写入产品 overlay，供下一次镜像使用：

- `overlay/vendor/drobotics/rdk_x5/ueventd.config`
  - `/dev/fuse 0666 root root`
- `overlay/vendor/drobotics/rdk_x5/init.rdk_x5.cfg`
  - `/mnt/data/100/media_fuse`
  - `/storage/media/100/local/files/Photo`
  - `/storage/cloud/100/files/Photo`
  - `/storage/cloud/100/files/.thumbs/Photo`
  - `/dev/fuse` chmod

这是单用户 dev image 的显式路径；正式产品应改成由 user mount/account 流程
生成，而不是写死 user 100。

### 5. 文档

- 全部 patch：`docs/patch-inventory-20261119.md`
- 多媒体修复：`docs/camera-media-photos-20261119.md`
- 本页：构建准备

## 当前产物

已在 `out/` 存在（构建输入，不代表已经进镜像）：

| 产物 | 备注 |
| --- | --- |
| `out/haps/camera.hap` | 最近构建，含 0004/0005/0006 |
| `out/haps/photos.hap` | 含 photos 0001/0002 |
| `out/haps/launcher.hap` | 含 launcher 0001..0004；已准备注入 |
| `out/rdk_x5/obj/foundation/multimedia/media_library/MediaLibraryExt/Media_Library_Ext.hap` | MediaLibraryData HAP |
| `sources/oh/openharmony-full/out/rdk_x5/multimedia/media_library/libmedialibrary_data_extension.z.so` | 原生库 |
| `out/kernel/obj/...` | 既有内核产物，本轮未重建 |
| `sources/oh/openharmony-full/out/rdk_x5/packages/phone/images/*.img` | 既有 userspace images，本轮未重建 |

## 构建前只读检查

建议在本页之后、真正构建之前执行：

```sh
./rdkhm doctor
./rdkhm check
./rdkhm plan all
bash -n scripts/make-openharmony-image.sh
python3 -m py_compile scripts/verify-openharmony-image.py
```

当前已确认：

- `./rdkhm check`：14 tests OK，patch format 0 failure。
- 103 个显式 patch，`patches/` 下 106 个 `.patch` 文件（含 3 个 glob）。
- `out/haps/camera.hap`、`out/haps/photos.hap`、`out/haps/launcher.hap` 均已存在。

## Patch 修复与预检结果（2026-11-19）

此前发现的 patch 可复现问题已修复：

1. **`launcher/0002-rdk-desktop-experiment.patch` 的 EntryView import hunk 已修正**，
   现在可在干净 HEAD 上应用。
2. 新增三个补充 patch，捕获此前 working-tree 的剩余源码：
   - `launcher/0004-bringup-desktop-fallbacks.patch`
   - `screenlock/0003-auto-unlock-fallbacks.patch`
   - `settings/0004-module-config.patch`
3. 已在干净 worktree 上验证：
   - launcher：0001 → 0002 → 0003 → 0004 全部通过；
   - screenlock：0001 + 0003 通过；native 0002 在 `screenlock_mgr` 通过；
   - settings：0001 → 0002 → 0003 → 0004 全部通过。
4. **Launcher HAP 已加入构建/镜像注入范围**：
   - `config/build/pipeline.json` 的 haps 阶段包含 launcher；
   - `scripts/make-openharmony-image.sh` 注入
     `/system/app/com.ohos.launcher/Launcher.hap`；
   - `scripts/verify-openharmony-image.py` 增加对应校验；
   - `scripts/integration.py` 增加注入 marker。
5. 生成型文件 `oh-package.json5`、`hvigor/*`、`local.properties`、
   `BuildProfile.ets` 仍不写入 patch；它们由 HAP 构建脚本生成。

当前 `./rdkhm check` 结果：**103 listed / 106 files present、0 format
failure、14 tests OK**。`apply-patches.py --record` 已把当前 kernel/openharmony
源码树记录为已应用；仍未启动构建。

## 真正的构建入口（尚未执行）

大编译 scope（等待明确批准）：

- target：`./rdkhm run build`（默认非 RT；不 fetch）
- 包含：prepare、kernel、userspace、drivers、haps、image、verify
- 影像：`out/images/rdkhm-x5-openharmony-dev.img`
- 预计：约 1–3 小时（取决于 kernel/userspace 增量；当前未实测本轮耗时）
- 不包含：刷盘、重启板卡、更新 QSPI/U-Boot

源码已存在、只重建当前 tree：

```sh
./rdkhm run build
```

需要重新 fetch/sync 时：

```sh
./rdkhm run all
```

只组装已有产物：

```sh
./rdkhm run package
```

手工链路见 `STATUS.md` / `docs/handoff.md`。不要同时启动 wrapper 和旧脚本。

## 构建后必须记录

- 构建时间、命令、run 目录。
- `out/images/rdkhm-x5-openharmony-dev.img` 和 `.img.sha256`。
- system.img 中 camera/photos/media library HAP 的 SHA256。
- 冷启动后的 boot_id、内核版本、板端实际镜像 SHA256。
- Camera 预览、Photos 打开、拍照/保存的实测结果。
- `/dev/fuse` 权限、`/mnt/data/100/media_fuse` 挂载和 MediaLibrary provider 连接。

## 还未完成的验收

- Camera 控制栏/快门布局未完成；当前只验证到预览。
- Photos 仍是空图库，未验证拍照保存后的缩略图和相册。
- overlay 的 `/dev/fuse`、目录创建还没有经过镜像冷启动。
- 本轮没有构建、没有刷写、没有改变已刷镜像。

## 本轮分区构建结果（2026-11-19）

- `system_image`：成功，8m16s
- `vendor_image`：成功，1m51s
- `make-openharmony-image.sh --partitions-only --only system,vendor`：成功
- 产物：
  - `out/fastboot/system.img` SHA256 `c783c4221a7f0a48aa4dab61d97e8cba6fc21526ce79312d08c4a29d841c6e76`
  - `out/fastboot/vendor.img` SHA256 `e09940d8a1669f71ea8504892e791f18a378237c2495aba4632692e3c6150998`
  - `out/fastboot/system.simg`、`vendor.simg`
- 日志：`out/logs/build-system-vendor-20261119/`、`SHA256SUMS`
- 已验证：
  - system 内 Camera/Photos/Launcher HAP 与 host 一致
  - system 内 MediaLibraryData `Media_Library_Ext.hap` 与源码构建一致
  - vendor `/etc/init.rdk_x5.cfg` 包含 `rdkhm-powermgr-off`
  - vendor `/etc/ueventd.config` 包含 `/dev/fuse 0666`
- 未验证/未改变：
  - 未生成新的完整 `out/images/...img`
  - 未刷写 system/vendor
  - `powermgr` 自动停止、camera/photos 在冷启动后的行为尚未板测

## 后续更新（2026-11-20）

- `config/build/pipeline.json` 的 `haps` stage 已扩展到
  `config/build/haps.json` 的 `image.apps` 全部 17 个 app，加上 SystemUI
  modules 和 PinTool；不再依赖旧的 `out/haps` 残留产物。
- 2026-11-19 20:54 已生成整盘镜像
  `db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78`
  并通过 verifier；未刷写。
