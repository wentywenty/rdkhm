# Image build preparation

Status: system/vendor partition build executed on 2026-11-19; a later full SD
image (`db0a75bb...`) was built and passed the verifier, but was not flashed.
See [image-build-prep-20261119.md](image-build-prep-20261119.md).
Current patch/HAP preflight is tracked in
[image-build-prep-20261119.md](image-build-prep-20261119.md); launcher clean-apply
and HAP injection have been prepared. A build still requires explicit approval.

## Readiness snapshot

- `./rdkhm doctor`: `Host preflight: 0 failure(s)`.
- `./rdkhm plan image`: `bash scripts/make-openharmony-image.sh`.
- Image inputs present:
  - `sources/oh/openharmony-full/out/rdk_x5/packages/phone/images/system.img`
  - `sources/oh/openharmony-full/out/rdk_x5/packages/phone/images/vendor.img`
  - `sources/oh/openharmony-full/out/rdk_x5/packages/phone/images/userdata.img`
  - `out/kernel/obj/arch/arm64/boot/Image`
  - `out/driver-bundle/lib/modules/6.1.83-rdkhm/`
  - `out/bringup-bin/`
  - 全部镜像 HAP：`python3 scripts/image_haps.py --check`（25 个条目，含
    Settings、SystemUI 模块、ScreenLock、contacts/mms 等）
- `haps` stage：构建 `image.apps` 的 17 个 app、SystemUI modules 和 PinTool；
  `image_haps.py --check` 是镜像组装前的硬门禁
- Patch hygiene: `check-patch-format.py` and `check-patch-coverage.py` pass; no orphan patch files.

## Commands

Assemble and verify from existing outputs only:

```sh
./rdkhm run package
```

Prepare, build, assemble and verify from existing source checkouts:

```sh
./rdkhm run build
```

Sync sources first, then prepare/build/package/verify:

```sh
./rdkhm run all
```

Assemble the image without rebuilding components:

```sh
./rdkhm run image
```

Read-only inspection first:

```sh
./rdkhm plan all
./rdkhm plan image
```

## Outputs

- `out/images/rdkhm-x5-openharmony-dev.img`
- `out/images/rdkhm-x5-openharmony-dev.img.sha256`
- Per-run evidence under `out/runs/<timestamp>/`
- Image verification log under the same run directory

## Before the first full build

1. Working-tree changes for launcher/screenlock/settings are captured in
   `launcher/0004`, `screenlock/0003` and `settings/0004`; see
   [image-build-prep-20261119.md](image-build-prep-20261119.md).
2. Re-run `./rdkhm check`.
3. Confirm `python3 scripts/image_haps.py --check` passes; a missing required
   HAP now aborts image assembly instead of keeping the stale prebuilt.
4. Confirm `./rdkhm doctor` still reports zero failures.
5. Confirm the disk behind `out/` has enough free space for another image.
6. Keep the previous image and its `.sha256` so a failed build can be rolled back.

## Known board notes (do not treat as image-build blockers)

- App icon bitmaps on the Launcher are still blank; labels and app launch work.
- HDMI display rotation stays at 800x480; `FreezeFlag` remains set at the display layer.
- Launcher and the auto-unlock ScreenLock HAP are now injected from
  `out/haps` like every other built app; board-side experiments and the image
  now share one manifest.
- `powermgr` is stopped on the running board to avoid suspend/HDC loss.
  2026-11-19 image preparation adds a boot service `rdkhm-powermgr-off` to stop it
  automatically; cold-boot behavior is not yet tested.

## Do not

- Do not flash or reboot the board as part of preparation.
- Do not run `./rdkhm run all/build/package/image` until the build is explicitly approved.
