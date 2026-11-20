# Camera / Photos / MediaLibrary 修复记录（2026-11-19）

本页记录 2026-11-19 在 `10.43.9.213:5555` 上的多媒体修复。结论按
“源码 / 本地构建 / 板端热部署 / 镜像”分开记录；当前没有重新构建或刷写镜像。

## 板端基线

- IP / HDC：`10.43.9.213:5555`
- boot_id：`00836ef8-c49c-4a6e-8c58-a0bf1da68998`
- 内核：`6.1.83-rdkhm #5 SMP PREEMPT`
- 显示：800x480 HDMI；触摸 `QDtech MPI5001`
- HAP：
  - Camera：`b4895d43766d6f9b9590564009e9dea3e4aecfead6371ed270630110eaf506f5`
  - Photos：`d222a4cddd2119ac052272b83be8b9ede610c5534e8eecee87c9d48c0bef461b`
  - MediaLibraryData：`dc2c9c32a17ac692ba18a836fa19ecad864ac5b09139c4e1fe25ae882a29760d`

## 根因

### 1. MediaLibraryData 在启动时自杀

`MediaLibraryData` 最初在 `MediaDataShareCreator` 后立即
`KillApplicationSelf`。日志：

```text
Current active account is 100
Current user verification result: 0
CheckUnlockScene Killing self caused by booting before unlocking
```

`account_info.json` 也是 `isVerified:false`、`isActived:false`。因此 provider
不是 HAP 配置问题，而是原生 `IsStartBeforeUserUnlock()` 的用户校验把
未验证 account 100 当成“启动早于解锁”。

修复：

- `patches/media-library/0001-skip-user-unlock-check.patch`
  - bring-up 镜像跳过该用户校验；保留 media path 检查。
- `patches/media-library/0002-datashare-config.patch`
  - 补 `ohos.extension.dataShare` metadata 和
    `resources/base/profile/media_data_share_config.json`。
- 重新构建 `libmedialibrary_data_extension.z.so` 与
  `Media_Library_Ext.hap`；provider 使用 HAP 内 `libs/arm64-v8a` 的库，
  不是 `/system/lib64` 的同名库。

### 2. media path / FUSE 缺失

provider 之后停在：

```text
CheckUnlockScene Killing self caused by media path unmounted
```

实际 `ROOT_MEDIA_DIR` 是 `/storage/cloud/files/`，且 media fuse 还需要：

- `/mnt/data/100/media_fuse` 存在
- `/dev/fuse` 可被 provider uid 打开
- `/storage/media/100`、`/storage/cloud/100/files` 等目录存在

板端修复：

```sh
mkdir -p /mnt/data/100/media_fuse
chmod 0711 /mnt/data/100 /mnt/data/100/media_fuse
mkdir -p /storage/cloud/100/files/Photo \
         /storage/cloud/100/files/.thumbs/Photo \
         /storage/media/100/local/files/Photo \
         /storage/media/100/local/files/.thumbs
chmod 666 /dev/fuse
```

已把 `/dev/fuse 0666 root root` 和目录创建写入产品 overlay 的
`ueventd.config` / `init.rdk_x5.cfg`，供下一次镜像使用；板端仍以热部署为准。

修复后：

```text
StorageDaemon: mount media fuse success, path is /mnt/data/100/media_fuse
MediaFuseManager: Mount fuse successfully
MediaFuseDaemon: Starting fuse ...
DataShare: on connect done
```

`MediaFuseDaemon` 不再报 `failed to open /dev/fuse: Permission denied`。

### 3. Photos 首帧 freeze

`MainAbility` 在 UI 之前同步触发 `UserFileManagerAccess`，DataShare 连接在
provider 未起来时阻塞，最终 `LIFECYCLE_TIMEOUT`。

修复：

- `patches/photos/0002-defer-media-library.patch`：媒体库初始化延迟到 UI 之后。
- `patches/photos/0001-photos-resources.patch`：补齐图库页面资源。
- 结果：Photos 空图库页面可正常显示，provider 可启动；截图
  `out/board-logs/camera-20261119/photos-fuse2.jpeg`。
- `getAllObject` 返回空是因为当前没有媒体文件，不再等同于启动卡死。

### 4. Camera 初始化链

Camera 的修复是分层的，最终才到真实预览：

1. `camera/0001`：`SaveCameraAsset` 懒初始化，避免首帧 DataShare 阻塞。
2. `camera/0002`：USB V4L2 VDI 输出有效的 UVC basic stream config
   （`Basic Stream Info Size` 从 0 到 26）。
3. `camera/0003`：首次 init 未完成时等待，不发布零 camera count。
4. `camera/0004`：bring-up 权限门禁放开，避免权限请求回调不返回。
5. `camera/0005`：`mCameraInput.open()` 的 JS Promise 不返回时不再阻塞初始化。
6. `camera/0006`：`commitConfig()` 加 1s 超时；`start()` 改为不阻塞，
   继续 UI preview。

板端日志已经出现完整链路：

```text
createCameraInput end
deviceType = default
initCamera end
XComponent_onLoad
startPreview begin
createSession beginConfig/addInput/addOutput/commitConfig
```

截图：`out/board-logs/camera-20261119/camera-session.jpeg`，800x480
画面中可见真实摄像头图像，640x480 居中，上下黑边。

## 仍未完成

- Camera 预览已出现，但相机控制栏/快门按钮在截图中不可见；可能是
  `footBarHeight`/布局问题，尚未修复。
- Camera 预览画面需要再做取景、点击快门、拍照、保存到 Photos 的完整验证。
- Photos 只有空图库；需要拍照或导入媒体后再验证缩略图、相册和 DataShare 查询。
- 镜像尚未重新构建；以上 HAP、native 库和 overlay 都只在源码/板端热部署层。

## 证据

- `out/board-logs/camera-20261119/photos-fuse2.jpeg`：Photos 空图库。
- `out/board-logs/camera-20261119/camera-session.jpeg`：Camera 真实预览。
- `out/board-logs/camera-20261119/camera-perm.jpeg`：权限门禁修复前黑屏。
- `out/board-logs/camera-20261119/camera-open.jpeg`：session commit 卡住阶段。

## 镜像前注意

- Camera/Photos HAP 必须由源码构建并注入 system.img；默认镜像的
  prebuilt `Camera.hap` / `Photos.hap` 不包含本轮 patch。
- MediaLibraryData HAP/native 库由 OpenHarmony images 构建；仍需确认
  system.img 中 HAP 的 SHA256 与源码构建一致。
- `/dev/fuse` 和 `/mnt/data/100` 等运行态修复已写入 overlay，但还没有经过
  镜像冷启动验证。
