# Driver integration - 2026-11-15

All results below are offline. No device has been connected or flashed.
Linux driver availability does not imply that an OpenHarmony application can use it.

| Device | Current integration | Remaining work |
| --- | --- | --- |
| HDMI | DRM/GEM display VDI and software composition | Modeset, buffers, fences and hotplug on X5 |
| USB keyboard/mouse | Kernel HID, evdev, userspace input HDI | Input events and focus on X5 |
| Ethernet | Built-in STMMAC and OH Ethernet service; default DHCP for discovered eth interfaces | Link and DHCP validation |
| AIC8800 Wi-Fi | BSP/fullmac modules, firmware, cfg80211, WLAN/WPA/hostapd HDF services | Scan, association, regulatory behavior and AP validation |
| USB serial | CH341, CP210x, FTDI and PL2303 modules; serial DDK HDF service | Enumeration, DDK app permission and I/O validation |
| SPI | spidev module; board DT pinmux retained | Only DT-declared devices can bind; app-facing access policy |
| CAN | SocketCAN raw/BCM, M_CAN, TCAN4x5x and gs_usb modules | Physical bus validation and app integration |
| USB camera | UVC kernel module; USB camera peripheral/interface components and common V4L2 provider selected | HDF camera host config packaging, `/dev/video*` policy and stream validation |
| ES8326 audio | Kernel modules, ALSA hooks, Audio HDI and 48 kHz stereo policy | Real playback/capture, mixer routing, mute/gain and jack detection |
| WS73 USB NearLink | Complete local SDK snapshot, pinned SSAP library, four SHA256-pinned firmware blobs and node permissions | Linux 6.1 API port, kernel module build, SLE service/HDI and Wi-Fi PM work |
| Bluetooth | HDF Bluetooth interface selected; AIC firmware assets present; explicit `bringup/rdkhm-bluetooth-init.sh` probe/attach entrypoint | X5 UART path/baud and vendor initialization, Bluetooth HDI and controller validation |
| CSI camera | Existing vendor kernel baseline retained | Camera SDK/HDI and selected sensor configuration |
| GPU | galcore and private glibc EGL/GLES runtime; offscreen probe | Hardware validation, OH native-window/buffer integration |
| BPU | Framework, governor, cores, vendor hardware-I/O object; private DNN runtime; model tensor descriptor probe | Runtime ABI validation, model execution, NNRT backend |
| Video acceleration | Codec HDI v1 and OMX extension components selected | X5 VPU userspace ABI, codec HCS capabilities and decode/encode validation |

CAN interfaces are not brought up, assigned a bitrate, or sent traffic by this port.
No pinmux overlays or external peripheral wiring are assumed.

## Module bundle

```sh
JOBS=64 bash scripts/build-kernel.sh modules
python3 scripts/import-driver-firmware.py
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
python3 scripts/prepare-driver-bundle.py
bash scripts/build-bringup-userspace.sh
JOBS=64 bash scripts/build-openharmony.sh --build-target images
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

`config/driver-modules.json` selects modules. The preparer resolves dependencies,
checks vermagic, and runs depmod against the built kernel's System.map.
It explicitly selects the target kernel release for modinfo; otherwise kmod can
return host built-in metadata for an identically named module such as rfkill.

The bundle contains 27 modules, their metadata, and 21 firmware/configuration files,
including `/vendor/etc/firmware/ws73/{ws73,wifi_cali,btc_cali,wow}.bin`.
It also carries the private accelerator runtime described in `accelerators.md`.
`config/firmware-lock.json` pins the copied BSP assets and the host's signed regulatory database.
`sources/driver-firmware` holds the captured bytes. Reimport rejects changed hashes.
The source BSP is read-only. The bytes retain upstream licensing.

The SD packer injects the bundle into vendor ext4, preserving existing OH metadata.
`/vendor/etc/rdkhm-drivers.json` records file hashes, kernel hash and source provenance.
The bootstrap mounts vendor, sets the kernel firmware search path, and loads modules
in dependency order before OpenHarmony init. Failures are reported to the serial
console; boot continues for diagnosis. No automatic module unloading occurs.

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
