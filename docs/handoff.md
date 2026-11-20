# RDKHM 工作交接

## 工程定位

`rdkhm` 是 RDK X5 Linux BSP 上的 OpenHarmony 集成工程，不是 OpenHarmony 上游源码的替代品，也不是已经量产的发行版。工程负责补丁、产品 overlay、构建编排、驱动模块/固件清单、镜像组装、离线校验和板测证据。

## 最新验证（2026-11-19）

- USB HDC：TCP 正常；`rdkhm-usb.sh` 修复 configfs 重复 mount。
  20:54 统一构建镜像冷启动后 gadget/FunctionFS/UDC 和 hdcd endpoint 已自动就绪；
  主机侧枚举待接 USB 的 PC 确认。
- CAN-FD：TCAN4550 的 18 MHz SPI 超规格；`kernel/0018` clamp 到 10 MHz。
  统一构建镜像 kernel #6 冷启动后经典 CAN + CAN-FD loopback 通过；外部总线待验证。
- 统一构建：本地镜像 `db0a75bb...`；板端 boot_id
  `9ade3a96-6eb4-4876-a3dc-f407990d6b5e`，kernel `6.1.83-rdkhm #6`。
- HAP：`admin_provisioning`、`theme` 已构建/签名并加入 `patches/haps/`；
  Settings 构建到 `out/settings/Settings.hap`。
- GPIO/PinTool：20:54 镜像冷启动 `gpio-daemon` 运行，Unix socket 和
  TCP `127.0.0.1:9800` 监听；`gpio list/show 7` 正常。`PinTool.hap` 文件存在，
  但 BMS 未注册该 bundle，UI 当前不可启动。源码已加 GPIO 加固（0660/TCP opt-in/
  peer creds/SELinux/Pintool capability），尚未进入该镜像。详见 [gpio.md](gpio.md)。
- RT：`RDKHM_KERNEL_PROFILE=rt` 仍是 opt-in，未构建/板测。

详见 [board-validation-20261119.md](board-validation-20261119.md)。

### HAP / Contacts / 文件管理（2026-11-19）

- Settings 已加入星闪入口并通过源码 HAP 启动；修复了 `settingEndText` 的
  `@Link` JsCrash。
- CallUI 已修复 strict-null、TS/ETS 导入和 `exported`，可启动到通话界面。
- Contacts DataAbility 已允许未验证账号启动；Contacts 权限门已放开首帧渲染。
  拨号键盘和联系人空状态/新建联系人页面已板端验证。
- FilePicker 仍不可用：BMS 查不到 `ExternalFileManager` 的 `fileAccess` 扩展，
  需修 extension 索引或重新打镜像，不是继续改 FilePicker。
- TEE 仍不可用：X5 是 OP-TEE，OH `teecd` 仍按 HiSilicon `tc_ns_client` ABI。
- Patch 列表、板端日志和命令见
  [hap-fixes-20261119.md](hap-fixes-20261119.md)。

## 目录责任

| 目录 | 责任 |
| --- | --- |
| `config/` | 产品、依赖、模块和 workspace 配置 |
| `patches/` | OpenHarmony/Linux 的最小补丁集 |
| `overlay/` | X5 产品 init、HDF、权限、SELinux 和文件标签 |
| `bringup/` | 板端只读诊断与受控初始化脚本 |
| `scripts/` | 同步、准备、编译、打包、验证、采集和部署 |
| `docs/` | 架构、驱动、调试、交接和验收记录 |
| `sources/` | 外部源码输入，可重建，不作为集成提交边界（可指向大磁盘） |
| `out/` | 编译物、镜像、运行证据和板端日志（可指向大磁盘） |
| `thirdparty/` | 本机大文件：工具链、预编译缓存、下载包；不入库 |

## 构建入口

```sh
cd <workspace>
./rdkhm doctor
./rdkhm check
./rdkhm plan all
./rdkhm run build

# 统一分批入口
./build kernel
./build oh
./build hap settings
./build image
```

补丁统一由 `config/patches.json` + `scripts/apply-patches.py` 管理；工具链和路径由 `env.sh` 导出（`RDKHM_HDC`、`RDKHM_OH_TREE`、`RDKHM_COMMAND_LINE_TOOLS` 等）。

已有源码时使用 `run build`；需要同步源码时使用 `run all`。只组装已有产物可使用 `run package`。不要并发运行旧脚本和 wrapper。

按组件分批处理（定义在 `config/build/components.json`）：

```sh
./rdkhm components
./rdkhm build display
./rdkhm package display
./rdkhm deploy display <ip:port>          # 默认 dry-run
./rdkhm deploy display <ip:port> --apply  # 需要串口保底
```

`deploy` 不会刷盘；未验证热部署路径的组件（kernel/input/settings/accelerators/image）会拒绝 `--apply`。

完整手工链路：

```sh
bash scripts/prepare-kernel.sh
bash scripts/prepare-openharmony.sh
JOBS=64 bash scripts/build-kernel.sh Image
JOBS=64 bash scripts/build-kernel.sh dtbs
JOBS=64 bash scripts/build-kernel.sh modules
bash scripts/build-bringup-userspace.sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/import-driver-firmware.py
python3 scripts/prepare-driver-bundle.py
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

镜像：`out/images/rdkhm-x5-openharmony-dev.img`。构建不会刷写磁盘，也不会自动连接板子。

## 当前基线

最新组装镜像：`out/images/rdkhm-x5-openharmony-dev.img`，
SHA256 `4368578ffed5043c1ac74be22556f61b1bf99a52c435e18928b6905b955a6727`，
运行证据 `out/runs/20261118T053124Z-0nkn4n3v`。该镜像包含
`DisplayComposerImplRelease`、render-service guards、drawable 客户端/服务端拆分、
buffer metadata 兼容、五个可选库 stub、tracefs/PSI/RTG/QoS、hardware-status 修复、
`screen-status.sh` 和 bootanimation 配置，但尚未刷写。

## 当前已知问题

1. `DisplayComposerImplRelease` 已导出并打包；`RegRefreshCallback` 已在 0002 中实现。
   `graphic2d/0003` + `0004` 已拆分应用/服务端 drawable 生成；2026-11-18 临时部署后
   800x480 锁屏可见，首帧已有一份板端证据。
2. `libgraphic_innovation.z.so` 缺失；并行合成关闭，当前不作为显示主链修复。
3. 背光 HDI 已加 HDMI fallback；板端 `backlight=255`，仍需在最终镜像冷启动复测。
4. HDMI connector/EDID 正常，锁屏已可见；桌面/HAP 交互和长时间刷新仍需验证。
5. 摄像头已在热部署 HAP 上验证到 USB camera 真实预览；camera/photos HAP
   已准备进入镜像注入，但控制栏/快门和拍照保存未完成。X5 VPU capability 和
   真实编解码仍未完成。详见
   [camera-media-photos-20261119.md](camera-media-photos-20261119.md)。
6. WS73 固件在镜像中，但模块未默认加载；实机加载曾导致网络/HDC 中断。
7. SELinux 仍 permissive，AVC 尚未收敛。
8. HDC 冷启动自启动需单独验证；现场报告可能在 hdcd 启动前采样为 not-listening。
9. 诊断脚本必须兼容目标 BusyBox；`hardware-status.sh` 已改用 `expr` 并随最新镜像打包，仍需板端复测。
10. GPU：`eglCreateContext` 的 `0x3005` 根因是私有 runtime 缺少被 `dlopen` 的
    `libGLSLC.so`。staging/lock 已加入，离屏 pbuffer 和 GBM window 在板端已通过
    （GC8000L / ES 3.1），当前已刷镜像仍未包含，需要重建镜像后再做冷启动验收。
    硬件合成路线见 `docs/hardware-composition.md`；`display/0009` 已实现
    composer 侧 COMPOSE 接入，但 2026-11-20 板端在 dma-buf 导入处 panic，
    `kernel/0021` 已加 sg_table 防护，daemon 的 COMPOSE 默认关闭；需要
    新内核/镜像验证后再打开。
11. HAP：镜像注入统一由 `config/build/haps.json` 的 `image` 段驱动
    （`scripts/image_haps.py`），已接入全部有明确上游目录的构建产物，
    包括 contacts/mms/call/filepicker、Settings/SystemUI/ScreenLock/Notes/
    PinTool。签名按“官方 key 或 bundle allowlist”判定。
    统一编译前需确认 scope（见 `hap-tasks.md` T12 和
    `image-build-prep-20261119.md`）。

## GPIO / PinTool（2026-11-19）

- 40pin 映射、`/rdkhm/gpio`、`gpio-daemon` 和 PinTool HAP 已接入源码；
  `./rdkhm check` 通过。
- HAP 已在 `10.43.9.213` 通过 hdc 安装，Pin 7 的 High/Low/Read 已验证；
  daemon 为手动启动。
- 镜像未构建/刷写；init 自启动、预装和冷启动行为未验证。
- 细节见 `docs/gpio.md`。

## 下一位工程师的第一小时

1. 阅读 `STATUS.md`、本文、`docs/debug-history.md` 和 `docs/backlog.md`。
2. 检查 `git status`，不要清理已有未提交改动。
3. 跑 `./rdkhm check`，确认脚本和配置完整。
4. 通过 HDC 采集当前板卡完整日志，记录 boot id 和镜像特征文件。
5. 检查目标板是否包含 `/rdkhm/boot-diagnostics.sh` 和 `/data/rdkhm-logs/boot-status.txt`。
6. 刷写最新镜像后复测 Composer 首帧、刷新回调和 GPU context；先确认
   `/vendor/lib64/rdkhm-accelerator/libGLSLC.so` 存在。release 符号已离线验证。
7. 每次刷写记录镜像 SHA256、刷写时间、板卡 IP、boot id 和日志目录。

## 验收定义

| 层级 | 通过条件 |
| --- | --- |
| 构建 | wrapper、OpenHarmony images、镜像组装和 verifier 全部通过 |
| 启动 | 冷启动无关键服务重启，boot id 改变，HDC 可用 |
| 显示 | HDMI 有 EDID、DRM enabled、首帧可见、Launcher 可交互 |
| 输入 | event 节点存在，实际触摸坐标进入 MMI 并驱动 HAP |
| GPU/NPU | RenderService 硬件路径和真实 NNRT 模型推理各有运行证据 |
| 多媒体 | 摄像头有真实帧，硬件编码/解码有输入输出和错误处理证据 |
| 安全 | enforcing 启用，新增 AVC 收敛，服务 domain 和设备标签正确 |
| 稳定性 | 多次冷启动、HDC 长连接、显示热插拔和至少一轮应用运行通过 |

## 证据规则

源码审查、离线编译、镜像校验、板端节点枚举、真实数据流和用户体验必须分别记录。任何结论都要带日期、目标板、镜像 SHA256 或 boot id、命令和日志路径。
