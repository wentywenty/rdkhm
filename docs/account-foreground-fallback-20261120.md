# Account foreground fallback - 2026-11-20

This record covers the BMS/Launcher failure where `bm` reported the current
user as `-2` and `aa start com.ohos.launcher` failed even though the account and
storage services were running.

## Symptom

```text
AccountMgr: service ptr is null!
BMS: GetForegroundOsAccountLocalId failed ret:4194341
bm install ... -u 100
code:301 user not exist.

aa start -b com.ohos.launcher -a com.ohos.launcher.MainAbility
10104001 The specified ability does not exist
```

StorageDaemon and the account activation were otherwise successful:

```text
StartUser: start user 100
StartUser: delay time = 184 ms.
PrepareStartUser end, errCode 0
```

Note could start with `-U 100`, so userspace and storage were functional.

## Cause

`SendToAMSAccountStart()` inserts the foreground user in an AMS completion
callback. On this image that callback did not complete, leaving
`foregroundAccountMap_` empty. BMS therefore had no current user and could not
install or resolve Launcher.

## Fix

Patch: `patches/account/0002-foreground-fallback.patch`

SHA256: `cd8e88e65fc65e4a59f843eb19715716f7af13c2993fcccf56dab67fc7813c00`

`IInnerOsAccountManager::GetForegroundOsAccountLocalId()` now falls back to
the activated default account for display 0 when the foreground map is empty:

```cpp
if (displayId == Constants::DEFAULT_DISPALY_ID &&
    defaultActivatedId_ >= Constants::START_USER_ID) {
    localId = defaultActivatedId_;
    return ERR_OK;
}
```

The patch is listed in `config/patches.json`.

## Build and image

The account library target was rebuilt:

```text
sources/oh/openharmony-full/out/rdk_x5/account/os_account/libaccountmgr.z.so
SHA256 d3e4779f0a94ca60aa19cc882537dd9d8c5dd8512662295902cdbb6f97a7ed05
```

The full `system_image` target was blocked by unrelated HAP SDK errors, so the
new library was injected into the system partition and the SD image was
reassembled:

```text
out/images/rdkhm-x5-openharmony-dev.img
SHA256 5e60512e95bd5132be187339a54c5f3622649516b0b7c98948247a0893c70c7d
```

`scripts/verify-openharmony-image.py` passes:

```text
PASS: MBR, checksum, four filesystems and 224 packaged artifact comparisons
```

## Not validated

- The image has **not been flashed**.
- The account fallback has **not been tested on the board**.
- The image reuses the existing signed HAP set because the HAP rebuild was
  blocked by SDK API mismatches.
- The next board test must verify `bm` current user is 100, install/start
  Launcher, and check whether the desktop compositor presents a frame.
