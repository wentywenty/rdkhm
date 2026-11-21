# RDK X5 / OpenHarmony 全系统测试计划

记录日期：2026-11-20。  
范围：系统启动、显示输入、网络、总线、多媒体、AI、应用和 HMDFS/账号激活。

## 1. 测试原则

1. **先只读，再功能，最后冷启动/刷写。**
2. 设备节点存在、服务进程存在、驱动加载成功，都只算“枚举通过”，不算功能通过。
3. 离线 verifier 通过不等于板端通过。
4. 每次板测必须记录镜像 SHA、boot_id、内核版本、日志路径。
5. 刷写、重启、模块加载、网络切换、改分区必须有明确确认。
6. 当前板端已刷镜像和本轮源码/测试镜像必须分开记录。

### 状态标记

| 标记 | 含义 |
|---|---|
| ✅ | 板端功能已验证 |
| ◐ | 部分验证；枚举或单个场景通过，完整功能未验证 |
| ✗ | 已知失败或阻塞 |
| ○ | 未验证 |
| — | 当前未集成/不支持 |

## 2. 当前基线

### 2.1 本轮测试镜像

| 项目 | 值 |
|---|---|
| 镜像 | `out/images/rdkhm-x5-openharmony-dev.img` |
| SHA256 | `7948f022b3073c8ec1688c57774dafd512c78572ae8432ec48f16ea8162329c8` |
| 内核 | 6.1.83-rdkhm |
| `/boot/Image` SHA256 | `6e6cb22c769db8d17fe8b7a02f04a3d50e6e8d09e1a60760d8d544a7da75e421` |
| HMDFS 参数 | `const.distributed_file_property.enabled=true` |
| 板端状态 | **未刷写，未冷启动验证** |

源码默认参数已恢复为 `false`。测试镜像里的 `true` 只用于 HMDFS 专项。

### 2.2 已刷板端

最近记录的板端：

```text
IP:      10.43.9.213:5555
boot_id: 9ade3a96-6eb4-4876-a3dc-f407990d6b5e
kernel:  6.1.83-rdkhm #6
```

该板端仍是旧镜像，不能用来证明本轮镜像的 HMDFS/账号修复。

### 2.3 当前总体状态

| 域 | 状态 | 说明 |
|---|---|---|
| 镜像构建 | ◐ | 模块/内核/镜像内容可确认；完整 verifier 曾因并发构建 artifact 不一致失败 |
| 冷启动 | ○ | 本轮镜像未刷 |
| 账号激活 | ✗/○ | 旧镜像被 hmdfs 阻塞；本轮镜像未板测 |
| HDMI 显示 | ◐ | 旧镜像可见锁屏；桌面、长时间显示、热插拔待验证 |
| 触摸 | ◐ | 设备和 evdev 链路通；displayId/-1、解锁和点击体验未完全验证 |
| HDC | ◐ | USB HDC 可用；冷启动自启动仍需验证 |
| Launcher/SystemUI | ◐ | 旧镜像有黑屏/未注册记录；本轮未验证 |
| 网络 | ◐ | 以太网/Wi-Fi/蓝牙/SLE/4G 都有未完成项 |
| CAN-FD | ◐ | 控制器和 loopback 通过；外部总线未验证 |
| GPIO | ◐ | 冷启动和 Pin 7 通过；PinTool BMS/UI 未通过 |
| 音频 | ◐ | 声卡/服务/策略存在；播放、录音、路由未完整验证 |
| 摄像头 | ◐ | USB camera 预览曾通过；拍照保存/Photos 未完成 |
| GPU/NPU/VPU | ◐/○ | 离屏 GPU 探针通过；OH 窗口、模型执行、硬编解码未验证 |
| 应用 | ◐ | Settings/CallUI/Contacts 部分通过；FilePicker/TEE 等阻塞 |

## 2.4 当前通过 / 未通过总表

> 下面是**已有证据**汇总，不等于本轮 `7948...` 镜像冷启动结论。
> 标“历史”的项目来自旧镜像、热部署或离线检查；本轮镜像未刷。

### 已通过（PASS）

| 项目 | 证据/范围 |
|---|---|
| `./rdkhm check` | 14 tests OK；108 个 patch 格式检查通过 |
| HMDFS 模块编译 | `hmdfs.ko`，6.1.83 vermagic |
| 镜像内 HMDFS 模块 | vendor 中存在，`modules.load` 第一项 |
| 镜像内 kernel 身份 | `/boot/Image` 与 host Image SHA 一致（离线） |
| CAN classic loopback | kernel #6 冷启动后通过 |
| CAN-FD loopback | kernel #6 冷启动后通过 |
| GPIO daemon 冷启动 | 20:54 镜像，gpio-daemon 运行 |
| GPIO Pin 7 操作 | export/set/dir/get/unexport 全部 rc=0 |
| HDMI 物理点亮 | 物理 HDMI 屏可见锁屏 |
| 触摸枚举 | QDtech MPI5001，event1 存在 |
| 触摸事件链 | MMI InputKeyFlow 有 down/move/up |
| USB HDC 数据链路 | 旧镜像可连接并执行命令 |
| Settings 星闪入口 | 源码 HAP 启动后可见 |
| CallUI 启动 | strict-null/TS/exported 修复后启动 |
| Contacts DataAbility | 查询有 start/end，无 LIFECYCLE_TIMEOUT |
| Contacts 页面 | 拨号键盘、空状态、新建联系人页面 |
| USB camera 预览 | 热部署 HAP 上真实预览 |
| SystemUI 状态栏 | 热更新后截图可见状态栏/导航栏 |
| Note 本地持久化 | 热部署验证输入/保存/重启保留 |
| GPU 离屏 | GC8000L / ES 3.1 离屏探针通过 |
| WS73 USB 枚举 | `ffff:3733` |
| WS73 固件下载 | 三个固件下载，HCC boot finish |
| SLE open/close | `/dev/hwsle` 打开/关闭成功 |
| 4G 模块枚举 | ttyUSB* / wwan0 创建 |

### 部分通过（PARTIAL）

| 项目 | 已通过 | 未通过/未完成 |
|---|---|---|
| 显示 | 锁屏可见 | 桌面交互、热插拔、长稳 |
| 触摸 | 原始事件到 MMI | 点击/滑动/解锁/唤醒，displayId=-1 |
| HDC | 旧镜像手工/可用 | 冷启动自动启动 |
| Launcher | 部分历史启动记录 | 20:54 镜像黑屏/未注册 |
| Settings | 星闪入口 | 页面进出稳定性、完整设置项 |
| Contacts | 页面/DataAbility | 拨号号码文本显示 |
| Camera | 预览 | 快门、拍照、保存、控制栏 |
| Photos | HAP/空图库 | 缩略图、相册、DataShare |
| Audio | 声卡/服务/策略存在 | 播放、录音、音量、jack、HDMI 音频 |
| Wi-Fi | 模块/固件/补丁 | `wlan0 up` 失败，扫描/关联/上网 |
| 蓝牙 | 固件/探针 | UART 映射、HCI attach、controller |
| SLE | open/close | 广播 complete、扫描、连接、HDI/HAP |
| 4G | 模块/节点 | SIM、注册、数据、RIL |
| GPIO/PinTool | GPIO 操作 | PinTool BMS 注册/UI |
| CAN | loopback | 外部总线、终端电阻、第二节点、长稳 |
| GPU | 离屏 | OH native window/GBM 合成 |
| SystemUI | 状态栏热更新 | 冷启动/锁屏/导航手势 |
| Note | 热部署持久化 | 本轮镜像冷启动 |
| 镜像 | 内容检查 | 完整 verifier（当前 7948 镜像） |

### 失败 / 阻塞（FAIL / BLOCKED）

| 项目 | 结果 | 原因/证据 |
|---|---|---|
| 旧镜像账号激活 | FAIL | hmdfs 缺失，StartUser timeout |
| 旧镜像 BMS 用户 | FAIL | 当前用户 -2 |
| HMDFS 板端加载 | BLOCKED | 旧内核 unknown symbol；新镜像未刷 |
| Launcher（20:54 镜像） | FAIL/BLOCKED | 黑屏，BMS 未注册 Launcher/Note |
| FilePicker | FAIL/BLOCKED | BMS 无 ExternalFileManager fileAccess 扩展 |
| TEE | FAIL | teecd 255，缺 tc_ns_client/passthrough |
| PIN/密码 | BLOCKED | 依赖 TEE；未完成 |
| Wi-Fi 打开 | FAIL | rwnx timeout / cmd queue crashed |
| PinTool BMS | FAIL/BLOCKED | bundle 未注册 |
| 当前 7948 镜像 verifier | FAIL | `/system/lib64/libaccountmgr.z.so` 不一致 |
| 本轮镜像冷启动 | UNVERIFIED | 镜像未刷 |

### 未验证（UNVERIFIED）

- 本轮 `7948...` 镜像冷启动、account.ready、user 100、Launcher
- HMDFS 实际 mount
- 以太网 link/DHCP/数据
- 蓝牙 controller/HCI
- 4G SIM/注册/数据
- USB 串口 DDK 应用读写
- SPI/I2C/UART/PWM
- 音频播放/录音/路由/jack
- CSI 摄像头
- 硬件编解码/VPU
- NPU/NNRT 模型执行
- HDMI 热插拔/长稳
- MMS/Calendar/Print/DLP/Screenshot/文件管理
- 连续冷启动、长稳、异常断电
- RT 内核

## 3. 测试分层

| 层 | 内容 | 风险 | 是否需要确认 |
|---|---|---|---|
| L0 离线 | build、镜像 SHA、分区、artifact、HAP 签名 | 低 | 否 |
| L1 只读板测 | 驱动枚举、节点、服务、日志、状态脚本 | 低 | 否 |
| L2 受控功能 | 打开设备、音频、摄像头、CAN、网络、模块 | 中 | 是 |
| L3 冷启动/刷写 | 刷 system/vendor、重启、切镜像 | 高 | 是 |
| L4 稳定性 | 多次重启、长稳、热插拔、反复打开关闭 | 高 | 是 |

## 4. 系统与启动测试

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| SYS-01 | 镜像完整性 | 比对 `.sha256`、分区表、e2fsck、verifier | 全部一致 | ◐ |
| SYS-02 | 镜像内内核 | 取 `/boot/Image` 与 host kernel 比 SHA | 一致 | ✅ 离线 |
| SYS-03 | 冷启动 | 刷写后冷启动 | 无 panic，服务启动 | ○ |
| SYS-04 | 账号激活 | `param get bootevent.account.ready` | `true` | ○ |
| SYS-05 | BMS 用户 | `bm dump -a`、账号日志 | user 100，不是 `-2` | ○ |
| SYS-06 | Launcher/SystemUI | 进程、窗口、截图 | 桌面可见可交互 | ○ |
| SYS-07 | HDC 冷启动 | 串口/网络检查 `hdcd`、5555 | 无需手工启动 | ○ |
| SYS-08 | 存储 | `/data` 挂载、读写、空间、account 目录 | 可读写，无满盘 | ○ |
| SYS-09 | SELinux | `enforce`、avc denied、关键服务域 | 预期模式；无阻断性 AVC | ○ |
| SYS-10 | 电源/息屏 | `power-shell`、30 秒息屏、唤醒 | 息屏和唤醒正常 | ○ |
| SYS-11 | 重启/断电恢复 | 多次重启、异常断电 | 可重复启动 | ○ |
| SYS-12 | TEE/PIN | `tee0`、`teecd`、`tc_ns_client`、pin_auth | TEE 服务可用 | ✗ 已知不匹配 |

### 建议采集

```bash
cat /proc/sys/kernel/random/boot_id
uname -a
param get bootevent.account.ready
param get const.distributed_file_property.enabled
bm dump -a
ps -A
dmesg
hilog -x
/rdkhm/boot-diagnostics.sh
/rdkhm/hardware-status.sh
/rdkhm/system-security-status.sh
```

## 5. 显示、输入与 HMI

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| HMI-01 | HDMI 连接 | `/rdkhm/hdmi-status.sh` | connector connected，EDID 正常 | ◐ |
| HMI-02 | 首帧/锁屏 | `screen-status.sh --capture` | 可见锁屏/桌面 | ◐ |
| HMI-03 | 触摸枚举 | `/rdkhm/touch-status.sh` | event 节点、QDtech/MPI5001 | ✅ 枚举 |
| HMI-04 | 触摸事件 | `getevent`/MMI/InputKeyFlow | down/move/up 到应用 | ◐ |
| HMI-05 | 触摸解锁 | 上滑/点击解锁 | 能解锁进入桌面 | ○ |
| HMI-06 | 息屏唤醒 | 息屏后触摸 | 能唤醒并响应 | ○ |
| HMI-07 | displayId 绑定 | MMI 日志 | 不再出现 physical(-1)/invalid displayId | ✗/○ |
| HMI-08 | USB 键鼠 | `input` 节点、焦点 | 键鼠可用 | ○ |
| HMI-09 | HDMI 热插拔 | 插拔 HDMI、切模式 | 不黑屏、不崩服务 | ○ |
| HMI-10 | 长时间显示 | 持续刷新/视频/桌面 | 无花屏、无 vblank 卡死 | ○ |
| HMI-11 | 截图/布局 | `snapshot_display`、`uitest dumpLayout` | 可采集真实 UI | ◐ |

注意：触摸有原始事件不等于触控体验通过，必须验证点击、滑动、解锁和唤醒。

## 6. 网络与无线

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| NET-01 | 以太网链路 | `ip link`、`ethtool`、`ip addr` | link up，DHCP 地址 | ○ |
| NET-02 | 以太网数据 | ping/HTTP/HDC over TCP | 可通信 | ○ |
| NET-03 | Wi-Fi 扫描 | `wlan0 up`、`iw dev wlan0 scan` | 扫描到 AP | ✗ 曾有 rwnx timeout |
| NET-04 | Wi-Fi 连接 | `wpa_supplicant`/设置页 | 关联、DHCP、上网 | ○ |
| NET-05 | Wi-Fi 恢复 | 超时后重新打开 | 不进入永久 CRASHED | ○ |
| NET-06 | 蓝牙固件 | `bluetooth-init.sh --probe` | 固件存在、UART 候选 | ◐ |
| NET-07 | 蓝牙 HCI | `--attach` + `bluetoothctl` | controller 出现 | ○ |
| NET-08 | 蓝牙数据 | 扫描/连接/传输 | 可用 | ○ |
| NET-09 | WS73 USB | `ws73-probe.sh` | `ffff:3733`、固件/配置 | ✅ 枚举 |
| NET-10 | SLE 打开 | `/dev/hwsle`、SLE_OPEN | open/close 成功 | ✅ |
| NET-11 | SLE 广播 | `sle-adv-probe` | 命令 complete，可被扫描 | ◐ 只有 PENDING |
| NET-12 | SLE HDI/HAP | 服务、API、第二设备 | 可发现/连接/收发 | ○ |
| NET-13 | 4G 模块 | `lsusb`、`/dev/ttyUSB*`、`wwan0` | 模块识别、节点创建 | ◐ SIM 未插 |
| NET-14 | 4G 注册/数据 | AT、RIL、ping | 注册成功、数据通 | ○ |
| NET-15 | MAC 地址 | `ip link` | 固定/正确 MAC | ◐ 源码已改，板端待验 |

## 7. 总线与扩展

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| BUS-01 | CAN 控制器 | `ip link set can0 up`、`cansend/candump` | 控制器可用 | ✅ |
| BUS-02 | CAN loopback | classic CAN | 收到一致帧 | ✅ |
| BUS-03 | CAN-FD loopback | FD 帧 | 收到一致 FD 帧 | ✅ |
| BUS-04 | 外部 CAN 总线 | 第二节点/收发器/终端电阻 | 真实总线收发 | ○ |
| BUS-05 | CAN 错误恢复 | bus-off、错误帧、长稳 | 自动恢复 | ○ |
| BUS-06 | GPIO 枚举 | `/rdkhm/gpio list`、`show` | 6 个 gpiochip、28 针 | ◐ |
| BUS-07 | GPIO 操作 | export/set/dir/get/unexport | 电平正确 | ✅ Pin 7 |
| BUS-08 | GPIO 权限 | SELinux、peer creds、Unix/TCP | 只有授权客户端可操作 | ○ |
| BUS-09 | PinTool | HAP 启动、BMS 注册 | UI 可控 GPIO | ✗ BMS 未注册 |
| BUS-10 | SPI | spidev、DT 设备 | 设备能 bind/读写 | ○ |
| BUS-11 | I2C | 总线扫描、设备读写 | 设备可用 | ○ |
| BUS-12 | UART | 串口收发 | 数据正确 | ○ |
| BUS-13 | PWM | sysfs/PWM 设备 | 输出可调 | ○ |
| BUS-14 | USB 串口 | CH341/CP210x/FTDI/PL2303 | 枚举、DDK 打开、收发 | ○ |
| BUS-15 | USB Host | U 盘/键鼠/摄像头 | 枚举和功能 | ○ |

GPIO 注意：`usable_as_gpio` 只表示当前没有驱动 claim；启用 I2C/SPI/UART/PWM 后 mux 会变化。

## 8. 音频

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| AUD-01 | 声卡枚举 | `/rdkhm/audio-status.sh` | duplexaudio/ES8326 存在 | ◐ |
| AUD-02 | 播放 | `aplay`/音频 HAP | 有真实声音 | ○ |
| AUD-03 | 录音 | `arecord`/录音 HAP | 有真实输入 | ○ |
| AUD-04 | 音量/静音 | HDI/ALSA controls | 左右声道、静音正确 | ○ |
| AUD-05 | 耳机插拔 | jack 检测、路由 | 自动切换 | ○ |
| AUD-06 | 采样率/格式 | 48 kHz stereo S16LE | 不报错、无杂音 | ○ |
| AUD-07 | 反复打开/关闭 | pause/stop/restart | 不崩溃、不泄漏 | ○ |
| AUD-08 | HDMI 音频 | HDMI 输出 | 声音从 HDMI 出 | ○ |

离线单测和 ASan/UBSan 通过不等于板端音频通过。

## 9. 摄像头、视频和 AI

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| MED-01 | USB 摄像头枚举 | `/rdkhm/camera-codec-status.sh` | `/dev/video*` 存在 | ◐ |
| MED-02 | 预览 | Camera HAP | 实时画面 | ◐ 曾通过 |
| MED-03 | 格式协商 | V4L2 | 分辨率/格式可用 | ○ |
| MED-04 | 拍照 | 快门 | 生成图片 | ○ |
| MED-05 | 保存/Photos | 拍照后图库 | 缩略图/相册可见 | ○ |
| MED-06 | 控制栏/布局 | 截图/layout | 按钮可见可点 | ○ |
| MED-07 | CSI 摄像头 | sensor/DT/HDI | 枚举并出流 | — 未集成 |
| MED-08 | 硬件编码 | codec HDI/OMX | 真实码流 | ○ |
| MED-09 | 硬件解码 | codec HDI/OMX | 真实播放 | ○ |
| MED-10 | VPU capability | capability HCS | 只声明真实能力 | — 未声明 |
| MED-11 | GPU 离屏 | `gpu-probe` | EGL/GLES 可用 | ✅ 历史 |
| MED-12 | GPU 窗口 | OH native window/GBM | 应用渲染 | ○ |
| MED-13 | BPU/NPU | `bpu` 节点、模型 | 模型推理成功 | ○ |
| MED-14 | NNRT | HDI/驱动服务 | 后端可用 | ○ |

## 10. 应用与框架

| ID | 测试 | 通过标准 | 当前 |
|---|---|---|---|
| APP-01 | Launcher | 桌面可见，图标可点 | ○ |
| APP-02 | SystemUI | 状态栏/导航/锁屏正常 | ◐ |
| APP-03 | Settings | 主列表、WLAN/蓝牙/星闪/移动网络 | ✅ 星闪入口 |
| APP-04 | Settings 稳定性 | 设置项进出不崩溃 | ◐ |
| APP-05 | 锁屏/解锁 | 解锁进入桌面 | ○ |
| APP-06 | Contacts | 列表、新建联系人、拨号 | ◐ 页面通过，号码显示待查 |
| APP-07 | Contacts DataAbility | 查询不超时 | ✅ 历史日志 |
| APP-08 | CallUI | 拨号/来电界面可启动 | ◐ 启动通过 |
| APP-09 | MMS | 会话、发送 | ○ |
| APP-10 | FilePicker | 选择文件、返回 URI | ✗ 扩展发现失败 |
| APP-11 | 文件管理 | 浏览/打开文件 | ○ |
| APP-12 | Camera | 预览/拍照 | ◐ |
| APP-13 | Photos | 图库/缩略图/相册 | ◐ 空图库 |
| APP-14 | Notes | 新建/保存/打开 | ○ |
| APP-15 | Calendar | 日历/日程 | ○ |
| APP-16 | Print | 打印服务/发现 | ○ |
| APP-17 | DLP | 权限/沙箱 | ○ |
| APP-18 | Screenshot | 截屏保存 | ○ |
| APP-19 | Security/Privacy | 权限管理、隐私中心 | ○ |
| APP-20 | PIN/密码 | 设置 PIN、解锁、错误重试 | ✗ TEE 未通 |

## 11. HMDFS / 账号激活专项

| ID | 测试 | 方法 | 通过标准 | 当前 |
|---|---|---|---|---|
| HM-01 | `hmdfs.ko` 编译 | `modinfo` | 6.1.83 vermagic | ✅ |
| HM-02 | 镜像内模块 | debugfs 读 vendor | 模块存在、autoload 第一 | ✅ 离线 |
| HM-03 | 模块加载 | `lsmod`、`/proc/filesystems` | hmdfs 已加载 | ○ |
| HM-04 | HMDFS 挂载 | StorageDaemon 日志 | 无 `err 2` | ○ |
| HM-05 | account.ready | `param get` | `true` | ○ |
| HM-06 | user 100 | BMS 日志 | 当前用户 100 | ○ |
| HM-07 | 应用注册 | `bm dump -a` | Settings/Contacts 等可见 | ○ |
| HM-08 | Launcher | UI/窗口 | 桌面启动 | ○ |
| HM-09 | LocalMount 对照 | `param=false` | 不依赖 hmdfs 也能启动 | ○ |
| HM-10 | 失败回退 | 移除/不加载 hmdfs | 有明确错误，不误判应用 | ○ |

专项细节见 [hmdfs-testing-20261120.md](hmdfs-testing-20261120.md)。

## 12. 稳定性与回归

| ID | 测试 | 通过标准 |
|---|---|---|
| STB-01 | 连续 5 次冷启动 | 每次 account.ready、user 100、Launcher |
| STB-02 | HDC 长连接 | 30 分钟不中断 |
| STB-03 | 显示长稳 | 30 分钟刷新/视频不黑屏 |
| STB-04 | 触摸长稳 | 反复点击/滑动不丢事件 |
| STB-05 | 网络长稳 | ping/吞吐 30 分钟 |
| STB-06 | CAN 长稳 | 连续收发无 bus-off |
| STB-07 | 音频长稳 | 连续播放/录音 |
| STB-08 | 摄像头长稳 | 连续预览/拍照 |
| STB-09 | 重启后配置 | Wi-Fi/显示/GPIO 状态可恢复 |
| STB-10 | 异常断电 | 文件系统可恢复 |

## 13. 证据清单

每次板测至少保存：

```text
/data/rdkhm-logs/boot-status.txt
/data/rdkhm-logs/hilog-current.txt
/data/rdkhm-logs/hilog-previous.txt
/data/rdkhm-logs/screen.jpeg
/data/rdkhm-logs/layout.json
```

主机侧保存：

```text
boot_id
uname -a
镜像 SHA256
dmesg 过滤结果
hilog 关键错误
bm dump -a
ps -A
测试命令和返回码
```

## 14. 失败分类

| 现象 | 优先检查 |
|---|---|
| 旧内核/旧参数 | `/boot/Image`、`param get`、镜像 SHA |
| HMDFS unknown symbol | kernel 是否包含 export 和新 Image |
| `HmdfsMount err 2` | 模块未加载、文件系统未注册 |
| account.ready=false | StorageDaemon/StartUser/HmdfsMount |
| BMS user -2 | 账号激活，不要先怀疑应用 |
| Launcher 黑屏 | user 100、BMS、SystemUI、RenderService |
| 触摸无反应 | powerStatus、event 节点、MMI、displayId |
| Wi-Fi up 失败 | rwnx timeout、cmd queue、固件/模块 |
| 音频无声 | 声卡、路由、HDI、jack |
| 摄像头无节点 | UVC/CSI、HDF config、权限 |
| CAN 失败 | SPI 时钟、DEV_ID、终端电阻、bus-off |
| verifier mismatch | 并发 build 改了 packages |

## 15. 测试记录模板

```text
日期:
测试人:
板卡 IP:
boot_id:
kernel:
镜像 SHA256:
镜像来源/构建时间:
param enabled:
HMDFS 加载:
account.ready:
BMS 当前用户:
Launcher:
HDMI:
触摸:
音频:
摄像头:
Wi-Fi:
蓝牙:
SLE:
CAN:
GPIO:
应用:
异常日志路径:
结论: PASS / PARTIAL / FAIL / BLOCKED
```

## 16. 发布门槛

### P0 可用性

- 冷启动无 panic
- account.ready=true，user 100
- Launcher/SystemUI 可见
- HDMI 显示和触摸可用
- HDC 可连接

### P1 基础外设

- 以太网或 Wi-Fi 至少一个可用
- 音频播放
- USB 键鼠/摄像头按需可用
- GPIO/CAN 按项目需要可用

### P2 功能完整

- Wi-Fi/蓝牙/SLE/4G 按产品定义
- 摄像头预览/拍照/保存
- GPU/NPU/VPU 按应用需求
- 主要 HAP 可启动

### P3 稳定性

- 多次冷启动
- 长稳和热插拔
- SELinux/权限符合预期
- 失败可恢复

## 17. 相关文档

- [全系统详细测试用例](system-test-cases-20261120.md)
- [HMDFS 测试](hmdfs-testing-20261120.md)
- [HMDFS backport](hmdfs-backport-20261120.md)
- [驱动集成](drivers.md)
- [NearLink](nearlink.md)
- [GPIO](gpio.md)
- [Camera/Photos](camera-media-photos-20261119.md)
- [Boot/Audio](boot-audio-fixes.md)
- [板端验证 2026-11-19](board-validation-20261119.md)
- [板端访问](board-access.md)
- [Fastboot 刷写](fastboot-flashing.md)
