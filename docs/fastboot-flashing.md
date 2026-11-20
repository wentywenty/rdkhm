# Fastboot 增量刷写 system / vendor

本文只描述通过 U-Boot fastboot 刷写 SD 卡上的 `system`、`vendor` 分区。
它不涉及 SPI 中的 miniboot/U-Boot 更新，也不涉及整盘 SD 镜像写入。

状态：`--partitions-only` 的离线生成与 sparse 转换已验证；板端 fastboot
枚举和实际写入尚未在本仓库记录中验证。

## 前提

- 板子串口：`ttyS0`，115200。
- 主板上的 device/OTG USB 口连接到主机（与 Linux 下 HDC 使用的口相同）。
- 主机 fastboot 客户端，例如：

  ```sh
  export PATH=/home/robo/platform-tools:$PATH
  fastboot --version
  ```

- U-Boot 启动脚本会从 system 分区加载 `/boot/boot.scr`、`/boot/Image` 和
  `/boot/hobot/*.dtb`，因此刷写的分区必须来自装配后的镜像，而不是 OH 的
  原始 `system.img`/`vendor.img`。

## 分区布局

当前 `rdkhm-x5-openharmony-dev.img` 的 MBR 布局（512 字节扇区）：

| 分区 | 起始 LBA | 扇区数 | 大小 |
| --- | ---: | ---: | ---: |
| config | 8192 | 524288 | 256 MiB |
| system | 532480 | 8912896 | 4.25 GiB |
| vendor | 9445376 | 1048576 | 512 MiB |
| userdata | 10493952 | 4194304 | 2 GiB |

这些值由 `scripts/make-openharmony-image.sh` 在装配时计算，并写入
`out/fastboot/partitions.json` 和 `out/fastboot/fastboot-uboot.cmd`。
重新装配后 system 大小可能变化，vendor 起始 LBA 也会随之变化，务必以最新
生成的文件为准。

## 生成 fastboot 分区

只重建发生变化的分区，然后只装配该分区：

```sh
# 只改 vendor
JOBS=64 bash scripts/build-target.sh vendor_image
bash scripts/make-openharmony-image.sh --partitions-only --only vendor

# 只改 system
JOBS=64 bash scripts/build-target.sh system_image
bash scripts/make-openharmony-image.sh --partitions-only --only system

# 两个一起
bash scripts/make-openharmony-image.sh --partitions-only --only system,vendor
```

输出到 `out/fastboot/`：

```
system.img / system.simg
vendor.img / vendor.simg
partitions.json
fastboot-uboot.cmd
```

说明：

- `--partitions-only` 仍然执行 RDKHM 注入：system 会扩展 256 MiB、`resize2fs`，
  注入 `/boot`、`/rdkhm` 和 busybox；vendor 会注入默认 buffer VDI 和驱动包。
  它只是跳过 CONFIG 分区、MBR 和 7 GiB 整盘生成。
- `.simg` 是 Android sparse 镜像；U-Boot fastboot 支持 sparse，主机客户端会
  自动识别。传给 `fastboot flash` 的 `.simg` 通常远小于 `.img`。
  使用 `--no-sparse` 可以跳过转换。
- 分开运行 system 和 vendor 不会互相覆盖；`out/fastboot/` 中会保留两者的产物。
- vendor 装配会校验 `out/driver-bundle` 与当前内核 `Image`、`.config` 的
  SHA256。内核改动后必须先重新生成驱动包：

  ```sh
  python3 scripts/prepare-driver-bundle.py
  ```

- 不要直接刷 OH 构建目录里的 `system.img`/`vendor.img`。它们没有 `/boot`、
  `/rdkhm` 和驱动包，刷入后 U-Boot 无法启动，或模块/firmware 缺失。

## 进入 U-Boot 控制台

打开串口，例如：

```sh
picocom -b 115200 /dev/ttyUSB0
```

上电或重启板子，在以下提示出现时按空格：

```
Hit <SPACE> key to stop autoboot in 2s
```

进入 `Hobot>` 提示符。

确认 SD 卡对应的 mmc 设备：

```text
mmc list
mmc dev 0
mmc info
printenv devtype devnum devplist
```

如果启动设备是 `mmc0`，后续使用 `-m 0`；如果是 `mmc1`，改成 `-m 1`。

设置裸分区描述。格式是 `"起始 LBA 扇区数"`，单位均为 512 字节扇区：

```text
setenv fastboot_raw_partition_system "0x82000 0x880000"
setenv fastboot_raw_partition_vendor "0x902000 0x100000"
setenv fastboot_raw_partition_userdata "0xa02000 0x400000"
```

这些值应来自 `out/fastboot/fastboot-uboot.cmd`。如果只改了 layout，重新生成
该文件后再使用。

启动 USB fastboot：

```text
fastboot -t emmc -m 0 usb 0
```

- `-t emmc` 选择 MMC/SD 介质；
- `-m` 使用十六进制解析，`0` 表示 mmc0；
- `usb 0` 选择 USB 控制器 0。

另一种等价方式：

```text
fastboot usb 0
```

然后在主机侧切换介质：

```sh
fastboot oem set_medium mmc0
```

`setenv` 只在本次运行生效；只有执行 `saveenv` 才会写入 SPI 的 ubootenv 分区。

## 主机侧刷写

```sh
fastboot devices

fastboot getvar partition-size:system
# 期望 0x110000000  (4,563,402,752)

fastboot getvar partition-size:vendor
# 期望 0x20000000   (536,870,912)

fastboot getvar partition-size:userdata
# 期望 0x80000000   (2,147,483,648)
```

只刷 vendor：

```sh
fastboot flash vendor out/fastboot/vendor.simg
```

只刷 system：

```sh
fastboot flash system out/fastboot/system.simg
```

完成后：

```sh
fastboot reboot
```

`fastboot reboot` 后 U-Boot 会重新执行 `/boot/boot.scr` 并启动新分区。
如果只想退回 U-Boot 控制台，在串口按 `Ctrl+C`，然后执行 `reset`。

## 常见问题

### `fastboot devices` 一直等待

1. 串口确认 U-Boot 已打印 `do fastboot usb`。
2. 换到板子的 device/OTG 口（与 HDC 相同），不要接 host-only 口。
3. 主机 `lsusb` 检查是否出现 `3652:0533`。
4. 更换 USB 线或端口后重试。

### `getvar partition-size` 失败

在 U-Boot 控制台检查变量：

```text
printenv fastboot_raw_partition_system
printenv fastboot_raw_partition_vendor
```

变量名必须与 `fastboot flash <name>` 中的 `<name>` 完全一致。

### 提示设备锁定或拒绝写入

先尝试：

```sh
fastboot flashing unlock
```

然后重刷。若仍被拒绝，需要结合当前 U-Boot 的 flashing lock/AVB 配置单独确认。

### U-Boot 中没有 `fastboot` 命令

说明 SPI 中的 U-Boot 不是包含 fastboot 的配置。此时不能使用本文流程，
需要先更新 U-Boot，或改用整盘 SD 镜像/`ums` 方式。

### USB fastboot 不通时的兜底

在 U-Boot 中把 SD 卡导出为 USB 大容量存储：

```text
ums 0 mmc 0
```

主机确认盘符后直接写分区：

```sh
lsblk
sudo dd if=out/fastboot/vendor.img of=/dev/sdX3 bs=4M status=progress conv=fsync
sudo dd if=out/fastboot/system.img of=/dev/sdX2 bs=4M status=progress conv=fsync
sync
```

`/dev/sdX` 必须按容量和设备型号确认；写错磁盘会破坏主机数据。

## 安全边界

- 确认 `mmc` 设备对应 SD 卡，而不是其他存储。
- 刷写过程中不要断电；中断会导致分区内容不完整。
- 只刷 system/vendor 不会修改分区表、userdata 或 SPI。
- 保留一份完整的 `rdkhm-x5-openharmony-dev.img`，用于整盘恢复。
- 本文不覆盖 SPI miniboot/U-Boot 的更新流程。
