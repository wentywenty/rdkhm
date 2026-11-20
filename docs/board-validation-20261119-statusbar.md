# SystemUI status bar validation - 2026-11-19

This record covers the missing top status bar and navigation bar. The fix was
hot-installed and verified on the board; the assembled image containing the
same HAPs has not been flashed or cold-boot tested.

## Board state during hot install

- Target: `10.43.9.213:5555`
- boot_id: `00836ef8-c49c-4a6e-8c58-a0bf1da68998`
- Kernel: `6.1.83-rdkhm #5` (built 2026-11-19 16:13:39 CST)
- The board was already running the 2026-11-19 development image; the exact
  board-side image SHA256 was not read back. The after-fix image
  `883c81231de78fd43fd2675983605f7d403b4801593693bab38118c99f3e04fd`
  was assembled later and is **not** the image under test here.
- SystemUI update: `com.ohos.systemui`, installed under
  `/data/app/el1/bundle/public/com.ohos.systemui`.

## Root cause

SystemUI status and navigation bars are service extensions in the same
`com.ohos.systemui` process. Their configuration reads resource strings through
`ResourceUtil`. The asynchronous `resourceManager.getString()` did not complete
in this service-extension context, so both configurations stopped after logging
`direction is 1` and never called `createWindow`.

Two changes fixed it:

1. `StatusBarConfiguration.ts` and `NavBarConfiguration.ts` use their own
   `ResourceUtil` instances instead of the shared default singleton.
2. `ResourceUtil.getString()` uses `getStringSync()`; missing context or
   resource-manager state is logged.

Patch: `patches/haps/systemui-resource-manager.patch`
SHA256: `9e55b5643a8a1c0e871ebca408813e901c9848979128fa1ba2455ce5ebe8b9fc`

The patch is listed in `config/patches.json`; `scripts/check-patch-format.py`
reports 0 failures and `scripts/check-patch-coverage.py` reports PASS (89
patches).

## HAPs built and installed

`./build hap systemui` produced and signed these HAPs under
`out/haps/systemui/`:

| Image file | SHA256 |
| --- | --- |
| `SystemUI.hap` | `9e984843492701ab56354d098f1da503474fd1d97d571e4de7397f34e95247ca` |
| `SystemUI-StatusBar.hap` | `b0d3e68a3af95bf4079e8195c0ca01d8f37ed4a3c0dd99f9aa4f4c7381637431` |
| `SystemUI-NavigationBar.hap` | `16b2468e8964ea7fa1f288bff452febcfb0c4cbe8392415d47db341e0b17aa7a` |
| `SystemUI-DropdownPanel.hap` | `5530a7320de4e9cc8a7db105a32b3de80340c3f7256533ac3d9cbced0753db42` |
| `SystemUI-NotificationManagement.hap` | `9c5370bb150994c3a79ad543c80f0db92b4ac0acb6a1b5485524fd3cb3626615` |
| `SystemUI-VolumePanel.hap` | `32f8f63f0511293b82e9aae6c42a722db4fff3c2ec4824da4ee2353dacea53c6` |
| `SystemUI-SystemDialog.hap` | `6135751b84eddbceb72703542afb349e7100a00d7002174d4c4800c98edb9d7f` |
| `SystemUI-ScreenLock.hap` | `54d537e6cc9eea5bddbfba7b98370b766c88a9edd404c758a59a323e51d5e27f` |

All eight were installed with:

```sh
bm install -r -p /data/local/tmp/systemui-install
```

The hashes read back from `/data/app/el1/bundle/public/com.ohos.systemui/*.hap`
match the host artifacts exactly. Raw evidence:
`out/evidence/20261119-systemui-statusbar/comparison.txt`.

## Runtime evidence

WindowManager (`hidumper -s 4606 -a -a`) reports:

```text
SystemUi_StatusBar    [0, 0, 800, 45]
SystemUi_NavigationB  [0, 432, 800, 48]
SystemUi_PrivacyIndi  [0, 0, 800, 32]
```

StatusBar/NavigationBar logs confirm:

```text
NavigationBar_ServiceExtAbility --> onCreate, createWindow success.
StatusBarConfiguration --> direction = 1 statusbarPosition = 2 shortSideLength = 36
StatusBarConfiguration --> initWindowManager ... realWidth 800 realHeight 36
```

Screenshot: `out/board-logs/statusbar.jpeg` (also copied into the evidence
directory). It shows the top bar with the "no SIM card" indicator, battery and
time.

## Assembled image (not flashed)

`out/images/rdkhm-x5-openharmony-dev.img`

- SHA256: `883c81231de78fd43fd2675983605f7d403b4801593693bab38118c99f3e04fd`
- `scripts/verify-openharmony-image.py`: `PASS: MBR, checksum, four filesystems
  and 198 packaged artifact comparisons`
- The eight SystemUI HAPs and the Settings HAP extracted from the image match
  the host artifacts byte-for-byte; see the evidence directory.

## Not validated

- Cold boot of `883c...`; the board result above is a hot HAP update.
- Status bar after reboot, lock-screen interaction, and navigation gestures.
- HDMI/input/HDC/service qualification for the assembled image.

## Reproduce

```sh
./build hap systemui
./build image
python3 scripts/verify-openharmony-image.py
```

Evidence directory: `out/evidence/20261119-systemui-statusbar/`
