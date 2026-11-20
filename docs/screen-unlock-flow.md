# RDKHM 退出锁屏流程

本文记录 RDK X5 OpenHarmony 板端从锁屏状态退出，并确认桌面窗口已经创建的流程、证据和回滚方式。

> 本文中的自动解锁 HAP 是开发板绕过方案，不是正式密码/PIN 认证解锁。它直接调用 `unlocking()`，不能作为产品或安全方案发布。

## 1. 角色和边界

- 板端：RDK X5，OpenHarmony standard system。
- 输入：QDtech MPI5001 USB 触摸屏，Linux `hid-multitouch`。
- HDC：TCP `5555`，不是 ADB。
- 当前示例地址：`<board-ip>:5555`。板子 IP 每次启动可能变化，不能写死到镜像。
- 屏幕锁 HAP：`com.ohos.systemui/SystemUI-ScreenLock.hap`。
- 桌面 HAP：`com.ohos.launcher/Launcher.hap`。

## 2. 正常锁屏退出链路

正常链路大致为：

```text
触摸滑动
  -> MMI / InputKeyFlow
  -> ScreenLockWindow
  -> ScreenLockService.unlockScreen()
  -> 账户/密码校验
  -> ScreenLockService.unlocking()
  -> hiddenScreenLockWindow
  -> sendScreenLockEvent(unlockScreenResult, 0)
  -> ScreenLockSystemAbility::SetScreenlocked(false)
  -> AMS 允许启动/聚焦桌面
```

本板此前的异常链路是：

```text
unlockScreen()
  -> 账户已激活
  -> 等待密码/解锁结果
  -> AMS: UnlockScreen timeout
  -> AMS: need password to unlock
  -> 锁屏窗口不消失
```

已知相关差异：

- HAP 侧账户模型使用 user `100`。
- native `ScreenLockSystemAbility::GetUserIdFromCallingUid()` 从 systemui uid `10008` 推得 user `0`。
- `isScreenlockedMap_[0]` 缺失时默认锁定，造成 HAP 与 native 状态不一致。

## 3. 开发绕过 HAP

当前工作区中的 screenlock 源码已经做了开发绕过：

```text
sources/oh/openharmony-full/applications/standard/screenlock/
  features/screenlock/src/main/ets/com/ohos/model/screenLockService.ts
```

`unlockScreen()` 开头直接执行：

```ts
this.unlocking();
return;
```

原来的账户判断和 `mUnLockBeginAnimation()` 不会执行。

这版 HAP 的产物：

```text
sources/oh/openharmony-full/applications/standard/screenlock/
  product/phone/build/default/outputs/default/phone-entry-default-signed.hap
SHA256: 85da6170128efeefebffa0992acd8f31758763e79d5c05e47f93c74d3573a10b
```

签名验证：

```sh
JAR=<workspace>/sources/oh/openharmony-full/prebuilts/ohos-sdk/linux/20/toolchains/lib/hap-sign-tool.jar
java -jar "$JAR" verify-app \
  -inFile /path/to/phone-entry-default-signed.hap \
  -outCertChain /tmp/screenlock-cert.cer \
  -outProfile /tmp/screenlock-profile.p7b
```

应看到：

```text
verify-app success
```

## 4. 前提检查

先确认 HDC 可用：

```sh
export PATH=<workspace>/thirdparty/command-line-tools-26/command-line-tools/sdk/default/openharmony/toolchains:$PATH
hdc tconn <board-ip>:5555
hdc list targets
hdc -t <board-ip>:5555 shell id
```

确认系统进程和锁屏窗口：

```sh
hdc -t <board-ip>:5555 shell \
  'pidof foundation; pidof com.ohos.systemui; pidof com.ohos.launcher'

hdc -t <board-ip>:5555 shell \
  'hidumper -s WindowManagerService -a "-a" | grep -E "ScreenLockWindow|EntryView|Focus window"'
```

注意：`hdc list targets` 里有 target 不代表 shell 可用。目标可能是上一个 boot 留下的失效 target。shell 无返回时先重置本地 HDC 客户端，不要先重启板子：

```sh
hdc kill
hdc start
hdc tconn <board-ip>:5555
```

## 5. 安装自动解锁 HAP

### 5.1 推送

```sh
HAP=<workspace>/sources/oh/openharmony-full/applications/standard/screenlock/product/phone/build/default/outputs/default/phone-entry-default-signed.hap

hdc -t <board-ip>:5555 file send "$HAP" /data/local/tmp/SystemUI-ScreenLock.dev.hap
```

### 5.2 挂载并备份旧 HAP

```sh
hdc -t <board-ip>:5555 shell \
  'mount -o rw,remount /'

hdc -t <board-ip>:5555 shell \
  'cp -p /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap \
        /data/local/tmp/SystemUI-ScreenLock.recovery.old'
```

### 5.3 替换并校验

```sh
hdc -t <board-ip>:5555 shell \
  'cp /data/local/tmp/SystemUI-ScreenLock.dev.hap \
       /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap; \
   chmod 644 /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap; \
   sync; \
   sha256sum /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap'
```

期望：

```text
85da6170128efeefebffa0992acd8f31758763e79d5c05e47f93c74d3573a10b
```

### 5.4 重启 systemui

```sh
hdc -t <board-ip>:5555 shell \
  'kill -9 $(pidof com.ohos.systemui); sleep 4; pidof com.ohos.systemui'
```

新进程必须起来。不要在这里重启整机。

## 6. 模拟触摸退出锁屏

屏幕是 800x480 时，使用一次从下往上的滑动：

```sh
hdc -t <board-ip>:5555 shell \
  'uitest uiInput swipe 400 400 400 100 600'
```

成功时 `hilog` 中应出现：

```text
ScreenLock-ScreenLockService --> unlockScreen
ScreenLock-ScreenLockService --> unlocking
ScreenLock-ScreenLockService --> hiddenScreenLockWindow finish
sendScreenLockEvent: typeName unlockScreenResult typeNo 0
SetScreenlocked state:0, userId:100
UnlockScreen end
```

关键判断条件：

```text
SetScreenlocked state:0
```

`state:1` 仍然表示锁定，不能算解锁成功。

## 7. 确认桌面窗口

```sh
hdc -t <board-ip>:5555 shell \
  'hidumper -s WindowManagerService -a "-a" | grep -E "ScreenLockWindow|EntryView|Focus window"'
```

成功时应有真实的 `EntryView` 尺寸，例如：

```text
EntryView  0  2688  4  2001 1 0 0 8 [0 0 800 480]
Focus window: 4
```

如果 `EntryView` 是 `[0 0 0 0]`，通常说明 HDMI/display 当时没有启用，窗口创建时拿不到有效显示尺寸。此时先确认：

```sh
hdc -t <board-ip>:5555 shell \
  'cat /sys/class/drm/card0-HDMI-A-1/status; \
   cat /sys/class/drm/card0-HDMI-A-1/enabled'
```

在 HDMI 已 `enabled` 后，再重启 launcher：

```sh
hdc -t <board-ip>:5555 shell \
  'kill -9 $(pidof com.ohos.launcher); sleep 2; uitest uiInput keyEvent Home; sleep 5'
```

然后重新检查 `EntryView` 是否变成 `800x480`。

## 8. 截图验证

```sh
hdc -t <board-ip>:5555 shell \
  'uitest screenCap -p /data/local/tmp/desktop-final.png -d 0'

hdc -t <board-ip>:5555 file recv \
  /data/local/tmp/desktop-final.png /tmp/desktop-final.png
```

`screenCap` 失败并报 `Failed to get display pixelMap` 时，先检查 HDMI/display；不能把截图失败当成锁屏未解。

## 9. 防止再次自动锁屏

本板 `powermgr` 会在约 30 秒后进入深度休眠：

```text
PM: suspend entry (deep)
printk: Suspending console(s)
```

唤醒后应停止 `powermgr`：

```sh
hdc -t <board-ip>:5555 shell \
  'service_control stop powermgr; sleep 1; pidof powermgr'
```

`pidof powermgr` 为空表示已停止。这个操作不是永久的，重启后会恢复。

触摸屏不一定是深度休眠的唤醒源；短按物理电源键可以唤醒。不要用长按电源键，长按会断电。

## 10. 回滚

恢复旧锁屏 HAP：

```sh
hdc -t <board-ip>:5555 shell \
  'mount -o rw,remount /; \
   cp -p /data/local/tmp/SystemUI-ScreenLock.recovery.old \
         /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap; \
   kill -9 $(pidof com.ohos.systemui)'
```

恢复旧 launcher HAP 时，对应备份为：

```text
/data/local/tmp/Launcher.recovery.old
```

## 11. 失败和禁止操作

- 不要在锁屏/显示异常时执行 `reboot`。本板已有重启后停在 bootanimation 的记录，恢复代价高。
- 不要在 HDMI 已异常时继续写 `edid_override` 或 `force`。实际测试中出现过写入后 HDC、ping、串口同时失去响应。
- `aa start -a com.ohos.launcher.MainAbility -b com.ohos.launcher` 不是解锁手段；报 `10106102` 表示仍锁定，报 `10103001` 表示 launcher extension 的 visibility 检查失败，不是锁屏成功。
- `screenCap` 成功生成 6.7 KB 白图，不代表桌面正常；必须同时看 `WindowManagerService` 的窗口和 `EntryView` 尺寸。
- 触摸事件到达 launcher 但 `Touch test result is empty` 时，问题在 launcher 页面没有可点击节点，不是触摸驱动。

## 12. 当前参考状态

```text
锁屏 HAP:
  /system/app/com.ohos.systemui/SystemUI-ScreenLock.hap
  sha256 = 85da6170128efeefebffa0992acd8f31758763e79d5c05e47f93c74d3573a10b

Launcher HAP:
  /system/app/com.ohos.launcher/Launcher.hap
  sha256 = 9c1662dcb4d4f4cad001cdc5e5e2b9d582d7591551a80197b64832dc46178ba1

恢复镜像:
  out/images/rdkhm-x5-openharmony-dev-recovery.img
  sha256 = 8f1f4ea9fc17bdef25e2e64d483aba31222504a8ca8e0aaa9f27e49025c61620
```
