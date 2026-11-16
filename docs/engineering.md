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
The ordered commands are declared in `config/pipeline.json`.

`plan` is read-only and shows exact commands. `doctor` checks host tools and
external input availability, including the WS73 archive hash. It is a preflight,
not proof that every upstream build prerequisite is satisfied. `check` validates
shell syntax, JSON, and orchestration regression tests; it is not a hardware test.
`run all` and `run build` require a successful doctor check. The wrapper serializes
build runs with a workspace lock. Legacy scripts remain available, but bypass
that lock and the per-run evidence; do not run them concurrently with the wrapper.

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
- Regulatory database files through `RDKHM_REGDB` matching `firmware-lock.json`.
- Host GCC 11, the AArch64 GNU userspace compiler/runtime, and the tools checked
  by doctor. OH prebuilts are prepared by the existing upstream setup.

Normal builds enforce firmware and accelerator library hashes without rewriting
locks. The accelerator glibc runtime currently comes partly from the host's
`/usr/aarch64-linux-gnu/lib`; a different package version fails the hash check.
Historical absolute paths in lock provenance are evidence of the original import,
not locations used to resolve inputs. SDK and firmware redistribution rights
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
  `config/openharmony.lock.xml` already pins every project revision used by sync.
- Supply a pinned host toolchain/container and an external dependency cache.
- Run a complete build in a fresh workspace and compare its installed contents.
- Make image UUIDs/timestamps deterministic before claiming byte reproducibility.
- Add CI for the same entry point and a separate board acceptance job.

Hardware work is tracked in [backlog.md](backlog.md).
