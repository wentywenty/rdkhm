# QEMU 三条路径任务拆分（A/B/C）— 2026-11-20

本文用于拆分 QEMU 相关工作，**不启动 QEMU、不编译、不刷板**。三条路径目标不同，
不能互相替代：

| 路径 | 目标 | 使用 X5 内核？ | 能否验证 X5 硬件 |
| --- | --- | --- | --- |
| A. 用户态 L1 | 在 x86 主机跑 AArch64 daemon/探针 | 否 | 否 |
| B. OH QEMU 产品 L2 | 构建/启动通用 OpenHarmony QEMU 产品 | 否（用 in-tree `kernel/linux`） | 否 |
| C. X5 内核 virt 适配 | 让当前 6.1.83-rdkhm 内核跑 QEMU `virt` | 是 | 仍不能验证 HDMI/触控/camera 等 X5 设备 |

## 先明确边界

当前 X5 镜像不是 QEMU 目标：

- `out/kernel/obj/.config` 是 `CONFIG_ARCH_HOBOT_X5=y` 的板级配置；
- 没有 QEMU `virt` DTB，只有 `hobot/x5-*` DTB；
- 没有为 QEMU 准备 PL011、virtio-blk/net/gpu 等设备配置；
- X5 的 DRM/HDMI/HDF、camera、audio、CAN、GPIO、BPU/GPU 驱动不在 QEMU 中模拟。

因此：

- **A** 只证明用户态二进制/协议可运行；
- **B** 证明通用 OpenHarmony userspace 能启动，不是 X5 移植验证；
- **C** 才是“让这个内核跑 QEMU”的新移植，但也不能替代 X5 板测。

## A. 用户态 QEMU（L1）

### 范围

用 `qemu-aarch64-static` 执行 `out/` 中的 AArch64 程序，验证：

- Composer/access-token ABI 检查；
- accelerator 私有库闭包、DNN 版本标记、Unix socket 协议；
- NearLink SSAP 的 codec/server/feature/link 四组用例；
- 现有 integration checks、HAP 签名与 image HAP 清单。

### 不包含

- 内核启动、HDF、显示、真实设备 I/O；
- GPU/BPU 实际执行；
- X5 板端行为。

### 具体任务

| ID | 任务 | 产物/证据 |
| --- | --- | --- |
| A1 | 运行 `./rdkhm check`、composer/access-token/HAP 检查 | `out/qemu-validation/l1-*/` |
| A2 | 运行 `test-accelerators.py` / `test-accelerator-socket.py` | 协议与库闭包日志 |
| A3 | 运行 `test-nearlink.sh --ohos` | 四组 suite 日志 |
| A4 | 汇总 pass/fail、失败原因和 host 限制 | 结果记录 |

### 验收

- A1–A3 全部通过；失败项必须有明确复现命令；
- 只声明“用户态可运行”，不声明 X5 硬件或镜像通过。

### 当前状态

按 `docs/qemu-validation.md` 的 2026-11-20 记录，L1 已通过；本任务主要是
可重复执行和归档证据，不需要新构建。

## B. OpenHarmony QEMU 产品（L2）

### 范围

构建并启动 OpenHarmony 提供的 QEMU 产品，验证通用 userspace：

- `qemu-arm64-linux-min`（arm64，最小标准系统，无 JS API）；
- `qemu-arm-linux-headless`（arm32，headless，graphics 关闭）；
- 启动到 `init`、`samgr`、`hdc`、`hilogd`/`hilog`；
- 可选 HDC 用户态网络。

### 关键事实

- 使用 in-tree `kernel/linux`（5.10/6.6），**不是** X5 6.1 内核；
- 不使用 `patches/kernel/` 的 X5 内核补丁；
- 当前 release 的 arm64 QEMU product 构建存在上游产品缺陷；
- 本树没有 arm64 graphics/ArkUI QEMU product。

### 具体任务

| ID | 任务 | 说明 |
| --- | --- | --- |
| B1 | 修 QEMU product 配置/whitelist | `device/qemu/arm_virt` 子系统名、`product_qemu-*` whitelist |
| B2 | 修 host C++ 头文件环境 | clang++15 找不到 GCC 12 的 C++ 标准头；记录可用 `CPLUS_INCLUDE_PATH` 或工具链修复 |
| B3 | 构建 `qemu-arm64-linux-min` | 先解决缺失组件（ffrt/rust_libc/ylong 等） |
| B4 | 启动 arm64 min | 记录串口 console、init/samgr/hdc/hilog |
| B5 | 构建/启动 arm32 headless | 解决 kernel 5.10/6.6 与 HDF audio 路径问题，或改用上游预编译 QEMU 镜像 |
| B6 | 归档镜像/日志/失败分类 | `out/qemu-validation/l2-*/` |

### 验收

- 串口 console 能到 userspace；
- `init`、`samgr`、`hdc`、`hilog` 不进入持续 crash loop；
- 不要求 Launcher/SystemUI/ArkUI；
- 明确标注“QEMU 产品验证”，不能写成“X5 板端通过”。

### 当前阻塞

`docs/qemu-validation.md` 已记录：

- QEMU product 子系统名/whitelist 不正确；
- arm64 product 依赖不完整；
- host clang++ 标准头路径问题；
- arm32 product 的 kernel 版本与 HDF audio 板级路径不匹配。

B 需要先决定：修本树产品，还是使用上游预编译 QEMU 镜像。不要把为 QEMU
产品做的修复无条件塞回 X5 product。

## C. X5 内核 virt 适配

### 范围

让当前 `sources/rdk/x5-kernel` 的 6.1.83-rdkhm 内核在 QEMU `virt` 上启动，
并复用通用 rootfs 或专用 initramfs：

- 新增/选择 QEMU `virt` defconfig；
- 提供 QEMU `virt` DTB，或让 kernel 使用 QEMU 生成 DTB；
- 启用 PL011 串口、GIC、virtio-blk/net、必要的 PCI/IOMMU；
- 准备 QEMU 可读的 rootfs/initramfs；
- 内核启动到 console/shell，再尝试 OpenHarmony userspace（如果复用 B 的 rootfs）。

### 不包含

- X5 HDMI/DRM/composer；
- USB 触摸、camera、audio、CAN、GPIO、WS73、BPU/GPU；
- X5 U-Boot/QSPI/分区启动链；
- 用 QEMU 结果替代 X5 板测。

### 具体任务

| ID | 任务 | 说明 |
| --- | --- | --- |
| C1 | 建 QEMU virt kernel config | 从 X5 config 派生，保留 ARM64/必要 core，补 PL011/virtio/PCI |
| C2 | DTB/启动参数 | QEMU `virt` DTB、`console=ttyAMA0`、root/init 参数 |
| C3 | rootfs | 先 initramfs/shell；再评估复用 B 的 QEMU product rootfs |
| C4 | 启动验证 | QEMU system mode 到 console/shell；记录 panic/驱动缺失 |
| C5 | OH userspace | 只在内核和 virtio 稳定后尝试；不以 HDF/X5 外设成功为标准 |
| C6 | 文档与隔离 | 记录 kernel config/DTB/rootfs 和“非 X5 硬件验证”边界 |

### 验收

- QEMU `virt` 能加载 X5 6.1 内核并到串口 console/shell；
- virtio 控制台/磁盘至少有一个可用；
- 明确记录哪些 X5 驱动未工作；
- 不以“内核启动”声称 OpenHarmony 系统或 X5 板端通过。

### 风险

- X5 内核配置与 QEMU `virt` 设备模型不同，不能只加一个 `-M virt`；
- X5 大量 built-in 驱动在 QEMU probe 失败，可能阻塞启动；
- rootfs/OpenHarmony 服务依赖 X5 分区和 HDF，C 只能先做内核/最小用户态；
- 这是新移植，不是当前镜像的一条启动命令。

## 建议拆分方式

- **A**：独立小任务，无构建；可立即在现有 `out/` 上执行。
- **B**：独立 QEMU product 任务线；需要单独构建目录和日志，避免与 X5 OH
  build 共用/并发写 `out/`。
- **C**：独立内核/rootfs 移植任务线；可在 B 的 rootfs 基础上做，但不要改
  X5 product 的默认配置；单独保存 config/DTB/启动脚本。

## 构建与证据纪律

- A 不构建；B/C 构建前必须明确 target、时间、产物路径并等待批准。
- B/C 不要和 X5 的 `system_image`/`vendor_image`/完整镜像并发构建。
- QEMU 镜像/日志放 `out/qemu-validation/` 或独立 `out/qemu-*`，不提交。
- 每个结论标注：用户态 / QEMU 内核 / QEMU OH / X5 板端，不能混写。
- X5 硬件（HDMI、触控、camera、audio、CAN、GPIO、WS73、BPU/GPU）仍只能在
  X5 板端验收。

## 参考

- `docs/qemu-validation.md`：已有 L1 结果、L2 上游缺陷、L3 graphics 限制。
- `docs/kernel-port.md`：X5 内核配置和板级依赖。
- `out/kernel/obj/.config`：`CONFIG_ARCH_HOBOT_X5=y` 等实际配置。
- `sources/rdk/x5-kernel/arch/arm64/boot/dts/hobot/`：只有 X5 DTB。

## C 执行记录（2026-11-20）

C4 已通过：**X5 6.1.83-rdkhm 内核在 QEMU virt 上启动到 BusyBox shell**。

- 内核源码：`sources/rdk/x5-kernel`
- 独立配置/输出：`out/qemu-x5-kernel`
- 关键配置：`SERIAL_AMBA_PL011=y`、`VIRTIO_MMIO=y`、`VIRTIO_BLK=y`、`PCI_HOST_GENERIC=y`
- Image：`out/qemu-x5-kernel/arch/arm64/boot/Image`（约 29M）
- initramfs：`out/qemu-x5-kernel/initramfs.cpio.gz`（静态 ARM64 BusyBox）
- QEMU：`-M virt -cpu max -smp 4 -m 2048 -nographic`
- 启动命令使用 QEMU 生成的 virt DTB，**没有使用 X5 DTB**
- 证据：`out/qemu-validation/c-x5-kernel-console.log`

边界：

- 只证明 X5 内核 + virtio/PL011 + initramfs 到 shell；
- **没有** OpenHarmony userspace、HDF 完整启动、HDMI/触控/camera/audio/CAN/GPIO/WS73/BPU/GPU；
- 不能替代 X5 板端验证；
- C5（把 OH QEMU rootfs 或 B 的 userspace 接到这个内核）尚未执行。

## C5 尝试记录（2026-11-20）

C4 之后尝试直接用 X5 arm64 system/vendor/userdata 作为 QEMU virtio 盘：

- 第一次：默认 SELinux，init 因 vda root 为 `unlabeled` 被拒绝，随后 panic。
  - 日志：`out/qemu-validation/c5-x5-rootfs-console.log`
- 第二次：`selinux=0 enforcing=0 hardware=rdk_x5`，能进入 init first/second
  stage 并启动一批服务，但 `storage_daemon` critical service 连续崩溃 4 次；
  init 随后 StopAllServices + sysrq panic。
  - 日志：`out/qemu-validation/c5-x5-rootfs-selinux0.log`
  - 关键错误：`/vendor/etc/fstab.rdk_x5` 未挂载/不存在，`storage_daemon` 退出。

结论：X5 production rootfs 不能直接作为 QEMU root 使用；C5 需要用
QEMU arm64 product rootfs，或做专门的 initramfs 先挂载 system/vendor 再进入
OH init。C5 **未通过**，也没有 X5 硬件验证。

补充：尝试构建 `qemu-arm64-linux-min` 作为 arm64 QEMU rootfs，但 product
config 本身不完整。补 `libuv`/`libusb`/`sqlite`/`device_info_manager` 后，
合并 headless 组件又触发：

- `support_jsapi=false`，但 user_auth extension 仍调用 `gen_js_obj`；
- GN 失败，未产出 arm64 rootfs。

因此 C5 仍然 **未通过**，不能把 X5 production rootfs 或半成品 QEMU product
算作 OpenHarmony userspace 验证。
