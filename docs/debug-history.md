# RDKHM 调试记录

本文记录 RDK X5 Linux 6.1.83 内核移植 OpenHarmony 6.0 标准系统的主要调试过程、证据和踩坑。记录中的“已验证”只表示对应证据成立，不自动表示整机功能完成。

## 目标与边界

- 内核继续使用 D-Robotics X5 Linux BSP，不替换为 OpenHarmony 内核。
- 用户空间采用 OpenHarmony ARM64 standard-system，目标是 HDMI 桌面、USB 触摸、HDC 和 ArkUI/HAP。
- GPU、BPU/NPU、摄像头、视频编解码、WS73 星闪先接入设备节点、库和 HDI 边界，再做真实硬件验证。
- 参考 BSP：`$RDKHM_BSP/roboparty_build`。
- 集成工程：`<workspace>`。

## 时间线

### 初始工程化

建立 `rdkhm` 集成工程，使用脚本管理 OpenHarmony 源码、X5 内核、补丁、驱动模块、固件、镜像组装和验证。`sources/`、`out/` 是可重新生成的输入和产物目录，不能作为源代码提交边界。

### 内核与系统启动

保留 Linux 6.1.83，接入 Binder/Ashmem/AccessToken/HDF 等 OpenHarmony 所需能力，制作 CONFIG、system、vendor、userdata 分区。镜像构建和分区校验通过，但这些检查不等价于 X5 冷启动通过。

### HDMI 与 Composer

早期问题依次包括：HDMI 未启用、CRTC 选择错误、无效 zpos、YUV-only primary plane、DRM 电源/首次 atomic 提交失败。对应补丁为：

- `0001-x5-software-drm.patch`
- `0002-composer-c-entrypoints.patch`
- `0003-crtc-mask-selection.patch`
- `0004-drm-power-and-present.patch`
- `0005-primary-plane-zpos.patch`
- `0006-primary-plane-format.patch`
- `0007-composer-release-entrypoint.patch`

真实板卡后来出现 HDMI `connected/enabled`、EDID 256 字节，但黑屏仍然存在。该板测镜像早于 `0007`，因此日志中的 release 缺失不代表当前源码状态；`0007` 已在 2026-11-17 晚的增量构建中进入镜像并由 verifier 检查导出符号。关键日志是：

```text
DisplayComposerImplRelease missing
RegRefreshCallback pointer is null
gpuContext is nullptr
PreProcessLayersComp failed, ret=-3
SetDisplayBacklight failed, ec=-5
libgraphic_innovation.z.so missing
```

结论：物理 HDMI 链路已建立，黑屏位于 Composer/VDI/RenderService 和 GPU backend 之间。不能只看 connector 状态判定“有画面”。

### 触摸

MPI5001 USB 触摸屏 `0484:5750` 被 Linux hid-multitouch 枚举为 `event1`，OpenHarmony MMI 服务运行。已经证明设备枚举和能力位存在，尚未证明触摸事件能到达 Launcher/HAP。

### HDC 与登录

板端 HDC 使用 TCP `5555`，不是 ADB 协议。使用 `adb connect` 会出现 `offline`，这不能证明 HDC 离线。正确客户端是 OpenHarmony prebuilts 中的 `hdc`。

现场地址随 DHCP 变化，历史地址不写入文档；每次使用前重新确认板卡 IP，且不要写死到产品配置。

### GPU/BPU/NPU

镜像有 `/dev/galcore`、`/dev/bpu`、DRM `card0/renderD128`，并包含隔离 glibc worker 和离线库加载检查。当前 RenderService 仍是软件渲染；NNRT 没有真实模型推理证据。库能加载、节点存在、版本可读都不等价于硬件渲染或 NPU 推理。

### 摄像头、编解码和 WS73

Camera host、camera service、codec service 和 HDF 配置存在，但现场没有 `/dev/video*`，也没有 X5 VPU capability 表。WS73 USB 设备和固件存在，模块可编译并打包，但未完成加载、Wi-Fi/BLE/SLE 连接和真实流量验证。此前手动加载实验曾导致网络/HDC 中断，因此模块默认保持 manual-only。

### SELinux 与服务

开发镜像使用 `selinux=1 enforcing=0`。策略和设备标签已打包，现场仍有 AVC，不能宣称 enforcing 完成。`access_token_id` 的 ioctl magic fail 是 ABI 问题，不应仅用 SELinux allow 规则掩盖。

## 反复踩坑

1. `adb` 和 `hdc` 协议不同；端口相同不代表客户端相同。
2. `start hdcd` 是 init 配置动作，不是 shell 可执行命令。板端应使用 `service_control start hdcd`。
3. `/sys/class/drm` 的 connector 状态不证明有可见 framebuffer。
4. 编译成功、`.so` 存在、符号检查通过，不证明 HDF VDI 在目标板能提交首帧。
5. 设备节点枚举不证明 HAP 能收到事件，也不证明摄像头能出帧。
6. BusyBox shell 不一定支持宿主 shell 的算术扩展；诊断脚本必须按目标 BusyBox 能力编写。
7. WS73 加载会改变网络和 HDC，必须串口保底并按单模块、可回滚方式测试。
8. 镜像文件的生成时间不能证明板子已刷入该镜像；必须用板端特征文件、启动报告和 boot id 关联。

## 当前结论

工程已经具备可构建、可组装、可验证、可通过 HDC 收集日志的骨架。2026-11-18
在旧镜像上临时部署显示库后，800x480 锁屏已经可见，`OnGenerate`/`InitRenderParams`
失败消失，`ScreenLockWindow`/`FrameBufferSurface` 均有 buffer。最新镜像 SHA256 为
`4368578ffed5043c1ac74be22556f61b1bf99a52c435e18928b6905b955a6727`，尚未刷写。

## 2026-11-18 追加记录：HDMI、suspend、锁屏和 HAP 构建

本节只记录有日志或命令证据的结果，不把临时手工点亮当成镜像修复。

### 板端状态

- 板卡 IP：`<board-ip>`
- 串口桥：`socket://127.0.0.1:22299`，`115200`
- 串口链路多次出现断连；HDC 也多次只剩 stale target
- 最新本地组装镜像：`out/images/rdkhm-x5-openharmony-dev.img`
  - SHA256：`878a7909d316678682f5ea22a3d18b6327a3953ce703763ea310245d850072d4`
  - 这是源码组装产物，不等于板端已刷入
- 2026-11-18 最后一份串口日志：`<workspace>/1`

### 已确认：HDMI 冷启动触发 suspend 复位

带 HDMI 冷启动时，日志稳定出现：

```text
PM: suspend entry (deep)
Suspending console(s)
Welcome to Horizon X5 ASIC BOOTROM
```

没有 `Kernel panic`、`Oops` 或 watchdog timeout。最后一份日志在
`[166.256] PM: suspend entry (deep)` 后断掉。因此需要区分：

- 接 HDMI 冷启动：可能进入 suspend 并复位
- 不接 HDMI：可以长时间稳定
- 保持串口/终端活动：可以暂时避免进入 suspend
- 运行时执行 `service_control stop powermgr` 后：uptime 从 242s 增长到
  332s、428s，未再复位

结论：`powermgr` 的 suspend 路径是复位触发器；不能把 watchdog_service
单独当作根因。当前镜像没有把 `stop powermgr` 固化。

### 已确认：显示链路可以手工点亮，但不是持久修复

HDMI 连接器初始状态为 `connected`，但：

```text
enabled = disabled
EDID = 0 bytes
modes = 空
```

手工执行：

```text
写入 800x480 合成 EDID 到 debugfs edid_override
echo on > /sys/kernel/debug/dri/0/HDMI-A-1/force
service_control stop/start composer_host
```

后得到：

```text
status = connected
enabled = enabled
modes = 800x480
```

屏幕可以亮，但这不是持久修复：EDID override、force 和 composer 重启都没有
固化到启动流程。冷启动仍可能是 EDID 0/白屏。

### 已确认：白屏是 UI 窗口缺失，不是 HDMI 没输出

手工点亮后出现白屏，`hidumper -s WindowManagerService -a -a` 只看到：

```text
ScreenLockWindow
SystemUi_VolumePanel
```

没有 launcher 窗口。旧预编译 launcher HAP 的启动日志停在：

```text
LauncherMainAbility --> onCreate start
RdbStoreManager --> initRdbConfig start
```

之后没有 `createWindow`。因此：

- 旧 HAP 中 `await getRdbStore()` 阻塞了后续 `createWindow()`
- 已加入源码补丁 `patches/launcher/0001-create-window-before-rdb.patch`
- 该补丁要求先创建桌面窗口，再初始化 RDB
- 尚未生成包含该补丁的 HAP

`aa start -b com.ohos.launcher -a com.ohos.launcher.MainAbility` 返回：

```text
error: failed to start ability.
Error Code: 10106102
The device screen is locked during the application launch
Cause: current mode is developer mode, and the screen cannot be unlocked automatically
```

### 已确认：触摸链路本身是通的

`QDtech MPI5001` 枚举为 `/dev/input/event1`，MMI 进程打开 `event1`，原始
evdev 有 down/move/up。`InputKeyFlow` 显示事件被送往 systemui 的
`ScreenLockWindow`，而不是 launcher。

锁屏滑动的日志显示：

```text
ScreenLock-SlideScreenLockViewModel --> Touch Event ...
slidingLength: 150
ScreenLock-ScreenLockService --> unlockScreen
```

但锁屏没有消失。`acm dump -a` 显示：

```text
ID: 100
Status: active
isForeground: 1
```

`acm switch -i 100` 返回成功，但 AMS 仍报 screen locked。因此账号不是第一
阻塞点；剩余问题是 ScreenLockWindow/AMS 锁屏状态和旧 launcher 没有窗口。

已设置的临时状态：

```text
/data/service/el1/public/screenlock/screenlock_state.xml
key="100" value="true"
```

systemui 重启后窗口树仍然为空，`aa start` 仍被锁屏拒绝。该状态没有解决
desktop 入口。

### 已确认：当前镜像不包含 launcher/screenlock 源码修改

镜像构建直接拷贝预编译 HAP：

```text
applications/standard/hap/Launcher.hap
applications/standard/hap/SystemUI-ScreenLock.hap
```

HAP 时间戳为 2025-08-27。`build-openharmony.sh --build-target images`
不重新编译这两个系统应用，因此：

- `patches/launcher/0001-create-window-before-rdb.patch`
- `patches/screenlock/0001-unlock-without-account.patch`

只在源码树中，不在镜像 HAP 中。继续重打 image 不会自动生效。

### HAP 构建环境结论

尝试过：

- 下载 API10 public SDK 到 `thirdparty/toolchains/ohos-sdk-api10/10`
- 拉取 OpenHarmony 4.0 `sdk-js` 系统 API 覆盖 public SDK
- 安装 `ruby`、`genext2fs`
- 使用本地 hvigor 4.0.9 和已有 API20 SDK 编译

结果：

- HAP `CompileArkTS` 仍报 `FormComponent`、`RemoteWindow`、
  `FormDimension` 等系统组件缺失
- 从当前 6.0 源码构建 `ohos-sdk` full SDK 失败于 host musl/glibc：
  `regparm` 非法、`MUSL_SIGNAL_*` 未声明
- 没有产出新的 `Launcher.hap` / `SystemUI-ScreenLock.hap`

结论：public SDK 加手工 d.ts 覆盖不能替代 matching full SDK；当前 host
也不能直接构建 full SDK。要真正修桌面入口，需要 DevEco Studio full SDK
或受支持的 OpenHarmony 4.0/full SDK 构建环境。

### 当前未完成项

1. 固化 `powermgr` 的临时停用，或修复 suspend 复位（2026-11-19 已在 overlay
   `rdkhm-powermgr-off` 中准备自动 stop，未冷启动验证）
2. 生成并刷入包含 launcher/screenlock 修改的 HAP
3. 清除/绕过 `ScreenLockWindow` 的 AMS 锁屏状态
4. 固化 HDMI EDID/force/composer 初始化
5. 验证 launcher 窗口出现后再测触摸点击、滑动和息屏唤醒

以上项目前都没有板端通过证据，不能标记为已解决。

### 日历 HAP 现场修复（2026-11-19）

现象：`aa start -a MainAbility -b com.ohos.calendardata` 返回成功，ability
处于 `FOREGROUND`，窗口 `calendardata0 [0 0 800 480]` 存在，但截图纯白、
`dumpLayout` 只有 bundleName。不是启动失败，而是页面没有内容。

根因：上游 `applications/standard/calendardata/entry/src/main/ets/pages/index.ets`
的 `build()` 为空（低代码页面本应由 `.visual` 生成，但该 checkout 没有
`.visual` 文件），而工程内预置的 `CalendarData.hap` 也来自同一空页面。

修改：`patches/calendardata/0001-calendar-month-page.patch` 把 `index.ets`
改为自包含月历页（标题、‹ › 翻月、星期表头、当月网格、今天高亮），只用本地
`Date` 计算，不访问日历数据库。已接入 `scripts/prepare-openharmony.sh`。

本机构建记录（仅编译 calendardata，不改产品镜像）：

```sh
cd sources/oh/openharmony-full/applications/standard/calendardata
# 复用 Launcher 的 hvigor 6.0.2 配置，并让 modelVersion 与 oh-package 一致
cp <workspace>/sources/oh/openharmony-full/applications/standard/launcher/hvigor/hvigor-config.json5 hvigor/
sed -i 's/"modelVersion": "5.0.0"/"modelVersion": "6.0.2"/' oh-package.json5
OHOS_BASE_SDK_HOME=<workspace>/sources/oh/openharmony-full/prebuilts/ohos-sdk/linux \
  <workspace>/thirdparty/toolchains/command-line-tools-26/command-line-tools/ohpm/bin/ohpm install --all
OHOS_BASE_SDK_HOME=<workspace>/sources/oh/openharmony-full/prebuilts/ohos-sdk/linux \
  <workspace>/thirdparty/toolchains/command-line-tools-26/command-line-tools/bin/hvigorw \
  --mode module -p product=default -p module=entry@default assembleHap --no-daemon
# 产物 entry/build/default/outputs/default/entry-default-signed.hap（工程自带 signature/）
```

说明：`hvigorw`/`hvigor-config`/`modelVersion` 只是本机构建脚手架，不进入
产品 patch；重同步 `sources/` 后需要重新准备。calendardata 用
command-line-tools-26 + API20 SDK 可以编译，但这不改变“Launcher/SystemUI
仍需要 matching full SDK”的旧结论。

板端验证（`<board-ip>:5555`，boot_id `49dd3d69-3264-446e-80f7-aa67193d9af9`）：

- `hdc install -r entry-default-signed.hap` → `install bundle successfully`
- 截图/布局：`out/board-logs/20261119-calendar/screen-month.jpeg`、
  `layout-month.json`
- 内容：`2026年11月`，1–30 全渲染，19 号蓝色高亮
- 交互：点击 `›` 后布局为 `2026年12月`（`layout-next-month.json`），点击
  `‹` 回到 `2026年11月`

注意：这次是 `/data` 覆盖安装，未刷写系统分区，也未重新打镜像。镜像
`4368578ffed5043c1ac74be22556f61b1bf99a52c435e18928b6905b955a6727`
不包含该修改。

只应用 patch 也不足以改变镜像：`applications/standard/calendardata` 没有
`BUILD.gn`，镜像消费的是预置 HAP（`applications/standard/hap/BUILD.gn:252`
的 `CalendarData.hap`）。要随镜像生效，需要先用
`applications/standard/hap/build.sh --project=<...>/calendardata` 重新生成
签名 HAP，再替换预置 HAP，或在 `make-openharmony-image.sh` 里注入生成的
HAP。具体走“替换预置二进制”还是“components/ 工作副本 + 注入”需要再确认。
