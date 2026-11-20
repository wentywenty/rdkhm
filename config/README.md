# Configuration control plane

`config/` is first-party integration state, grouped by domain. It is not
managed by `repo`; it *contains* the repo manifests.

```
config/
  build/          pipeline.json  components.json  haps.json
  sources/        repo.xml  openharmony.lock.xml
  kernel/         *.config  modules.json  firmware-lock.json
  gpio/           rdk_x5_40pin.json
  accelerators/   sources.json  assets-lock.json
  patches.json    workspace.example.json  npmrc  README.md
```

| File | Purpose | Consumers |
| --- | --- | --- |
| `build/pipeline.json` | Full build stages and profiles | `./rdkhm plan/run` |
| `build/components.json` | Per-component build, package, deploy | `./rdkhm build/package/deploy`, `build` |
| `build/haps.json` | HAP build registry: app source, hvigor product name and `verified` flag | `scripts/build-hap.py`, `./build hap`, `./rdkhm build settings` |
| `build/components.json` `pintool` | First-party PinTool HAP build/package target | `scripts/build-pintool-hap.sh`, `./rdkhm build/package pintool` |
| `sources/repo.xml` | `repo` manifest for RDK kernel/BSP and the OH manifest repo | `scripts/fetch-sources.sh`, `scripts/check-sources.py` |
| `sources/openharmony.lock.xml` | `repo` manifest pin for the OpenHarmony tree | `scripts/sync-openharmony.sh`, `./rdkhm snapshot` |
| `kernel/` | Base config, vendor defconfigs, `modules.json`, `firmware-lock.json`; `RDKHM_KERNEL_PROFILE` selects `default` or `rt` | `scripts/build-kernel.sh`, `scripts/prepare-kernel.sh`, `prepare-driver-bundle.py`, `import-driver-firmware.py` |
| `gpio/rdk_x5_40pin.json` | RDK X5 40-pin GPIO/alt-function map and current mux state | bring-up notes, GPIO HDI/NAPI work |
| `accelerators/sources.json` | Accelerator upstream revisions | `scripts/prepare-accelerators.py` |
| `accelerators/assets-lock.json` | Runtime library hashes | `scripts/prepare-accelerators.py` |
| `patches.json` | Single patch manifest for kernel and OpenHarmony | `scripts/apply-patches.py`, `scripts/check-patch-coverage.py` |
| `npmrc` | npm/ohpm registry | `scripts/build-openharmony.sh`, `prepare-openharmony.sh` |
| `workspace.example.json` | Template for machine-local settings | operators |
| `workspace.local.json` | Ignored machine-local overrides | `scripts/workspace.py` |

Rules:

- `sources/repo.xml` project paths must stay under `oh/`, `rdk/` or `deps/`
  and must not nest. camsys is a sibling project linked into the kernel tree.
- `RDKHM_KERNEL_PROFILE=default` must not apply `patches/optional/preempt-rt`;
  the `rt` profile uses the tracked `_rt` defconfig and the `kernel-rt` patch
  collection. `./rdkhm check` validates both remain wired.
- JSON files that describe state carry `schema_version`.
- Component artifact and module paths may use `${KERNEL_RELEASE}`; package and
  deploy expand it from `out/kernel/obj/include/config/kernel.release`. Do not
  hardcode a kernel release in `build/components.json` or deploy scripts.
- `deploy.serial_required` makes `./rdkhm deploy --apply` require
  `--serial-confirmed`; the flag records operator confirmation of serial access,
  not detection.
- `./rdkhm check` validates JSON, patch/HAP/component references, pipeline
  stages and source-manifest paths before any build.
- Never commit `workspace.local.json` or absolute machine paths.
