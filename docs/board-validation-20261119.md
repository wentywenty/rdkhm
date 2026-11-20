# 板端验证记录 - 2026-11-19

本文记录 2026-11-19 的板端只读检查、受控运行态验证和源码结论。
源码、`out/images` 中的镜像、板端已刷镜像三者分开记录，不能互相替代。

## 板端状态

- IP / HDC：`10.43.9.213:5555`（TCP）
- boot_id：`9ade3a96-6eb4-4876-a3dc-f407990d6b5e`
- 内核：`6.1.83-rdkhm #6 SMP PREEMPT`，构建时间 2026-11-19 20:36 CST
- 板型：`D-Robotics RDK X5 V1.0`，活动 DTB 为 `x5-rdk-v1p0.dtb`
- 板端镜像 SHA256：未在板端记录
- 本地 `out/images/rdkhm-x5-openharmony-dev.img.sha256`：
  `db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78`
  - 镜像文件时间 2026-11-19 20:54
  - 板端内核 #6、模块时间和该统一构建一致；板端未单独读取镜像 SHA
  - `STATUS.md` 中较早的 `4368578f...` 和 `8f1f4ea9...` 属于历史记录
- 统一构建后的冷启动已包含 USB HDC 和 CAN-FD 修复；本文以下结果以
  kernel #6 / `db0a75...` 镜像为准

## USB HDC

板端 TCP HDC 正常：`hdcd` 运行，`/proc/net/tcp` 监听 `15B3`（5555），
`hdc list targets` 可以看到 `10.43.9.213:5555`。

USB 侧已验证到板端 gadget/FunctionFS/hdcd 通道：

- `rdkhm-usb.sh` 原先无条件 `mount -t configfs none /config`；
  板上 `/config` 已由 init 挂成 configfs，重复 mount 返回 busy，
  脚本在 `set -eu` 下直接退出
- 修复方式：先检查 `/proc/mounts`，并把 `os_desc/b.1` 和 functionfs
  mount 做成幂等
- 统一构建后的冷启动已自动完成：
  - `/config/usb_gadget/g1` 创建成功
  - `configs/b.1/f1 -> functions/ffs.hdc`
  - `/dev/usb-ffs/hdc` 下出现 `ep0/ep1/ep2`
  - UDC `35300000.usb`：`state=configured`，`current_speed=high-speed`
  - `hdcd` 打开 `ep0/ep1/ep2`，日志显示 `bEnableTCP:1,bEnableUSB:1`
  - `sys.usb.ffs.ready=1`
  - `configfs` 和 `functionfs` 都已挂载
- 主机侧（本构建机）没有看到 `1d6b:0104` 的 USB HDC target；
  板端 UDC 已 configured，说明 USB device 口已经枚举到某个主机。
  需要在物理连接板子的那台 PC 上执行：
  `hdc list targets` 和 `lsusb | grep -i 1d6b:0104`。
- 该修复已进入 kernel #6 的统一构建镜像；板上冷启动可自动拉起。

USB 标识：`idVendor=0x1d6b`，`idProduct=0x0104`。

## CAN-FD

### 结论

TCAN4550 的 SPI 接口上限为 10 MHz；X5 RDK DTS 请求 18 MHz。
18 MHz 下读取 DEV_ID 全为 0，`m_can` 报：

```text
tcan4x5x spi5.0 can0: Failed to init module
```

把 SPI 时钟降到 10 MHz 后，DEV_ID 读到：

```text
0x4e414354 0x30353534   /* "TCAN" "4550" */
```

经典 CAN 和 CAN-FD loopback 均通过。

### 驱动 patch

- `patches/kernel/0018-tcan-spi-max-speed.patch`
- 在 `tcan4x5x_can_probe()` 的 `spi_setup()` 前把
  `spi->max_speed_hz` clamp 到 10 MHz
- 日志会显示：
  `clamping SPI speed 18000000 -> 10000000 Hz`
- 已加入 `config/patches.json` 的 `kernel` collection

### 验证结果

统一构建前的运行态验证：使用 `tcan4x5x.ko` 模块加载，并重新 bind SPI5
控制器，让 DT 重新下发 18 MHz，驱动随后 clamp 到 10 MHz。
统一构建后的 kernel #6 镜像冷启动后，使用同一测试程序再次验证：

```text
CAN_TEST_PASS   id=0x123 dlc=8 data=1011121314151617
CANFD_TEST_PASS id=0x123 len=8 flags=0x5 data=1011121314151617
```

冷启动后无需手动加载模块，`can0` 的 FD 配置生效（MTU 72）；
`/proc/net/can/stats` 从 TX 1 / RX 0 变为有实际收发计数。

### 边界

- 只验证了控制器、驱动和 CAN-FD loopback
- 未接第二个节点/外部收发器，未验证真实总线、终端电阻、错误帧和长稳
- patch 已进入 kernel #6 / `db0a75...` 镜像；外部总线仍需单独验证
- 2026-11-19 外部尝试：把 `CAN_CTRLMODE` 清成 `flags=0x20`（FD，loopback off）
  后发送一帧 FD；`listen` 2 秒没有收到总线流量，`TXF` 没有增加，
  没有检测到 ACK/第二个节点。需要接入 CAN 分析仪或另一个节点后重测。

## HAP 构建状态

### admin_provisioning

- patch：`patches/haps/admin_provisioning-build-config.patch`
- 修复：模块级 `entry/oh-package.json5`、`srcEntry`、`embeddedUI`、
  build-profile SDK/signing、ArkTS 空值检查
- HAP：`out/haps/admin_provisioning.hap`
- SHA256：`37c2b1b790d5110c2a6ff72945f8be7534b3ba255458ee2785faef2b830d79c2`
- `config/build/haps.json` 中 `verified=true`

### theme

- patch：`patches/haps/theme-build-config.patch`
- 修复：`product/phone`、`product/pad` 的模块级 `oh-package.json5`、
  `srcEntry`、`AbilityStage` 导入、`pixelData` 类型、build-profile/SDK
- 两个 module HAP 均构建成功：
  - `phone_wallpaper-default-unsigned.hap`
  - `pad_wallpaper-default-unsigned.hap`
- 暂存 HAP：`out/haps/theme.hap`
- SHA256：`797a81ea12225790fcc3219b2953914735fe729736c34eb4474db7de45391067`
- `config/build/haps.json` 中 `verified=true`

### Settings

- `config/build/haps.json` 中 `verified=true`
- `out/settings/Settings.hap` 已生成（2648954 bytes）
- （历史记录）当时 `make-openharmony-image.sh` 仍只注入 Settings HAP；
  2026-11-19 的统一构建准备已增加 Camera/Photos/Launcher/Notes 等注入，详见
  [image-build-prep-20261119.md](image-build-prep-20261119.md)。
  admin_provisioning/theme 的 HAP 目前是构建产物，未改变镜像注入路径
- Settings patches：
  - `settings/0001-storage-statvfs.patch`
  - `settings/0002-storage-uri.patch`
  - `settings/0003-nearlink-settings-page.patch`

## 统一构建准备

以下检查在 2026-11-19 通过：

- `apply-patches.py --dry-run --only kernel`：19/19 already
- `apply-patches.py --dry-run --only openharmony`：71/71 already
- 干净 kernel HEAD 按顺序应用 `0001..0018`：18 个全部通过
- `./rdkhm check`：14 个测试通过
- `check-patch-format.py`：0 failure
- `check-patch-coverage.py`：91/93 listed（其余 optional/globbed）

## 统一构建后的冷启动

- 本地镜像：`out/images/rdkhm-x5-openharmony-dev.img`
  SHA256 `db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78`
- 板端：boot_id `9ade3a96-6eb4-4876-a3dc-f407990d6b5e`，
  kernel `6.1.83-rdkhm #6`，运行时间约 30 分钟
- USB HDC：冷启动 gadget/FunctionFS/UDC 已 configured，
  `hdcd` 监听 TCP 5555
- CAN-FD：冷启动 `can0` 可用，classic/FD loopback 通过；驱动 clamp 生效
- 主机侧 USB HDC target 仍需要在接 USB 的 PC 上确认

## GPIO / PinTool

2026-11-19 20:54 统一镜像冷启动：

- 6 个 gpiochip：base 347/379/411/434/466/498
- `gpio-daemon` 运行；`/dev/rdkhm-gpio.sock` 存在，
  TCP `127.0.0.1:9800` 监听
- `/rdkhm/gpio list`、`/rdkhm/gpio show 7` 正常
- Pin 7 CLI 复测：`export 7 out 1` → `get 7` = 1 → `set 7 0` →
  `dir 7 in` → `get 7` = 1 → `unexport 7`，全部 rc=0；`gpio420` 已移除
- `/rdkhm/gpio-status.sh` 正常输出，但板上旧脚本的 `head -100` 在 BusyBox
  下会报错；源码已改为 `head -n 100`，待下次构建更新
- 源码已加入 GPIO 加固：CLI 拒绝非 usable/被 claim 的针；daemon 默认
  socket `0660`、TCP opt-in、Unix `SO_PEERCRED`；新增 `rdkhm_gpio`
  SELinux 域和 `install_list_capability` Pintool 条目。这些**尚未进入
  20:54 镜像**，板上仍是旧 daemon（0666/TCP 开启/无 peer 校验）
- `PinTool.hap` 文件位于 `/system/app/com.rdkhm.pintool/`，但
  `bm dump -n com.rdkhm.pintool` 报错、`bm dump -a` 没有该 bundle；
  BMS 未注册，PinTool UI 不可启动
- 当前镜像显示为黑屏/Launcher 未运行，UI 侧测试需等显示恢复

更早的 HDC 安装/UI 验证：PinTool 显示 `GPIO service connected` 和 28 针列表；
Pin 7（GPIO 420）High/Low/Read 均通过，验证后已 unexport。
详见 [gpio.md](gpio.md)。

## RT profile


- `RDKHM_KERNEL_PROFILE=rt` 是 opt-in
- 默认仍使用非 RT defconfig
- `rt` 会应用 `patches/optional/preempt-rt/patch-6.1.83-rt28.patch`
  并使用 `config/kernel/hobot_x5_rdk_ubuntu_rt_defconfig`
- 尚未构建 RT 内核，也未做板端验证

## 未验证项

- USB HDC 主机侧枚举（需要在接 USB 的 PC 上确认）
- CAN 外部总线、第二节点、终端电阻、真实收发和长稳
- admin_provisioning/theme HAP 进入镜像后的运行表现
- PinTool BMS 注册/签名 allowlist、UI 启动/权限和 `gpio-status.sh` 新脚本
- RT 内核启动和实时性
