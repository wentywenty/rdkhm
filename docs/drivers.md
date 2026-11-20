# Driver integration - 2026-11-15

Results below combine offline integration with the 2026-11-17 board session
where noted. Device-node presence does not prove operation, and driver
availability does not imply that an OpenHarmony application can use it.

| Device | Current integration | Remaining work |
| --- | --- | --- |
| HDMI | DRM/GEM display VDI and software composition; missing panel backlight is treated as an unmodulated output | First frame, buffers, fences and hotplug on X5 |
| USB keyboard/mouse | Kernel HID, evdev, userspace input HDI | Input events and focus on X5 |
| Ethernet | Built-in STMMAC and OH Ethernet service; default DHCP for discovered eth interfaces | Link and DHCP validation |
| AIC8800 Wi-Fi | BSP/fullmac modules, firmware, cfg80211, WLAN/WPA/hostapd HDF services | Scan, association, regulatory behavior and AP validation |
| USB serial | CH341, CP210x, FTDI and PL2303 modules; serial DDK HDF service | Enumeration, DDK app permission and I/O validation |
| USB 4G/LTE | SIMCom SIM7600G-H (`1e0e:9001`) QMI mode; `option`/`usb_wwan` and `qmi_wwan`/`cdc-wdm`/`usbnet` (plus `cdc_ncm`/`cdc_mbim` alternates) selected in `config/kernel/modules.json` | SIM insertion, network registration, `wwan0` data path and OpenHarmony RIL/telephony integration unverified; the existing image and driver bundle predate this selection |
| SPI | spidev module; board DT pinmux retained | Only DT-declared devices can bind; app-facing access policy |
| CAN | SocketCAN raw/BCM, M_CAN, TCAN4x5x and gs_usb modules; TCAN4550 SPI clock clamped to 10 MHz by `kernel/0018`; classic CAN and CAN-FD loopback verified | External bus/transceiver, termination, second node and application integration unverified |
| USB camera | UVC kernel module; USB camera peripheral/interface components, common V4L2 provider, camera host HDF registration and `camera_host_config.hcb` packaging | Physical `/dev/video*` enumeration, format negotiation and preview/capture stream validation |
| ES8326 audio | Kernel modules, ALSA hooks, Audio HDI and 48 kHz stereo policy | Real playback/capture, mixer routing, mute/gain and jack detection |
| WS73 USB NearLink | Complete local SDK snapshot, pinned SSAP library, four SHA256-pinned firmware blobs and node permissions | Linux 6.1 API port, kernel module build, SLE service/HDI and Wi-Fi PM work |
| Bluetooth | HDF Bluetooth interface selected; AIC firmware assets present; explicit `bringup/network/rdkhm-bluetooth-init.sh` probe/attach entrypoint | X5 UART path/baud and vendor initialization, Bluetooth HDI and controller validation |
| CSI camera | Existing vendor kernel baseline retained | Camera SDK/HDI and selected sensor configuration |
| GPU | galcore and private glibc EGL/GLES runtime; offscreen probe | Hardware validation, OH native-window/buffer integration |
| BPU | Framework, governor, cores, vendor hardware-I/O object; private DNN runtime; model tensor descriptor probe | Runtime ABI validation, model execution, NNRT backend |
| Video acceleration | Codec HDI v1/OMX components and generic codec libraries are built and packaged | X5 VPU userspace ABI and capability HCS are deliberately not asserted; decode/encode validation requires D-Robotics VPU ABI and a board stream |

## Camera and codec boundary

`bringup/status/camera-codec-status.sh` is packaged as a read-only inventory. It reports
video nodes, HDF services and capability blobs without opening a camera or
changing a format. The board HDF config now registers the upstream USB camera
host, so a real UVC node can be discovered by the OpenHarmony camera service.
CSI sensors are not claimed: the X5 kernel device tree and sensor model are
still required before adding a CSI provider.

`bringup/status/hardware-status.sh` is the unified read-only board acceptance report.
It records connector state, device nodes, network/controller presence, loaded
modules, HDF capability files and SELinux mode in one timestampable output.
Presence is intentionally reported separately from operation: it does not open
GPU/NPU/camera/codec devices, attach Bluetooth, associate Wi-Fi or submit a
render/inference request.

The codec service libraries are present for ABI/build coverage, but no RK or
other vendor capability table is copied to X5. Advertising those entries would
make applications select unsupported hardware. An X5 VPU adapter must provide
the vendor ioctl/allocator ABI and measured format limits before its HCS
capabilities can be added.

### CAN-FD / TCAN4550

The X5 RDK device trees request an 18 MHz SPI clock for the TCAN4x5x, but the
TCAN4550 SPI interface is limited to 10 MHz. At 18 MHz the DEV_ID registers
read as zero and `m_can` reports `Failed to init module`.
`patches/kernel/0018-tcan-spi-max-speed.patch` clamps the SPI clock in
`tcan4x5x_can_probe()` and logs:

```text
clamping SPI speed 18000000 -> 10000000 Hz
```

On 2026-11-19, the rebuilt `tcan4x5x.ko` produced DEV_ID
`0x4e414354 0x30353534` ("TCAN4550"); classic CAN and CAN-FD loopback both
passed. The 20:54 unified image (kernel #6) includes the patch, and the same
loopback tests pass after a cold boot without manually loading a module. This
verifies the controller, driver and FD data path only. No external bus,
termination, second node or application integration has been validated yet.
See [board-validation-20261119.md](board-validation-20261119.md).

## Module bundle

```sh
JOBS=64 bash scripts/build-kernel.sh modules
python3 scripts/import-driver-firmware.py
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/prepare-driver-bundle.py
bash scripts/build-bringup-userspace.sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

`config/kernel/modules.json` selects modules. The preparer resolves dependencies,
checks vermagic, and runs depmod against the built kernel's System.map.
It explicitly selects the target kernel release for modinfo; otherwise kmod can
return host built-in metadata for an identically named module such as rfkill.

The built bundle currently contains 38 modules (28 autoloaded, 10 manual-only),
their metadata, and 21 firmware/configuration files,
including `/vendor/etc/firmware/ws73/{ws73,wifi_cali,btc_cali,wow}.bin`.
`config/kernel/modules.json` now also selects the USB 4G/LTE modem modules, so a
rebuilt bundle will contain more; the existing artifact predates that change.
It also carries the private accelerator runtime described in `accelerators.md`.
`config/kernel/firmware-lock.json` pins the copied BSP assets and the host's signed regulatory database.
`out/driver-firmware` holds the captured bytes. Reimport rejects changed hashes.
The source BSP is read-only. The bytes retain upstream licensing.

The SD packer injects the bundle into vendor ext4, preserving existing OH metadata.
`/vendor/etc/rdkhm-drivers.json` records file hashes, kernel hash and source provenance.
The bootstrap mounts vendor, sets the kernel firmware search path, and loads modules
in dependency order before OpenHarmony init. Failures are reported to the serial
console; boot continues for diagnosis. No automatic module unloading occurs.

## USB 4G/LTE findings

On 2026-11-19 (`<board-ip>:5555`, `6.1.83-rdkhm #1`), `lsusb` reported
`1e0e:9001`: a SIMCom SIM7600G-H (firmware `SIM7600G_V2.0.2`, IMEI
`<imei>`) with six vendor-specific interfaces and no bound driver.
Loading same-build `usb_wwan`, `option`, `usbnet`, `cdc-wdm` and `qmi_wwan`
created `/dev/ttyUSB0`-`ttyUSB4` and `wwan0`; AT commands on `ttyUSB2` returned
`+CME ERROR: SIM not inserted`, so registration, data and telephony were not
tested. The modules are now selected for future bundles, but the flashed image
and `out/driver-bundle` were not rebuilt and do not contain them.

## WLAN details

In this release, `drivers_peripheral_wlan_feature_enable_HDF_NL80211 = false`
selects `client/src/netlink`; `true` selects the kernel HDF sbuf implementation.
X5 needs the former because its AIC8800 driver uses Linux cfg80211/nl80211.
The separately named `wpa_supplicant_driver_nl80211` remains true.
The optional vendor extension VDI is disabled because no X5 extension library exists.

The AIC fullmac module depends on cfg80211 and aic8800_bsp. Firmware is available
before either module loads. The supplied D-Robotics firmware set targets the X5
AIC8800D80 revisions; arbitrary external Wi-Fi adapters are outside this selection.
Advanced vendor commands, random MAC handling and concurrent AP/P2P remain unverified.

On the 2026-11-19 board session `ifconfig wlan0 up` failed with `rwnx_open error
waiting for close time out` followed by `cmd queue crashed` and `add_if: Status
Error(255)`. The command manager marks itself CRASHED after any LMAC timeout and
the vendor recovery is a userspace reload driven by the `DHDISDOWN` uevent, which
OpenHarmony does not handle. `patches/kernel/0016-aic8800-cmd-recovery.patch`
recreates the queue before the next open and clears `RWNX_DEV_STARTED` when
`rwnx_send_add_if()` fails, and fixes the CRASHED workqueue teardown. The first
command timeout's trigger is still unproven; the patch does not prove firmware
recovery. It has not been built or board-tested.

The USB serial DDK uses the upstream Linux sysfs/termios adapter. Its service
requires `ohos.permission.ACCESS_DDK_USB_SERIAL`; this port does not bypass the
permission check. Service registration alone does not prove an application can
enumerate, open or exchange data with an adapter.

## Audio findings

The X5 DT enables `hobot-snd0` with ES8326 and the name `duplex-audio`.
`snd_soc_hobot_sound_duplex_host` matches that compatible string.
The OH ALSA example uses Rockchip control names and an obsolete adapter JSON schema.
The X5 adapter uses `cardId: -1` to select ALSA ID `duplexaudio`; USB enumeration
must not redirect primary audio to another card. The scoped peripheral patch also
fixes fixed-length reads beyond JSON strings and bounds the PCM discovery table.

Board hooks use the kernel's `HPL Playback Volume`, `HPR Playback Volume` and
`ADC Capture Volume` controls. Writes update both capture channels; playback rolls
back the left value if the right write fails. Control descriptors close on errors.
PCM prepare/drop/pause callbacks propagate failures and reset pause state on stop.
Pause is supported only when ALSA advertises it. Unsupported gain, mute and special
channel modes return an error; the legacy bool-only mute getter reports false.
Hardware volume zero is not treated as a guaranteed hardware mute.

The primary v5 Audio HDI service, adapter JSON, policy XML, ALSA configuration and
sound-device permissions are packaged. Policy selects S16LE stereo at 48 kHz,
within the codec's advertised rates. Logical Speaker/MIC names map to the ES8326
codec path; they do not assert an onboard loudspeaker or microphone. Fixed-route
path selection is used, and jack events/routing still need board validation.

`bash scripts/test-audio.sh` uses mocked ALSA I/O with real libasound value objects
under ASan/UBSan to check channel writes, range rejection, error cleanup and
pause/stop/restart state. The OH build checks the real AArch64 headers and ABI.
These are not hardware audio tests.

## Source references

- Reference BSP: `config/sources/families/hobot-x5.conf`, `packages/bsp/hobot-x5/vendor/etc/firmware`.
- X5: `arch/arm64/boot/dts/hobot/x5-rdk-v1p0.dts`, `x5-rdk.dtsi`, `drivers/net/wireless/aic8800`.
- OH: `drivers/peripheral/wlan/client/BUILD.gn`, `drivers/peripheral/audio/supportlibs/alsa_adapter`.
- OH Ethernet: `foundation/communication/netmanager_ext/services/ethernetmanager/src/ethernet_management.cpp`.
