# WS73 USB NearLink integration

Reference: `/home/robo/roboparty_repo/bsp/nearlink-E573H-USBDC`, revision
`bcbd3ecf5bc407a2bd44e9dd5187c054124e9d79`. The reference repository is unchanged.
SDK and SSAP sources are exported into `sources/ws73-sdk` and `sources/nearlink-ssap`.
The original SDK snapshot remains in `sources/ws73-sdk`.
Kernel builds now use the patched archive from
`/home/robo/roboparty_repo/bsp/roboparty_build/packages/blobs/ws73`.
Archive SHA256: `94a02d3a8031482827ebf323261ac596b8c2b63c10e0188f6f58beefa2f18f65`.
`scripts/prepare-ws73-bsp.py` imports it into `sources/ws73-bsp-94a02d3a`
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

The native SSAP codec, server, link state machine, feature manager and hwsle
transport are included as experimental `vendor/lib64/librdkhm_ssap.so`, compiled
against OpenHarmony's AArch64 musl ABI. No vendor glibc/uClibc daemon is reused.
There is no automatic SLE radio startup, daemon, HDI service, public HAP API or
network bridge. Device permissions reserve `/dev/hwsle` and `/dev/hwslechba` for
root while service ownership is still undefined. The transport is a singleton
and has not been validated against the dongle in this workspace.

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
