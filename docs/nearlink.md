# WS73 USB NearLink integration

Reference: `$RDKHM_BSP/nearlink-E573H-USBDC`, revision
`bcbd3ecf5bc407a2bd44e9dd5187c054124e9d79`. The reference repository is unchanged.
SDK and SSAP sources are exported into `sources/rdk/ws73-sdk` and `sources/oh/nearlink-ssap`.
The original SDK snapshot remains in `sources/rdk/ws73-sdk`.
Kernel builds use the official patched archive at
`thirdparty/downloads/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz`
(`$RDKHM_WS73_ARCHIVE`).
Archive SHA256: `94a02d3a8031482827ebf323261ac596b8c2b63c10e0188f6f58beefa2f18f65`.
`scripts/prepare-ws73-bsp.py` imports it into `sources/rdk/ws73-bsp-94a02d3a`
and applies `patches/nearlink-bsp/0001-x5-linux-6.1.patch`.
The reference repository and original SDK remain unchanged.

## Current boundary

The board enumerates USB ID `ffff:3733`. `plat_soc` provides USB/HCC and firmware loading;
`sle_soc` provides `/dev/hwsle`; `wifi_soc` is a separate Wi-Fi driver. SLE is
not an Ethernet interface. The reference README records a Wi-Fi lazy-init PM
deadlock. All four modules now compile against X5 Linux 6.1.83.
The live loading experiment on 2026-11-16 lost HDC and ping connectivity.
No serial evidence yet identifies the failing stage or cause. Do not equate
this event with the historical Wi-Fi deadlock without a stack trace.
Modules and dependencies are in `modules.manual`, excluded from `modules.load`.
`out/logs/ws73-board-deploy.log` records the experiment. Firmware and ini were
staged; successful firmware boot or radio traffic remains unproven.

## Firmware download fix (2026-11-19)

Minimal SLE stack: `plat_soc + sle_soc`. `wifi_soc` is not required for SLE and
should not be loaded for this test; both `plat_soc` and `wifi_soc` match the
same USB ID.

Symptom: `sle_soc` loaded and created `/dev/hwsle`, but HCC reported
`device boot not finish`, `pm_sle_open` failed with
`PM_BOARD_POWER_FIRMWARE_DOWNLOAD_FAIL` (3), and the USB device kept its
pre-firmware strings.

Root cause: `FIRMWARE_BOARD_INFO_PARA_LEN` was 50. The `/vendor/...` command
string for `wifi_cali.bin` is exactly 50 bytes, so its NUL terminator was
overwritten by the next struct field (`0x01`). `filp_open()` then received
`...wifi_cali.bin\x01` and failed with -30801; `ws73.bin` succeeded because it
is shorter.

Fix: `patches/nearlink-bsp/0002-firmware-para-len.patch` raises the array to
128 bytes.

Board result on 6.1.83-rdkhm: all three firmware files download, HCC reaches
boot-finish, `pm_svc_open` and `pm_sle_open` succeed, and `/dev/hwsle` is
created. HDC and Ethernet remained up. `wifi_soc` was not loaded and no new
network interface appeared.

Remaining: `sle_enable_reply_cb is NULL`; there is still no SLE service, HDI
daemon or HAP API, and no radio traffic. The fixed modules were loaded from
`/data/local/tmp` for diagnosis; they are not yet in the vendor image or the
driver bundle. Temporary direct `printk` instrumentation used to locate the
failure is local to `sources/rdk/ws73-bsp-94a02d3a`; the patch contains only
the length fix.

The native SSAP codec, server, link state machine, feature manager and hwsle
transport are included as experimental `vendor/lib64/librdkhm_ssap.so`, compiled
against OpenHarmony's AArch64 musl ABI. No vendor glibc/uClibc daemon is reused.
There is no automatic SLE radio startup, daemon, HDI service, public HAP API or
network bridge. Device permissions reserve `/dev/hwsle` and `/dev/hwslechba` for
root while service ownership is still undefined. The transport is a singleton
and has not been validated against the dongle in this workspace.

The image includes two read-only bring-up probes. `/rdkhm/ws73-probe.sh` reports
the expected USB ID (`ffff:3733`), module state, firmware and configuration
without loading modules or changing network state. `/rdkhm/bluetooth-init.sh --probe`
reports candidate UARTs and HCI UART modules. Bluetooth attachment is
still explicit (`--attach <hciattach> <uart> <baud>`); no UART mapping is
invented from a generic X5 node and no boot service starts WS73 automatically.

## Earlier SDK limitations

The earlier SDK snapshot lacked:

- `Kconfig`
- `driver/platform/ws73_comm_defconfig`
- `driver/platform/plat_ws73_default_defconfig`
- `driver/wifi/ws73_comm_defconfig`
- `driver/wifi/ws73_wifi_defconfig`
- `firmware/us/ws73.bin`, `wifi_cali.bin`, `btc_cali.bin` (and optional `wow.bin`)

The original copied snapshot supplied the four defconfigs and firmware but
failed on kernel API drift. Its `out/nearlink/preflight.json` describes that
older source only. Current module builds use the complete BSP archive instead.

The new importer uses `ws73_usb_light_v2.config`, the BSP's selected config.
It overrides ARM64, the X5 kernel tree, compiler and vendor firmware/ini paths.
The four BSP firmware hashes match the existing pinned firmware bundle.
The patch adapts platform remove callbacks, timers, unaligned access headers,
kernel varargs, cfg80211 callbacks and obsolete private netlink helpers to 6.1.
No protocol workaround or successful radio operation is claimed.
Delete only the isolated imported tree to re-import the pinned baseline.
Keep patch files for reproducible builds and a targeted rollback.

## Offline checks

```sh
bash scripts/build-nearlink.sh
python3 scripts/prepare-driver-bundle.py
bash scripts/test-nearlink.sh
bash scripts/test-nearlink.sh --ohos
JOBS=64 bash scripts/build-openharmony.sh --build-target images
```

The four upstream SSAP suites run locally under ASan/UBSan and as OpenHarmony
AArch64/musl executables under QEMU, without opening a USB device. QEMU reports
missing HiLog connections because no OH services run in this process-only test.
A passing suite and an AArch64 library establish host code portability,
not USB enumeration, firmware download, SLE interoperability or Wi-Fi operation.

## Userspace SLE probe (2026-11-20)

`bringup/network/sle-adv-probe.c` is a static aarch64 probe built for the
20:54 image. It was run from `/data/local/tmp` with `plat_soc + sle_soc`
manually loaded.

- `open("/dev/hwsle")` succeeds and triggers SLE_OPEN:
  `sle btc open finish`, `sle set sle state 1`, `sle open time:99`.
  Closing returns state 0 in 25 ms.
- The probe sent DLI frames SET_ADV_PARAMS (0x0C02), SET_ADV_DATA (0x0C03)
  and SET_ADV_ENABLE (0x0C05). Each received an A2 response with status
  `0x01` (PENDING per the reference scripts) and data `0x0f`, `0x0b`, `0x0f`.
- Holding the fd for 30 seconds produced no command-complete, ACB or ICB
  events. Advertising is not confirmed; the hand-written DLI dialect may not
  match this firmware revision.
- No second WS73/SLE scanner is available on the host, so over-the-air
  verification was not possible.
- Vendor `application/bin/rk3568/sle/sparklinkd` is aarch64 glibc
  (`/lib/ld-linux-aarch64.so.1`), while the board userland is musl; it cannot
  run unmodified. `sparklinkchba` is not present in that directory.

Current boundary: SLE_OPEN works; advertising, scanning, connection, HDI/HAP
integration and radio traffic remain unverified. Modules remain manual and
`/dev/hwsle` remains root-only.
