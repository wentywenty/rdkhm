# RDK X5 40-pin GPIO 与 PinTool

记录日期：2026-11-19。2026-11-19 20:54 统一镜像已刷写；`gpio-daemon` 冷启动已验证。`PinTool.hap` 文件已注入 system 分区，但当前 BMS 未注册该 bundle，PinTool UI 不可用。

## 范围

- 40pin 引脚映射、当前 mux 状态和可当 GPIO 使用的引脚
- Linux 侧 sysfs/GPIO chardev 能力
- `/rdkhm/gpio` 命令行工具与 `/rdkhm/gpio-daemon` 服务
- `com.rdkhm.pintool` HAP（ArkTS UI + NAPI）
- 镜像注入、init 启动和权限边界

## 分层

| 层 | 位置 | 说明 |
| --- | --- | --- |
| Linux | `sources/rdk/x5-kernel` | `CONFIG_GPIOLIB`、`CONFIG_GPIO_SYSFS`、`CONFIG_GPIO_CDEV`、`CONFIG_PINCTRL_HORIZON`；6 个 gpiochip |
| 数据 | `config/gpio/rdk_x5_40pin.json` | 28 个信号针；物理针、GPIO、chip/line、SoC 功能、mux 状态 |
| 工具 | `bringup/gpio/rdkhm-gpio.c` | sysfs CLI：`list/show/export/get/set/dir/unexport` |
| 服务 | `bringup/gpio/rdkhm-gpio-daemon.c` | Unix socket + TCP 回环；按请求 exec `/rdkhm/gpio` |
| 诊断 | `bringup/gpio/gpio-status.sh` | gpiochip、socket、daemon、映射、当前 claimed pads |
| UI | `apps/rdkhm-pintool` | bundle `com.rdkhm.pintool`；NAPI `libpintool.so` |
| 构建 | `scripts/build-pintool-hap.sh` | hvigor 构建 + `hap-sign-tool` 签名 |

## 当前 gpiochip

固定 `gpio-base`，与板端 `/sys/class/gpio/gpiochipN` 一致：

| 控制器 | base | ngpio | 设备 |
| --- | ---: | ---: | --- |
| `ls_gpio1` | 347 | 17 | `34130000.gpio` |
| `ls_gpio0` | 379 | 32 | `34120000.gpio` |
| `dsp_gpio` | 411 | 23 | `32150000.gpio` |
| `hs_gpio1` | 434 | 18 | `35070000.gpio` |
| `hs_gpio0` | 466 | 31 | `35060000.gpio` |
| `aon_gpio` | 498 | 8 | `31000000.gpio` |

40pin 映射公式：

- `ls_gpio0` line `N` → 全局 `379 + N`
- `ls_gpio1` line `N` → 全局 `347 + N`
- `dsp_gpio` line `N` → 全局 `411 + N`
- `hs_gpio0/1`、`aon_gpio` 同理按 base 加 line

## 映射状态

完整表在 `config/gpio/rdk_x5_40pin.json`。当前快照（2026-11-19）：

可直接当 GPIO（没有驱动 claim，按 RDK `hobot-gpio` 假设默认 mux 为 GPIO）：

`7, 11, 12, 13, 15, 16, 18, 22, 29, 31, 35, 36, 37, 38, 40`

被总线占用：

| 总线 | 物理针 |
| --- | --- |
| `i2c5` | 3, 5 |
| `uart1` | 8, 10 |
| `spi1` | 19, 21, 23, 24, 26 |
| `i2c0` | 27, 28 |
| `pwm3` | 32, 33 |

电源/地：`1, 2, 4, 6, 9, 14, 17, 20, 25, 30, 34, 39`。

注意：`usable_as_gpio` 的含义是“当前没有驱动 claim”。启用对应 i2c/spi/uart/pwm 后，这些针会被重新 mux，状态会变。

## 使用

命令行：

```sh
/rdkhm/gpio list
/rdkhm/gpio show 7
/rdkhm/gpio export 7 out 1
/rdkhm/gpio get 7
/rdkhm/gpio set 7 0
/rdkhm/gpio dir 7 in
/rdkhm/gpio unexport 7
/rdkhm/gpio-status.sh
```

服务（源码已加固，尚未进入 20:54 镜像）：

- Unix socket：`/dev/rdkhm-gpio.sock`，默认 `0660`；`-m` 可覆盖
- TCP：daemon 默认关闭；init 的 `rdkhm-gpio` 服务显式 `-t` 为 PinTool 开启 loopback TCP；手动启动默认关闭，`-t`/`RDKHM_GPIO_TCP_ENABLE=1` 可开启调试
- 端口可用 `RDKHM_GPIO_TCP_PORT` 覆盖
- Unix peer 默认只允许 root；`RDKHM_GPIO_ALLOWED_UID`/`RDKHM_GPIO_ALLOWED_GID` 可放行调试 UID/GID
- 工具路径/映射可用 `RDKHM_GPIO_TOOL`、`RDKHM_GPIO_MAP` 覆盖
- `rdkhm-gpio` 默认拒绝 `usable_as_gpio=false`/被 claim 的针；
  `RDKHM_GPIO_ALLOW_CLAIMED=1` 仅用于显式调试
- PinTool HAP 仍走 TCP；init 服务显式 `-t` 保留该 loopback 调试路径。
  长期仍应完成 PinTool 到 Unix/SA 的改造，而不是依赖无认证 TCP

协议（每行一个请求）：

```text
list
show <pin>
export <pin> [in|out] [0|1]
unexport <pin>
get <pin>
set <pin> <0|1>
dir <pin> <in|out>
ping
quit
```

响应：

```text
OK
<payload>
.
```

或

```text
ERR <exit-code>
<diagnostic>
.
```

## 构建

```sh
./rdkhm build pintool        # 构建/签名 out/haps/rdkhm_pintool.hap
./rdkhm package pintool      # staging 到 out/stage/pintool
./rdkhm run build            # 统一构建；haps 阶段包含 PinTool
```

- GPIO CLI/daemon 由 `scripts/build-bringup-userspace.sh`（kernel 阶段）交叉编译
- HAP 需要 `java`、hvigor、API20 SDK/NDK
- 镜像组装在 `out/haps/rdkhm_pintool.hap` 存在时注入 `/system/app/com.rdkhm.pintool/PinTool.hap`
- `PinTool.hap` 位于 `/system/app/com.rdkhm.pintool/`，但当前 `bm dump -n com.rdkhm.pintool` 报错、`bm dump -a` 无该 bundle；文件存在不等于已注册/可启动

## Pinmux / DTB

- `pinmux-gpio.dtsi` 已为每条线准备 group：`lsio_gpio0_N`、`lsio_gpio1_N`、`hsio_gpio0_N`、`hsio_gpio1_N`、`aon_gpio_N`、`dsp_gpio0_N`。
- 在板级 DTS 中通过 `pinctrl-0` 引用这些 group；Linux 没有通用 userspace mux 接口。
- 不要给要交给用户态控制的线加 `gpio-hog`，否则会被内核占用、无法 export。
- 被总线占用的针要变成 GPIO，需要在 DTB 中 disable 对应节点，或显式加 GPIO pinctrl，然后重编 dtb/镜像。
- RDK Ubuntu 的参考实现是 `hobot-io` 的 `RDK_X5_PIN` 表 + `srpi-config` 改 `/boot/hobot/x5-rdk.dtb` 的 status；本工程吸取映射表，但把配置放在编译期。


## 待改代码

| 优先级 | 位置 | 问题 | 目标 |
| --- | --- | --- | --- |
| 状态 | 位置 | 说明 |
| --- | --- | --- |
| 已改，源码 | `bringup/gpio/rdkhm-gpio.c` | `pin_allowed()` 默认拒绝 `usable_as_gpio=false`/被 claim 的针；`RDKHM_GPIO_ALLOW_CLAIMED=1` 仅用于显式调试 |
| 已改，源码 | `bringup/gpio/rdkhm-gpio-daemon.c` | socket 默认 `0660`；TCP 默认关闭（`-t`/`RDKHM_GPIO_TCP_ENABLE=1`）；Unix 侧 `SO_PEERCRED` 默认只允许 root/显式 UID/GID |
| 已加，待构建/enforce | `overlay/vendor/drobotics/rdk_x5/sepolicy` | `rdkhm_gpio` domain、`rdkhm_gpio_exec`/`rdkhm_gpio_socket` 类型、`file_contexts`、init `secon` |
| 已加，待构建/BMS 验证 | `install_list_capability.json` | 已补 `com.rdkhm.pintool` 签名条目；当前镜像仍是旧文件 |
| 未改，由 init `-t` 保留 | `apps/rdkhm-pintool` | NAPI 仍连 TCP `127.0.0.1:9800`，HAP 仍申请 `ohos.permission.INTERNET`；init 服务显式 `-t` 让 UI 继续使用 loopback TCP，长期改 Unix/SA |
| 已改，板端未更新 | `bringup/gpio/gpio-status.sh` | `head -100` 已改 `head -n 100`；板上旧脚本待下次构建 |
| 待复核 | `config/gpio/rdk_x5_40pin.json` / CLI | Pin 7 等 usable 针仍可能是 I2S/总线功能；DTS/总线启用后重新生成并复核 |

## HAP 是否进镜像

`config/build/haps.json` 的 `image.extra` 已登记 `rdkhm_pintool`，
`scripts/image_haps.py` 在 `make-openharmony-image.sh` 中注入
`out/haps/rdkhm_pintool.hap` 到 `/system/app/com.rdkhm.pintool/PinTool.hap`。
2026-11-19 20:54 镜像板端已确认该文件存在（1469931 bytes），
HAP 由 `scripts/build-pintool-hap.sh` 用 OpenHarmony release key 签名。

但 20:54 镜像的 BMS 当前没有注册这个 bundle：`bm dump -n com.rdkhm.pintool`
报错，`bm dump -a` 也没有该 bundle。源码已补
`install_list_capability.json` 的 Pintool 签名条目，但当前镜像仍是旧文件；
需要重建/刷写后再验证 BMS 注册和 UI。注意当前镜像 BMS 同时缺少
Launcher/Note，不能把 PinTool 单独当成唯一问题。

## 权限边界

当前是 **bring-up 权限模型**，不是可量产的权限模型：

源码已加固（尚未进入 20:54 镜像）：

- `rdkhm-gpio` 默认拒绝 `usable_as_gpio=false`/被 claim 的针
- daemon 默认只开 Unix socket `0660`，TCP opt-in，Unix 侧用 `SO_PEERCRED`
  限制 root/显式允许的 UID/GID
- 已加入 `rdkhm_gpio` SELinux 域、`rdkhm_gpio_exec`/`rdkhm_gpio_socket`
  类型和 `file_contexts`；init 服务带 `secon`
- `install_list_capability.json` 增加 `com.rdkhm.pintool` 签名条目

当前 20:54 板上仍是旧 daemon：socket `0666`、TCP 默认开启、无 peer 校验。
所以板上实际行为仍是 bring-up 信任模型，必须重建/刷写后才会使用上面的加固。
即使加固后，服务仍以 root 运行，没有 SA/HDI 权限、审计和限速。

影响：本机任意进程或 HAP 都能通过旧服务拉高/拉低未占用引脚，
可能误复位外设、改变总线/电源相关引脚，或在被攻破的应用里变成提权/破坏入口。
TCP 目前只在 loopback，但任何把 9800 转发出去的环境都会进一步扩大暴露面。

量产前还需要：

1. PinTool 改走 Unix socket 或 SA，移除 TCP 依赖；调试 TCP 必须显式打开
2. 正式接口改为 SAMGR SA/HDI（或受控 native service）+ 专用权限，不再让 HAP 直接走 sysfs
3. 增加审计和限速，明确哪些 UID/GID/应用可以控制哪些针
4. 在板端 enforce SELinux 并验证 `rdkhm_gpio` 域策略

本文档中的当前实现只用于 bring-up，不代表这个权限模型可以随产品发布。

## 板端验证

板卡：`10.43.9.213:5555`

2026-11-19 20:54 统一镜像冷启动（旧 daemon；源码加固尚未进入该镜像）：

- `gpio-daemon` 运行，`/dev/rdkhm-gpio.sock` 存在，TCP `127.0.0.1:9800` 监听
- 6 个 gpiochip：base 347/379/411/434/466/498
- `/rdkhm/gpio list` 和 `/rdkhm/gpio show 7` 正常
- Pin 7 CLI 复测：`export 7 out 1` → `get 7` = 1 → `set 7 0` →
  `dir 7 in` → `get 7` = 1 → `unexport 7`，全部 rc=0；`gpio420` 已移除
- `PinTool.hap` 文件位于 `/system/app/com.rdkhm.pintool/`
- `bm dump -n com.rdkhm.pintool` 报错，`bm dump -a` 没有该 bundle；
  BMS 未注册，PinTool UI 不可启动
- 当前镜像显示为黑屏/Launcher 未运行，本轮没有重新启动 PinTool UI
- `gpio-status.sh` 的 `head -100` 在 BusyBox 下报错，源码已改为 `head -n 100`；
  板上旧脚本仍待下次构建更新

更早的 HDC 安装/UI 验证：

- `hdc install -r out/haps/rdkhm_pintool.hap` → `install bundle successfully`
- PinTool 启动后显示 `GPIO service connected` 和 28 针列表
- 在 Pin 7（GPIO 420）上：
  - UI `High` → `/sys/class/gpio/gpio420/value=1`
  - UI `Low` → `value=0`
  - UI `Read` → `direction=in`，界面输出 `get 7 1`
  - 验证后已 unexport，未改动其他引脚
- 证据：
  - `out/board-logs/20261119-pintool/screen-connected.jpeg`
  - `out/board-logs/20261119-pintool/layout-connected.json`
  - `out/board-logs/20261119-pintool/layout-pin7-read.json`
- `./rdkhm check`：14 tests OK；GPIO daemon Unix/TCP 冒烟测试通过

## 已知限制

1. 20:54 镜像已刷写；`gpio-daemon` 冷启动已验证。PinTool HAP 文件存在，
   但 BMS 未注册，UI 不可用。
2. 需要排查 `install_list.json` / `install_list_capability.json`、HAP 签名/allowlist
   和 BMS 扫描；当前镜像的 BMS 本身也缺少 Launcher/Note bundle。
3. `gpio-status.sh` 的 `head -100` 已改为 `head -n 100`；板上旧脚本需等下次构建。
4. 13 个被总线占用的针仍需 DTB 处理。
5. JS `@ohos.net.socket` 的 `connect` promise 在当前镜像上不回调（native connect 已成功）；PinTool 改用 NAPI 原生 TCP。
6. `PinData.ets` 由 `scripts/gen-pin-data.py` 生成；改 JSON 后需重新构建/生成。
7. mux 快照会随 DTB/总线启用状态变化，JSON 不是永久结论。

## 相关文件

- `config/gpio/rdk_x5_40pin.json`
- `scripts/gen-gpio-map.py`、`scripts/gen-pin-data.py`
- `bringup/gpio/rdkhm-gpio.c`、`rdkhm-gpio-daemon.c`、`gpio-status.sh`
- `apps/rdkhm-pintool/`
- `scripts/build-pintool-hap.sh`、`scripts/sdk-home.py`、`scripts/test-gpio-daemon.py`
- `overlay/vendor/drobotics/rdk_x5/init.rdk_x5.cfg`
- `overlay/vendor/drobotics/rdk_x5/preinstall-config/install_list.json`
- `config/build/components.json`、`config/build/pipeline.json`
