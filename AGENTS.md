# RDKHM Agent Instructions

## 镜像与构建纪律

- **禁止未经用户明确同意自动构建镜像。** 包括但不限于：
  - `scripts/build-target.sh`
  - `scripts/build-kernel.sh`
  - `scripts/build-openharmony.sh`
  - `scripts/make-openharmony-image.sh`
  - `./rdkhm run package`
  - 任何刷写板卡、重启板卡或远程改板端系统分区的操作。
- 镜像构建耗时且会改变共享产物。构建前必须先说明：
  - 要构建哪个 target
  - 包含哪些源码/patch 变化
  - 预计影响哪个镜像
  - 预计耗时
  - 然后等待用户明确确认。
- **一次只打一版。** 构建、验证、停止。不要为了追一个现象连续重打 `be7d`、`fa1c` 这类多版镜像。
- 不允许用“先打一版看看”替代分析。先在源码和板端只读日志中定位，再决定是否需要构建。
- 源码、本地镜像、板端已刷镜像必须分开记录。源码领先于镜像时，明确标注“未编译/未刷写”，不能暗示板端已经包含。
- 离线 verifier 通过不等于板端验证通过。没有实际启动、显示、输入日志时，不得宣称修复完成。

## 板端状态记录

每次板测必须记录：

- 板卡 IP
- boot_id
- 内核版本
- 板端实际镜像 SHA256
- 本次验证的具体命令和日志路径

当前已知状态（用户确认或日志证据）：

- 显示：物理 HDMI 屏已能点亮，能看到锁屏。
- 触控：触摸屏枚举为 `QDtech MPI5001`，`event1` 存在，MMI 日志已有 `InputKeyFlow` 的 down/move/up，说明设备、evdev、MMI 链路是通的；但仍有 `InputWindowsManager: Failed to obtain physical(-1) display` 和 `windowsPerDisplay_ contain invalid displayId:-1`，不能算完全解决。
- HDC：当前已刷镜像仍需手动 `service_control start hdcd`；源码里的冷启动修复尚未进入已刷镜像。
- MAC：源码 DTS 已加固定 `local-mac-address = [02 52 44 4b 48 4d]`，尚未进入已刷镜像。
- QoS：`0009-qos-proc-unconditional.patch` 已加入源码，未在板端验证。

## 触控问题排查规则

- 不要因为“用户说没触控”就直接断言触摸屏或驱动坏了。
- 按层次分开判断：
  1. USB/内核：`/proc/bus/input/devices`、`/dev/input/event*`、`dmesg`
  2. MMI：`multimodalinput`、`InputKeyFlow`、`InputWindowsManager`
  3. 显示绑定：`displayId`、`GetPhysicalDisplay`、屏幕电源状态
  4. UI：窗口/lockscreen 是否收到 pointer event
- 屏幕默认可能 30 秒息屏。先确认 `powerStatus`，不要拿息屏状态下的触摸行为当作触摸失败。
- 有原始触摸事件不等于触控体验通过；必须验证点击/滑动/解锁和息屏唤醒。

## 沟通与变更规则

- 状态要分清“已解决 / 板端验证过 / 源码改了但没构建 / 只是推断”。
- 不要用镜像数量掩盖未定位的问题。
- 用户说“先别急”“别乱编镜像”时，立即停止构建，只做分析。
- 需要构建时，先给用户一版确定的 scope，得到确认后只打一版。
