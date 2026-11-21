# HMDFS / 账号激活测试文档

## 1. 目标

验证 X5 6.1.83 上的 HMDFS 6.6 backport 是否能让 StorageDaemon 正常挂载，
并恢复 OpenHarmony 账号激活、user 100、BMS 应用注册和 Launcher 启动。

测试分两层：

1. **离线镜像测试**：确认镜像里确实有正确的 kernel、param、hmdfs.ko。
2. **板端冷启动测试**：确认 HMDFS 实际加载，账号激活成功，UI 可用。

> 离线 verifier 通过不等于板端通过。没有 `boot_id`、`dmesg`、`hilog`、
> BMS 和 UI 日志时，不能标记为“已解决”。

## 2. 当前测试对象

| 项目 | 值 |
|---|---|
| 测试镜像 | `out/images/rdkhm-x5-openharmony-dev.img` |
| 镜像 SHA256 | `7948f022b3073c8ec1688c57774dafd512c78572ae8432ec48f16ea8162329c8` |
| 镜像时间 | 2026-11-20 17:22 |
| 内核 | 6.1.83-rdkhm |
| 镜像内 `/boot/Image` SHA256 | `6e6cb22c769db8d17fe8b7a02f04a3d50e6e8d09e1a60760d8d544a7da75e421` |
| 测试参数 | `const.distributed_file_property.enabled=true` |
| HMDFS 模块 | `/lib/modules/6.1.83-rdkhm/hmdfs.ko` |
| 板端状态 | **未刷写，未板测** |

源码默认参数已恢复为 `false`，用于 LocalMount 保底路径。
上表中的 `true` 只存在于这版测试镜像里。

## 3. 测试前置条件

### 3.1 构建环境

- 同一时间只能有一个 build 写 `out/`。
- 不允许其他 `build-openharmony.sh` / `build.py` / `ninja` 并发运行。
- 构建前确认：

```bash
pgrep -af 'build-openharmony|build.py|gn gen|ninja -w|install.sh|autoreconf'
```

- 构建后检查镜像和打包产物是否一致。

### 3.2 板端记录

每次板测必须记录：

| 字段 | 命令/来源 |
|---|---|
| 板卡 IP | 例如 `10.43.9.213:5555` |
| boot_id | `cat /proc/sys/kernel/random/boot_id` |
| 内核版本 | `uname -a` |
| 实际镜像 SHA256 | 刷写前记录 host 镜像 hash |
| bootevent | `param get bootevent.account.ready` |
| 日志路径 | hilog/dmesg 保存路径 |

## 4. 离线测试

### T1. 镜像完整性

```bash
sha256sum out/images/rdkhm-x5-openharmony-dev.img
cat out/images/rdkhm-x5-openharmony-dev.img.sha256
python3 scripts/verify-openharmony-image.py
```

验收：

```text
SD checksum 一致
MBR / 分区表正确
system/vendor/userdata 文件系统 clean
必要 artifacts 与 packages 一致
```

### T2. 镜像内 kernel 是否正确

从镜像 system 分区取出 `/boot/Image`，与 host 内核比较：

```bash
dd if=out/images/rdkhm-x5-openharmony-dev.img \
   of=/tmp/system.img bs=512 skip=532480 count=8912896
debugfs -R 'dump /boot/Image /tmp/Image' /tmp/system.img
sha256sum /tmp/Image out/kernel/obj/arch/arm64/boot/Image
```

验收：

```text
两个 SHA256 完全一致
```

这一步用于避免“新镜像仍然带旧 kernel”的问题。

### T3. 镜像内 HMDFS 和参数是否正确

```bash
dd if=out/images/rdkhm-x5-openharmony-dev.img \
   of=/tmp/vendor.img bs=512 skip=9445376 count=1048576

debugfs -R 'ls -l /lib/modules/6.1.83-rdkhm' /tmp/vendor.img
debugfs -R 'dump /lib/modules/6.1.83-rdkhm/hmdfs.ko /tmp/hmdfs.ko' /tmp/vendor.img
debugfs -R 'dump /lib/modules/6.1.83-rdkhm/modules.load /tmp/modules.load' /tmp/vendor.img

debugfs -R 'dump /system/etc/param/distributed_file.para /tmp/distributed_file.para' /tmp/system.img
```

验收：

```text
hmdfs.ko 存在
modules.load 第一行包含 hmdfs.ko
distributed_file.para 中 enabled=true（仅 hmdfs 测试镜像）
```

### T4. 模块 ABI

```bash
modinfo /tmp/hmdfs.ko
```

验收：

```text
vermagic 与板端内核一致：
6.1.83-rdkhm SMP preempt mod_unload aarch64
depends 为空或依赖模块均已打包
```

## 5. 板端冷启动测试

### T5. 启动前记录

刷写前在 host 记录：

```text
image path:
image sha256:
kernel sha256:
param value:
build time:
```

不允许在未记录镜像 SHA 的情况下板测。

### T6. 基础启动

板端执行：

```bash
cat /proc/sys/kernel/random/boot_id
uname -a
param get const.distributed_file_property.enabled
param get bootevent.account.ready
lsmod | grep hmdfs
cat /proc/filesystems | grep hmdfs
```

通过条件：

```text
kernel 版本为 6.1.83-rdkhm
enabled=true
account.ready=true
lsmod 中能看到 hmdfs
/proc/filesystems 中出现 hmdfs
```

失败时优先看：

```bash
dmesg | grep -iE 'hmdfs|unknown symbol|StorageDaemon|StartUser|account'
```

重点排除：

```text
hmdfs: Unknown symbol ...
HmdfsMount: failed to mount hmdfs, err 2
StartUser failed
ActivateDefaultOsAccount failed due to timeout
```

### T7. 账号和 BMS

```bash
param get bootevent.account.ready
bm dump -a | head -30
```

通过条件：

```text
account.ready=true
BMS 当前用户不再是 -2
能看到 user 100 相关应用
```

失败时记录：

```bash
hilog -x | grep -iE 'account|StartUser|BMS|user 100|user -2'
ps -A | grep -E 'launcher|systemui|foundation'
```

### T8. Launcher 和 UI

通过条件：

```text
Launcher 进程存在
桌面可见
触摸/点击/滑动可用
锁屏可解锁
```

同时确认 SystemUI 和 Launcher 不是仅“进程存在”但窗口未显示。

建议检查：

```text
HDMI 输出状态
input event 节点
Launcher 窗口是否在前台
```

### T9. 应用注册

至少检查：

```text
Settings
Contacts
Mms
FilePicker
Launcher
SystemUI
```

通过条件：

```text
bm dump -a 能看到对应 bundle
点击能启动，没有 bundle not exist / timeout
```

### T10. HMDFS 回归对照

建议保留两版测试：

| 版本 | param | 预期路径 |
|---|---|---|
| 保底版 | `false` | `LocalMount`，不依赖 hmdfs |
| HMDFS 版 | `true` | `HmdfsMount`，依赖 hmdfs.ko |

两版都必须验证账号激活和 Launcher。
不能用 `false` 版本通过来证明 `true` 版本正常。

## 6. 当前测试结果

| 测试项 | 结果 | 说明 |
|---|---|---|
| hmdfs.ko 编译 | PASS | 6.1.83 vermagic |
| 镜像内 boot Image | PASS | 与当前 kernel Image SHA 一致 |
| 镜像内 param=true | PASS | 仅测试镜像 |
| 镜像内 hmdfs.ko | PASS | vendor 中已确认 |
| 完整镜像 verifier | FAIL | `/system/lib64/libaccountmgr.z.so` 与当前 packages 不一致 |
| 板端冷启动 | NOT RUN | 镜像未刷 |
| hmdfs 实际 mount | NOT RUN | 旧板端内核曾报 unknown symbol |
| account.ready / user 100 | NOT RUN | 等待冷启动 |
| Launcher / UI | NOT RUN | 等待冷启动 |

### 当前 verifier 失败说明

最近一次：

```text
FAIL: Artifact mismatch: /system/lib64/libaccountmgr.z.so
```

原因是构建期间有其他并发 build 修改了 `out/rdk_x5/packages/phone`，
镜像组装后又发生了变化。该失败目前不能归因于 HMDFS，但也说明这版镜像
**不能标记为完全验证通过**。

需要停止其他构建后，重新执行一次干净的：

```text
images -> prepare-driver-bundle -> make-openharmony-image -> verify
```

## 7. 失败分类

| 现象 | 优先检查 |
|---|---|
| `Unknown symbol filemap_remove_folio` | 板端 kernel 是否为新 Image |
| `failed to mount hmdfs, err 2` | `hmdfs.ko` 是否加载、`/proc/filesystems` 是否有 hmdfs |
| `account.ready=false` | StorageDaemon、StartUser、HmdfsMount 日志 |
| BMS 当前用户 `-2` | 账号激活是否完成，不要先怀疑应用 HAP |
| Launcher 不启动 | user 100、BMS bundle 注册、SystemUI/窗口状态 |
| 应用在 `/data/app` 但不可用 | 是否注册到 user 100 |
| verifier artifact mismatch | 是否有并发 build 修改 packages |

## 8. 测试记录模板

```text
日期:
板卡 IP:
boot_id:
kernel:
镜像 SHA256:
param enabled:
hmdfs 加载: yes/no
account.ready:
BMS 当前用户:
Launcher:
触摸:
应用启动:
日志路径:
结论:
```

## 9. 相关文件

- `docs/hmdfs-backport-20261120.md`
- `patches/kernel/0019-hmdfs-backport.patch`
- `config/kernel/openharmony-base.config`
- `config/kernel/modules.json`
- `out/images/rdkhm-x5-openharmony-dev.img.sha256`

全系统外设和功能测试见 [system-test-plan-20261120.md](system-test-plan-20261120.md)。
