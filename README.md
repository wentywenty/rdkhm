# RDK X5 OpenHarmony port

Experimental port of OpenHarmony standard system onto the D-Robotics X5
Linux BSP. Initial scope: boot, HDMI, USB input, HDC, and an ArkUI app.
GPU/BPU driver and isolated-runtime integration is in progress; see
[accelerators.md](docs/accelerators.md). Camera preview is in bring-up; hardware
video codecs are deferred.

## Integration entry point

```sh
./rdkhm doctor
./rdkhm check
./rdkhm plan all
./rdkhm run all
```

Machine settings live in the ignored `config/workspace.local.json`, following
`config/workspace.example.json`. Environment variables override local settings.
The current machine is configured. See [engineering.md](docs/engineering.md) for
migration, prerequisites, dependency ownership, build profiles and evidence.
`all` includes source fetching; `build` starts from existing checkouts; `package`
only assembles and verifies existing outputs. Individual stages are also supported.
`plan` is read-only. No wrapper command flashes hardware or connects to a board.

An Armbian-style entry point is available for the common batches:

```sh
./build list
./build kernel
./build oh
./build hap settings
./build image
```

`./build oh` builds the SDK API and installs the source-generated system SDK
declarations before the image build. A direct
`build-openharmony.sh --build-target images` requires
`bash scripts/install-system-sdk-api.sh` first.

Component-scoped work does not assemble a full image:

```sh
./rdkhm components
./rdkhm build display                          # only that component's build steps
./rdkhm package display                        # stage artifacts under out/stage/display
./rdkhm deploy display <target:port>           # dry-run plan
./rdkhm deploy display <target:port> --apply --serial-confirmed
```

Build commands, artifacts, remote paths and service restarts are declared in
`config/build/components.json`. `deploy` is dry-run by default, never flashes a disk,
and refuses components whose hot-deploy path has not been verified. Components
marked `serial_required` reject `--apply` unless `--serial-confirmed` is also
given; that flag records operator confirmation of serial access, not detection.

## Patch management

All patches are listed in `config/patches.json`; `scripts/apply-patches.py` is
the single applier used by `prepare-kernel.sh` and `prepare-openharmony.sh`:

```sh
python3 scripts/apply-patches.py --dry-run
python3 scripts/apply-patches.py --only kernel
```

Applied state is recorded under `out/patches-state/`, so stacked patches are not
re-applied and `scripts/check-patch-coverage.py` rejects orphan patch files.

### Kernel profiles

`RDKHM_KERNEL_PROFILE` selects the kernel configuration. The default is the
vendor non-RT config; the RT profile is opt-in:

| Profile | Defconfig | Extra patch |
| --- | --- | --- |
| `default` (default) | `hobot_x5_rdk_ubuntu_defconfig` | none |
| `rt` | `config/kernel/hobot_x5_rdk_ubuntu_rt_defconfig` | `patches/optional/preempt-rt/patch-6.1.83-rt28.patch` |

```sh
RDKHM_KERNEL_PROFILE=rt ./rdkhm run build
```

`prepare-kernel.sh` applies the optional RT patch for the `rt` profile and
reverse-applies it when switching back to `default`. The RT profile has not
been board-validated; passing `./rdkhm check` only proves the configuration is
wired, not that the resulting kernel is real-time on hardware.

## Applications (HAPs)

System apps are HAPs, not APKs. Default images use the prebuilt HAPs under
`applications/standard/hap/` (Launcher, SystemUI, Settings, ...), installed by
upstream `ohos_prebuilt_etc` rules. Source changes under
`applications/standard/<app>` do not reach the image unless that app is rebuilt
and injected.

Settings is rebuilt from source and injected at image assembly:

```sh
./build hap settings
./rdkhm package settings
```

`config/build/haps.json` lists the apps; entries marked `verified: false` require
`--force` because their SDK/product configuration has not been validated.
`./build hap --all --force --jobs N` builds the registered HAPs in parallel
(default is serial). `scripts/build-hap.py` writes `out/haps/<app>.hap` and, for Settings, also stages
`out/settings/Settings.hap`. All rebuilt HAPs are signed with the official
OpenHarmony release key; see [hap-signing.md](docs/hap-signing.md). `--no-sign`
is debugging-only and must not be used for an image. The `haps` stage in
`config/build/pipeline.json` builds every app in the image manifest, SystemUI
modules and PinTool, so `./rdkhm run build` no longer relies on stale `out/haps`
artifacts.

PinTool is a first-party HAP under `apps/rdkhm-pintool`; it is not part of the
OpenHarmony manifest:

```sh
./rdkhm build pintool
./rdkhm package pintool
```

`scripts/build-pintool-hap.sh` builds the ArkTS UI plus a small NAPI bridge and
signs the HAP with the pinned OpenHarmony keys. Image assembly injects
`out/haps/rdkhm_pintool.hap` when present, in addition to the optional Settings
HAP. The app talks to `/rdkhm/gpio-daemon` on `127.0.0.1:9800`; the daemon is
started by `init.rdk_x5.cfg` and exposes the 40-pin map under `/rdkhm`.
HAP signing reads `RDKHM_HAP_KEY_ALIAS`, `RDKHM_HAP_KEY_PWD`,
`RDKHM_HAP_STORE_PWD` and optionally `RDKHM_HAP_SIGN_TOOL`; no key material or
password defaults are compiled into the scripts. Use `--no-sign` to keep a HAP
unsigned.

## Toolchain and environment

`env.sh` exports canonical paths; scripts source it instead of hardcoding
directories. Values come from `config/workspace.local.json` and can be
overridden by environment variables:

| Variable | Default |
| --- | --- |
| `RDKHM_TOOLS_DIR` | `thirdparty` |
| `RDKHM_COMMAND_LINE_TOOLS` | `thirdparty/toolchains/command-line-tools-26` |
| `RDKHM_OH_TREE` | `sources/oh/openharmony-full` |
| `RDKHM_OH_DEPS_TREE` | `sources/oh/openharmony` |
| `RDKHM_KERNEL_TREE` | `sources/rdk/x5-kernel` |
| `RDKHM_OH_SDK` | `$RDKHM_OH_TREE/prebuilts/ohos-sdk/linux/20` |
| `RDKHM_HDC` | `$RDKHM_OH_SDK/toolchains/hdc` |
| `RDKHM_CACHE_DIR` | `thirdparty/downloads` |
| `RDKHM_WS73_ARCHIVE` | `$RDKHM_CACHE_DIR/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz` |
| `CROSS_COMPILE` | `thirdparty/toolchains/gcc-arm-11.2/bin/aarch64-none-linux-gnu-` |

`sources/` contains only three categories: `oh/` (OpenHarmony components),
`rdk/` (D-Robotics kernel, BSP and wireless) and `deps/` (extracted source
dependencies such as busybox). Toolchains and prebuilt caches live in
`thirdparty/toolchains`; downloaded archives live in `thirdparty/downloads`;
generated driver firmware lives under `out/driver-firmware`.

Every run writes separate logs, code archives, input snapshots and command results
under `out/runs/`. `./rdkhm snapshot` captures a baseline without building. Existing
images are never retroactively attributed to that snapshot. Hardware work is
temporarily deferred in [backlog.md](docs/backlog.md).

The complete-system development artifact is
`out/images/rdkhm-x5-openharmony-dev.img` (7172 MiB), with system services,
Launcher/SystemUI and a software-rendering integration. Earlier iterations have
booted on X5 and produced HDMI output; the latest fixes require cold-boot acceptance.
The current checkpoint is recorded in [STATUS.md](STATUS.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `build` | Unified build entry point (`kernel`, `oh`, `hap`, `image`, ...) |
| `env.sh` | Shared environment and path resolution |
| `config/` | Pipeline, components, patch manifest, HAP registry and locks |
| `scripts/` | Sync, prepare, build, package, verify and deploy entry points |
| `patches/` | Minimal OpenHarmony and X5 kernel patch set |
| `overlay/` | X5 product init, HDF, SELinux and file labels |
| `bringup/` | On-device diagnostics and controlled init helpers |
| `apps/` | First-party OpenHarmony applications (`rdkhm-pintool`) |
| `tests/` | Offline host-side tests |
| `docs/` | Architecture, driver, debugging and handoff records |
| `sources/` | Upstream checkouts: `oh/`, `rdk/`, `deps/` (ignored, disposable) |
| `out/` | Build outputs, images and evidence (ignored, disposable) |
| `thirdparty/` | Local toolchains and downloaded archives (ignored) |

All paths above except `sources/`, `out/` and `thirdparty/` are tracked.
Those three may be ordinary directories or links to a larger disk; they are
never part of the integration commit boundary and can be rebuilt or re-fetched.

## Handoff and debug records

- [Documentation index](docs/README.md)
- [Debug history and pitfalls](docs/debug-history.md)
- [Board login and HDC](docs/board-access.md)
- [Fastboot partition flashing](docs/fastboot-flashing.md)
- [Engineering handoff](docs/handoff.md)
- [Latest board validation (2026-11-19)](docs/board-validation-20261119.md)
- [Note local persistence validation (2026-11-19)](docs/board-validation-20261119-note.md)
- [galcore DMA-BUF panic fix (2026-11-20)](docs/galcore-dmabuf-errptr-20261120.md)
- [Account foreground fallback (2026-11-20)](docs/account-foreground-fallback-20261120.md)
- [Earlier board validation (2026-11-17)](docs/board-validation-20261117.md)
- [X5 NNRT backend integration](docs/nnrt-backend.md)
- [X5 model conversion](docs/model-conversion.md)
- [HAP build task breakdown](docs/hap-tasks.md)
- [Patch inventory](docs/patches.md)
- [Image build preparation](docs/image-build.md)
- [QEMU validation plan](docs/qemu-validation.md)
- [40-pin GPIO and PinTool](docs/gpio.md)

## Storage

- Entry point and integration files: the directory containing this README.
- `sources` and `out` may be ordinary directories or links to a larger disk.
- Local-only large inputs (command-line tools, reference trees, component working
  copies, download archives) live under the ignored `thirdparty/` directory.
- Existing BSPs outside this workspace are read-only references.
- Board access is confined to explicit development/deployment scripts.

## Baselines

- X5: https://github.com/D-Robotics/x5-kernel
  `b2edb450c6eaef1c7277885d49f74efb6088b634`, Linux 6.1.83.
- OpenHarmony: `OpenHarmony-v6.0-Release` tag.
- Manifest: https://gitcode.com/openharmony/manifest.git
  `d6a0fef04cd19e2ecf0ea978e683e5d2f7953198`.
- Non-OpenHarmony upstreams (X5 kernel, camsys, x5-hobot-*, manifest repo) are
  a `repo` workspace defined by `config/sources/repo.xml`.
- The OpenHarmony tree is a separate `repo` workspace pinned by
  `config/sources/openharmony.lock.xml`.
- Compiler: Arm GNU 11.2, existing installation under `/opt`.

The OH release is a deliberate initial baseline, not a claim that it is the
newest release. Its 5.10/6.6 kernel adaptations must be ported to X5's 6.1.

## Kernel build

```sh
bash scripts/prepare-kernel.sh
bash scripts/build-kernel.sh configure
bash scripts/build-kernel.sh Image
bash scripts/build-kernel.sh dtbs
```

The Image is under `out/kernel/obj/arch/arm64/boot/`; logs are in `out/logs/`.
The nested object directory contains HDF's relative output paths within `out/`.
`CROSS_COMPILE` and `JOBS` can be overridden.
The configuration starts from the vendor defconfig; the build verifies that
every requested enabled/disabled setting survives Kconfig dependency resolution.
The initial patches integrate Ashmem, AccessToken, Binder token propagation and
HDF core. They are NOT a complete OpenHarmony kernel qualification; see
`docs/kernel-port.md` for the remaining ABI and runtime checks.

## OpenHarmony userspace

```sh
bash scripts/sync-openharmony.sh
bash scripts/prepare-openharmony.sh
bash scripts/prepare-sdk.sh
bash scripts/build-openharmony.sh
JOBS=64 bash scripts/build-kernel.sh modules
bash scripts/build-bringup-userspace.sh
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/import-driver-firmware.py
python3 scripts/prepare-driver-bundle.py
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

The kernel `Image`/DTBs and `out/bringup-bin/busybox` built by the kernel section
are required inputs for the image step.
The full standard-system source tree is `sources/oh/openharmony-full`; the smaller
`sources/oh/openharmony` tree remains the pinned kernel/HDF dependency checkout.
The resolved full manifest is recorded in `out/openharmony-resolved.xml`.
The prepare script applies the Node dependency fix and runs upstream prebuilts
setup. Local setup issues and their
fixes are recorded in [userspace status](docs/userspace.md).
`rdk_x5` is the ARM64 standard-system target under development. Its configuration
includes application and graphics components. The full `images` target builds;
X5 display/input and Launcher/application execution still need hardware validation.
Driver coverage and rebuild instructions are in [drivers.md](docs/drivers.md).
ES8326 Audio HDI/ALSA integration and offline tests are included. The USB WS73
NearLink preparation and pending runtime validation are tracked in [nearlink.md](docs/nearlink.md).

## Milestones

1. X5 kernel with initial OH IPC, memory, security and HDF adaptations: built.
2. SD bring-up layout and ABI probes: built and inspected offline.
3. ARM64 OpenHarmony system/vendor/data images and SD assembly: built.
4. Display buffer/composer, evdev input and HDC: integrated; HDMI observed on X5.
5. Complete desktop, touch and ArkUI HAP acceptance: pending.

Neither successful compilation nor a reference board image proves X5 runtime
support. See STATUS.md for dated board evidence. The bring-up SD image requires existing X5 QSPI
firmware; it does not contain or update that firmware.
