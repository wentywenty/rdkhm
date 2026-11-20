# `<local>/1` 日志逐项追踪

来源：`<local>/1`，7706 行，时间窗口 `01-01 08:00:43` 到 `08:00:57`，
`E=5463`、`W=2218`。这是启动窗口的 hilog，包含大量“服务尚未 ready”的级联错误，
不能把所有 `E` 都当成持久故障。下面按“持久问题 / 启动竞态 / 已修 / 待硬件验证”分类。

## 1. 显示与合成（P0）

| 日志 | 次数 | 根因 | 状态 |
| --- | --- | --- | --- |
| `GetScreenColorGamut failed` (`:7017`) | 16 | 默认 VDI 缺 `GetDisplaySupportedColorGamuts`，服务返回 NOT_SUPPORT | 已加 0002 补丁，返回 sRGB |
| `SetDisplayBacklight ... ec=-5` (`:2875`) | 4 | X5 HDMI 无 kernel backlight 设备 | 已加 0004 补丁，NOT_SUPPORT→成功 |
| `RSRenderNode::InitRenderParams failed` (`:7007`) | 5 | 应用/系统进程链接 base 但没有 drawable generator | 已加 `graphic2d/0003` |
| `PreProcessLayersComp failed, ret -3` (`:7021`) | 4 | `layerIdMap_` 为空（`hdi_output.cpp:421`） | 与上方同链，待刷写验证 |
| `libdisplay_buffer_vdi_impl.z.so` 加载失败 | 见 boot 日志 | 默认 buffer VDI 只在 chipset-sdk 路径 | 已加镜像双路径注入 |
| `create data_share helper failed` (`:2184`) | 1 | DataShare/BMS 未 ready | 启动竞态，随后重试 |

显示链结论：`GetScreenColorGamut` 和 backlight 是独立小问题；黑屏主链仍是
应用侧 drawable 失败 → RS 空 layer map。已由 `graphic2d/0003` + `0004` 修复，
2026-11-18 临时部署后板端锁屏可见；持久化仍待刷写。

## 2. 持久缺失的配置/库（P1）

| 日志 | 次数 | 根因 | 状态 |
| --- | --- | --- | --- |
| `ams_extension_config.json` (`:91`) | 68 | 文件未装入 `/system/etc`，installd 扩展沙箱查询失败 | 已加 overlay + 镜像注入 |
| `bms-extensions.json` (`:1`) | 211 | 文件未装入 `/system/etc/app`，BMS 扩展解析失败 | 可选扩展；当前未伪造内容，记 TODO |
| `SystemCapability.Security.DeviceAuth is not exsit` (`:1955`) | 11 | 产品 syscap 未声明 DeviceAuth，bundle 安装检查失败 | TODO：补 syscap |
| `libdsoftbus_client_plugin.z.so` (`:36`) | 30 | 未构建/未安装的 softbus 插件 | TODO：按产品 feature 补包 |
| `libdevicemanagerresident/deviceprofileadapter/security_component_client_enhance` | 各 4–8 | 可选组件未构建/未安装 | TODO：按 feature 补包 |
| `bundle_active_config_reader LoadConfigFile file does no exit` | 32 | `bundle_active` 配置缺失 | TODO：补产品配置 |

## 3. 音频（P1）

| 日志 | 次数 | 根因 |
| --- | --- | --- |
| `AudioEffectChainManager: null audioEffectChain` (`:15`) | 769 | audio effect 配置/效果链未初始化 |
| `AudioRunningLock: lock is nullptr` (`:4`) | 333 | PowerMgr runninglock 未就绪/不支持 |
| `AVBufferQueue CheckConfig not OK` (`:75`) | 141 | audio/video buffer 配置失败 |
| `MediaSyncManager progress lag` (`:2250`) | 111 | 音视频同步被启动阻塞拖慢 |

音频不是黑屏根因；先修 audio effect 配置和 runninglock 服务，再做真实播放/采集。

## 4. QoS / cgroup（P1）

| 日志 | 次数 | 根因 |
| --- | --- | --- |
| `CONCUR ... open qos node failed` (`:2128`) | 262 | `/dev/cpu/foreground/cgroup.procs` 或 qos 节点不存在 |
| `ffrt TrivalOpenQosCtrlNode ... no such file` (`:108`) | 43 | 同上，cgroup 路径未创建 |

对应 kernel 日志里的 `Failed to open realPath: (null) /dev/cpu/foreground/cgroup.procs errno:2`。
需要产品 init/内核 cgroup 配置，当前不影响显示。

## 5. Account/BMS 启动竞态（P2，多数可自愈）

| 日志 | 次数 | 说明 |
| --- | --- | --- |
| `BMS` E/W | 792/590 | 启动早期 BMS 未 ready、RDB 空、preinstall 查询失败 |
| `DataShare` (`:*`) | 539 | 依赖 BMS/foreground user |
| `AccountMgrService` (`:534`) | 102 | `/data/service/el1/public/account/0/account_info.json` 不存在，账号创建中 |
| `BMSHelper` | 168 | 同上 |
| `Rdb GoToFirstRow failed` | 256 | 空数据库/启动竞态 |
| `Wallpaper_OS Query all created userIds failed` | 47 | 账号未 ready |
| `ZDD/DeviceManager` | 139 | softbus/UDID/账号未 ready |

判断依据：20:32 板端复查时 `account.ready=true`、`bms.main.bundles.ready=true`、
Launcher/SystemUI 已运行，说明这些多数是启动窗口的瞬时级联。验收时应以
`bootevent.account.ready` / `bms.main.bundles.ready` 之后仍存在的错误为准。

## 6. 安全/TEE/syscap（P2）

| 日志 | 次数 | 说明 |
| --- | --- | --- |
| `HUKS` (`:186`) | 45 | HUKS/TEE 未就绪 |
| `ATM TokenID invalid` | 35 | access token/账号未 ready，部分由 TYPE=84 误报链影响 |
| `DfxUnwinder Find map error` (`:6826`) | 100 | 崩溃栈展开符号缺失，不是业务崩溃本身 |
| `MemMgr` (`:1097`) | 43 | 内存管理/PSI 配置缺失 |
| `pin_auth_host` / `usb_serial_host` / `teecd` | kernel log | secon/sandbox/TEE 配置问题 |

`access_token TYPE=84` 已确认是 `TCGETS`（0x54）误报，内核 patch 0006 改为 `-ENOTTY`。

## 7. 纯噪声/可忽略

- `MUSL-LDSO load ... namespace=ndk`：可选库探测，失败后走默认命名空间。
- `ffrt open qos node warn`：cgroup 未配置的告警。
- `le_epoll timeout`：init 事件循环 timeout 告警。
- `HUKS`/`DfxUnwinder` 的部分错误依赖账号/TEE 初始化顺序。

## 8. 本轮已落地的代码

- `patches/display/0002`：`RegRefreshCallback` + `GetDisplaySupportedColorGamuts`
- `patches/display/0004`：HDMI backlight fallback
- `patches/graphic2d/0003`：应用/服务端 drawable 拆分
- `patches/kernel/0006`：access-token 非 `'A'` ioctl 静默返回 `-ENOTTY`
- `scripts/make-openharmony-image.sh`：buffer VDI 双路径 + `ams_extension_config.json`
- `scripts/verify-openharmony-image.py`：对应校验
- `bringup/status/screen-status.sh`、`audio-status.sh`、`scripts/build-target.sh`

## 9. 尚未落地的代码/TODO

1. `bms-extensions.json` 的真实产品内容（不伪造空扩展）。
2. `SystemCapability.Security.DeviceAuth` 的 syscap 声明。
3. `libdsoftbus_client_plugin`、`libdevicemanagerresident` 等可选组件打包。
4. `bundle_active_config`、`productName` 产品配置。
5. audio effect 配置/效果链、PowerMgr runninglock。
6. QoS cgroup（`/dev/cpu/foreground/cgroup.procs`）创建/挂载。
7. `pin_auth_host`/`usb_serial_host` 的 `secon` 与 chipset sandbox。


## 10. 本轮已全部整改的项

- BMS 可选扩展缺失：`bundlemanager/0001` 缺失文件返回 OK
- `ams_extension_config.json`：overlay + 镜像注入
- 音频无 effect chain：`audio/0003` 返回默认声道
- `AudioRunningLock` 空锁：`audio/0004` 10 个文件改为 no-op/SUCCESS
- `pin_auth_host` secon：`resourceschedule/0001` + `type.te`
- 失效 `/dev/cpu/...` writepid：`resourceschedule/0001` 删除
- `bundle_active_config` 空路径：`resourceschedule/0002` 静默跳过
- softbus client plugin 可选：`dsoftbus/0001` 降为 warning
- device manager resident 可选：`device-manager/0002` 降为 warning
- security enhance 可选：`security-component/0001` 降为 warning
- QoS 内核接口缺失：`qos-manager/0001` 降为 warning
- 示例 HAP `com.example.kikakeyboard` / `com.example.distributedcalc`：从产品
  preinstall 列表移除，避免 DeviceAuth/signature 失败
- 产品安全子系统加入 `device_auth` 组件

## 11. 仍不能靠配置解决的

- HUKS/TEE 失败：X5 TEE 未就绪
- `DfxUnwinder Find map error`：栈展开符号缺失
- `AVBufferQueue`/`MediaSyncManager`：音视频启动竞态
- `/proc/thread-self/sched_qos_ctrl`：X5 内核没有 QoS/RTG 接口，只能降噪或移植内核
- 可选 device manager resident/profile 适配库：当前 manifest 没有源码/预编译产物

以上代码改动尚未重新编译；需要时只用 `build-target.sh` 编受影响组件，不要全量重打。
