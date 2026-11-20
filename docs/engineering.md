# Integration workflow

The integration repository owns product overlays, patches, dependency locks,
build orchestration, diagnostics, and tests. `sources/` and `out/` are disposable
workspace directories and may also be symlinks to larger disks. Upstream kernel
and OpenHarmony build systems remain responsible for compilation.

## Entry point

Run commands from the repository root; `python3 rdkhm` also works without an
executable file mode. No command below flashes a disk or connects to a board.

```sh
./rdkhm doctor
./rdkhm check
./rdkhm plan all
./rdkhm run all
```

`all` fetches and synchronizes sources before preparing and building them.
`build` uses existing checkouts, then prepares, builds, packages, and verifies.
`package` assembles and verifies existing build outputs; it does not rebuild them.
Individual stages are `fetch`, `prepare`, `kernel`, `userspace`, `drivers`,
`image`, and `verify`. Individual stages require their earlier inputs to exist.
The ordered commands are declared in `config/build/pipeline.json`.

`plan` is read-only and shows exact commands. `doctor` checks host tools and
external input availability, including the WS73 archive hash. It is a preflight,
not proof that every upstream build prerequisite is satisfied. `check` validates
shell syntax, JSON, bring-up artifact presence/injection and orchestration
regression tests; it is not a hardware test.
`run all` and `run build` require a successful doctor check. The wrapper serializes
build runs with a workspace lock. Legacy scripts remain available, but bypass
that lock and the per-run evidence; do not run them concurrently with the wrapper.

## Fast incremental builds

Do not rebuild the full `images` target for every source change. Build the
affected ninja target, then assemble/verify only when a flashable artifact is
actually needed:

```sh
# one component/library
JOBS=64 bash scripts/build-target.sh \
    drivers/peripheral/display/composer/vdi_base:display_composer_vdi_impl_default

# init/HDF/sepolicy/overlay changes -> vendor image only
JOBS=64 bash scripts/build-target.sh vendor_image

# full image is only for flashing/acceptance
JOBS=64 bash scripts/build-openharmony.sh --build-target images
```

`--build-target images` skips the SDK API installation step. When rebuilding
system apps, run `bash scripts/install-system-sdk-api.sh` first (or use
`./build oh`, which builds the SDK API and installs it); otherwise
`compile_app.py` fails on system APIs such as `sendData` or
`getPermissionFlags`.

For fastboot-based incremental updates, prepare only the partition that changed.
Assembly still performs the RDKHM injections (boot files, driver bundle,
kernel-matched firmware); it only skips CONFIG/MBR/whole-disk assembly:

```sh
# vendor-only iteration (~250 MiB sparse)
JOBS=64 bash scripts/build-target.sh vendor_image
bash scripts/make-openharmony-image.sh --partitions-only --only vendor

# system-only iteration (~1.4 GiB sparse)
JOBS=64 bash scripts/build-target.sh system_image
bash scripts/make-openharmony-image.sh --partitions-only --only system
```

Outputs land in `out/fastboot/`: `<name>.img`, optional `<name>.simg`,
`partitions.json`, and `fastboot-uboot.cmd` containing the
`fastboot_raw_partition_*` LBA lines for the U-Boot console. Assembled partitions
from separate runs are kept, so system and vendor can be regenerated
independently. `--no-sparse` skips the `.simg` copies.
See [fastboot-flashing.md](fastboot-flashing.md) for the U-Boot console setup,
host commands, verification values and troubleshooting.

The Armbian-style wrapper groups the common batches:

```sh
./build kernel
./build oh
./build hap settings
./build image
```

Patch application is manifest-driven: `config/patches.json` plus
`scripts/apply-patches.py`; `prepare-kernel.sh` and `prepare-openharmony.sh` no
longer contain per-patch lists. Applied state is recorded under
`out/patches-state/` so stacked patches are not re-applied.

Canonical paths come from `env.sh` (`RDKHM_OH_TREE`, `RDKHM_KERNEL_TREE`,
`RDKHM_HDC`, `RDKHM_COMMAND_LINE_TOOLS`, ...), so scripts do not hardcode
`sources/oh/openharmony-full` or the SDK toolchain path. `sources/` contains
only `oh/`, `rdk/` and `deps/`; generated driver firmware lives under
`out/driver-firmware`.

`scripts/build-target.sh` calls the same upstream `build.py`/ninja path as the
full build, so incremental objects are reused. `./rdkhm check` is seconds;
`verify-openharmony-image.py` and `run package` are the slow image-wide steps.
For a controlled board test without flashing, `scripts/deploy-composer-fix.sh`
defaults to dry-run; `--apply` requires serial access.
The last assembled image is `out/images/rdkhm-x5-openharmony-dev.img` plus its
`.img.sha256`; it is not rebuilt by a component-only build.

## Component batches

`config/build/components.json` declares each component's build commands, package
artifacts, remote paths and service restarts. The CLI keeps the same lock and
evidence rules as the full pipeline:

```sh
./rdkhm components                 # list components and deploy kind
./rdkhm build display              # run only that component's build steps
./rdkhm package display            # copy artifacts to out/stage/display/
./rdkhm deploy display <ip:port>   # dry-run: print target paths and hashes
./rdkhm deploy display <ip:port> --apply
```

`package` writes `out/stage/<component>/manifest.json` with the source path,
remote path, size and SHA-256 of every artifact. `deploy` re-verifies the staged
hashes, and with `--apply` backs up the board copies under
`/data/rdkhm-fixes/<component>-<timestamp>/original`, installs through
temporary names followed by an atomic rename, verifies the remote checksum, remounts read-only and
restarts the declared services. A failed deploy restores the backups.
Components whose hot-deploy path is not verified (`kernel`, `input`, `settings`,
`accelerators`, `image`) are marked `kind: image` and refuse `--apply`; they must
go through image assembly and flashing.

## Machine settings and external inputs

Create `config/workspace.local.json` using `config/workspace.example.json`.
The current machine is already configured. This file is ignored by Git and
excluded from code archives. Environment variables override local settings.
Relative input paths resolve against the workspace, not the caller's directory.

Provide these inputs on a new machine:

- An Arm GNU 11.2 compiler prefix through `CROSS_COMPILE`.
- The reference BSP through `RDKHM_BSP`, containing AIC firmware and the pinned
  WS73 archive. `RDKHM_WS73_ARCHIVE` can override the archive path separately.
- The NearLink reference Git repository through `RDKHM_NEARLINK_REFERENCE`, with
  commit `bcbd3ecf5bc407a2bd44e9dd5187c054124e9d79` available for SSAP extraction.
- Regulatory database files through `RDKHM_REGDB` matching `config/kernel/firmware-lock.json`.
- Host GCC 11, the AArch64 GNU userspace compiler/runtime, and the tools checked
  by doctor. OH prebuilts are prepared by the existing upstream setup.

Normal builds enforce firmware and accelerator library hashes without rewriting
locks. The accelerator glibc runtime currently comes partly from the host's
`/usr/aarch64-linux-gnu/lib`; a different package version fails the hash check.
Lock provenance records workspace-relative source paths; inputs resolve through
`config/workspace.local.json` or environment overrides, never through stored
absolute paths. Host toolchain libraries stay absolute because they come from
the pinned host compiler. SDK and firmware redistribution rights
remain upstream; code archives do not redistribute those external inputs.

## Evidence and migration

Every wrapper run gets `out/runs/<UTC timestamp>-<unique suffix>/` containing:

- `snapshot.json`: integration file hashes/modes, source revisions/status,
  selected settings and compiler versions.
- `integration.tar.gz`: the exact integration files captured before execution,
  excluding local settings, generated SSAP links, downloaded sources and outputs.
- `host-packages.tsv` and the existing resolved OH manifest, when available.
- `openharmony-source-state.json` and `source-diffs/`: every OH project revision,
  working-tree status and binary-capable tracked-file diffs at capture time.
- Separate stage logs and `run.json` with command order, exit status and failure.
- `after/`: a second snapshot after a successful run. Successful image builds
  also record the image hash and size in `run.json`.

The image verifier compares every packaged bring-up diagnostic against its
source copy, including the hardware status report, camera/codec report and
WS73/Bluetooth probes. It also runs the access-token ioctl ABI check and
confirms the composer service release exports. This catches an image assembled
from an incomplete working tree before it reaches a board.

Use `./rdkhm snapshot` to preserve a development baseline without building.
Extract its integration archive into a new directory, provide local settings
and external inputs, then run doctor/check/plan/all. Generated links are recreated
by preparation scripts. For an incremental move, rebuild rather than carrying
compiled output trees containing absolute paths.

These records are an integration baseline, not a signed release or a substitute
for Git review. An existing image is never retroactively attributed to a new
snapshot. A package-only run explicitly records that it used existing build
outputs. Untracked/ignored upstream file contents are not archived. Bit-identical
rebuilds are not yet guaranteed: filesystem UUIDs, timestamps and host tools
still need isolation. Board validation is always recorded separately.

## Next engineering gates

- Maintain reviewed Git commits and release tags after the initial local baseline;
  remote publication is separate from local integration work.
- Reconcile the captured OH subproject changes against the maintained patch set;
  `config/sources/openharmony.lock.xml` already pins every project revision used by sync.
- Supply a pinned host toolchain/container and an external dependency cache.
- Run a complete build in a fresh workspace and compare its installed contents.
- Make image UUIDs/timestamps deterministic before claiming byte reproducibility.
- Add CI for the same entry point and a separate board acceptance job.

Hardware work is tracked in [backlog.md](backlog.md).
