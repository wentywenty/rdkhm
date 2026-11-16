# First SD image

Artifact: `out/images/rdkhm-x5-bringup-0.1.img`, 516 MiB.
Checksum: adjacent `.img.sha256` file. This is an offline development milestone,
not a completed OpenHarmony system or a board-tested release.

## Contents and layout

- Patched D-Robotics Linux `6.1.83-rdkhm`, with Binder AccessToken extension,
  AccessToken device, Ashmem, and HDF core.
- Both vendor RDK DTBs: `x5-rdk.dtb` and `x5-rdk-v1p0.dtb`.
- BusyBox 1.36.1, static ARM64, GNU toolchain 11.2; upstream archive SHA256
  `b8cc24c9574d809e7279c3be349795c5d5ceb6fdf19ca709f80cde50e47de314`.
- Dedicated ARM64 test executable for Binder feature/version/token ioctls,
  per-task AccessToken roundtrip, and Ashmem mapping/read/write.
- Serial root shell at 115200 baud with no password; no network service enabled.
- Persistent `/var/log/kernel-probe.log` and `/var/log/dmesg-boot.log`.

| Region | Start | Size | Purpose |
| --- | --- | --- | --- |
| MBR/reserved | 0 | 4 MiB | DOS partition table |
| Partition 1 | 4 MiB | 256 MiB | FAT32 CONFIG, informational README |
| Partition 2 | 260 MiB | 256 MiB | ext4 rootfs, active/boot flag |

The layout follows the local vendor BSP `pack_image.sh`. The U-Boot script
follows the vendor `hobot-boot/debian/boot/boot.cmd` loading convention. It loads
the kernel and DTB from `/boot` on the ext4 partition, with no initramfs.
Board IDs `0x0301` and `0x0302` select the corresponding DTB. Unknown IDs stop
automatic boot. Optional overlays are not applied in this diagnostic image.
Existing X5 QSPI boot firmware is required; the image does not include miniboot
or modify QSPI. Kernel module drivers are not packaged at this stage.

## Verification performed

`scripts/verify-bringup-image.py` reads the regular image file, extracts the
rootfs to a temporary file, runs read-only e2fsck, checks partition offsets,
root ownership, device nodes, `/bin/sh`, kernel/DTB/program hashes, the stage
marker, and the U-Boot script header. No disk mounts or root access are needed.
The static BusyBox executable also runs under QEMU user-mode emulation.

These checks do not prove X5 boots, the ABI probes pass on that kernel, HDMI
works, or OpenHarmony runs. The board is not connected. No user SD card or board
has been modified.

## Not included

OpenHarmony init/services, HDC, Launcher, HAP runtime, display/input HDIs, Wi-Fi,
GPU/BPU acceleration, camera and hardware codecs are not present in this image.
The full source tree and `rdk_x5` build target are separate ongoing work.
The probes are smoke tests, not full IPC/security qualification: transaction
token propagation and permissions under different UIDs still need runtime tests.
