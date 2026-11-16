# RDK X5 OpenHarmony port

Experimental port of OpenHarmony standard system onto the D-Robotics X5
Linux BSP. Initial scope: boot, HDMI, USB input, HDC, and an ArkUI app.
GPU/BPU driver and isolated-runtime integration is in progress; see
[accelerators.md](docs/accelerators.md). Camera and hardware video codecs are deferred.

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

Every run writes separate logs, code archives, input snapshots and command results
under `out/runs/`. `./rdkhm snapshot` captures a baseline without building. Existing
images are never retroactively attributed to that snapshot. Hardware work is
temporarily deferred in [backlog.md](docs/backlog.md).

The complete-system development artifact is
`out/images/rdkhm-x5-openharmony-dev.img` (7172 MiB), with system services,
Launcher/SystemUI and a software-rendering integration. Earlier iterations have
booted on X5 and produced HDMI output; the latest fixes require cold-boot acceptance.
The older `rdkhm-x5-bringup-0.1.img` is only a kernel/shell checkpoint.
The current checkpoint is recorded in [STATUS.md](STATUS.md).

## Storage

- Entry point and integration files: the directory containing this README.
- `sources` and `out` may be ordinary directories or links to a larger disk.
- Existing BSPs outside this workspace are read-only references.
- Board access is confined to explicit development/deployment scripts.

## Baselines

- X5: https://github.com/D-Robotics/x5-kernel
  `b2edb450c6eaef1c7277885d49f74efb6088b634`, Linux 6.1.83.
- OpenHarmony: `OpenHarmony-v6.0-Release` tag.
- Manifest: https://gitcode.com/openharmony/manifest.git
  `d6a0fef04cd19e2ecf0ea978e683e5d2f7953198`.
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

## SD bring-up image

```sh
bash scripts/build-bringup-userspace.sh
bash scripts/make-bringup-image.sh
python3 scripts/verify-bringup-image.py
```

Image construction uses regular files, fakeroot, and mke2fs; it does not mount
filesystems, allocate loop devices, or write a physical disk. Rebuilds are
scriptable but not bit-for-bit reproducible (timestamps and filesystem UUIDs).

## OpenHarmony userspace

```sh
bash scripts/sync-openharmony.sh
bash scripts/prepare-openharmony.sh
bash scripts/prepare-sdk.sh
bash scripts/build-openharmony.sh
JOBS=64 bash scripts/build-kernel.sh modules
python3 scripts/prepare-accelerators.py
bash scripts/build-accelerator-modules.sh
bash scripts/build-nearlink.sh
python3 scripts/import-driver-firmware.py
python3 scripts/prepare-driver-bundle.py
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```

The full standard-system source tree is `sources/openharmony-full`; the smaller
`sources/openharmony` tree remains the pinned kernel/HDF dependency checkout.
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
