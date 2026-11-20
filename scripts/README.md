# Script index

All scripts resolve paths through `env.sh`; do not hardcode
`sources/...`, `thirdparty/...` or SDK tool paths.

## Entry points and orchestration

| Script | Role |
| --- | --- |
| `integration.py` | `./rdkhm` implementation: plan/run/snapshot/check/components |
| `workspace.py` | Loads `config/workspace.local.json` and derives canonical paths |
| `components.py` | Component build/package/deploy implementation |
| `apply-patches.py` | Applies or reverts `config/patches.json` collections idempotently |
| `build-hap.py` | Builds one HAP from `config/build/haps.json`; `--all --jobs N` builds in parallel |
| `image_haps.py` | Resolves the shared HAP-to-image manifest |
| `hvigor_sdk.py` | Internal hvigor SDK layout helper (used by the CLI below) |
| `workspace-env.sh` | Exports workspace settings to shell entry points |

## Sources and preparation

| Script | Role |
| --- | --- |
| `fetch-sources.sh` | `repo init/sync` from `config/sources/repo.xml` |
| `check-sources.py` | Verifies existing checkouts against the manifest |
| `sync-openharmony.sh` | `repo init/sync` for the pinned OpenHarmony tree |
| `prepare-kernel.sh` | Fetch, apply kernel patches (plus opt-in RT), link HDF |
| `prepare-openharmony.sh` | Apply OH patches, install Python/prebuilts/SDK |
| `prepare-sdk.sh` | Installs the pinned API 20 SDK |
| `prepare-nearlink.py` | Exports WS73/SSAP sources and config |
| `prepare-ws73-bsp.py` | Imports the pinned WS73 BSP archive |
| `prepare-accelerators.py` | Captures the private accelerator runtime |
| `prepare-driver-bundle.py` | Stages kernel modules, firmware and driver config |
| `import-driver-firmware.py` | Imports firmware and validates its lock file |
| `inject-driver-bundle.py` | Injects the staged driver bundle into a vendor image |
| `install-system-sdk-api.sh` | Installs source-generated system API declarations |
| `prepare-host-tools.sh` | Checks/installs host build prerequisites |
| `link-hdf.sh`, `link-product.sh` | Create generated links into source trees |

## Build, image and verification

| Script | Role |
| --- | --- |
| `build-kernel.sh` | Kernel `Image`, `dtbs`, `modules` for `RDKHM_KERNEL_PROFILE` |
| `build-openharmony.sh` | Upstream `build.py` wrapper |
| `build-target.sh` | One ninja target without image assembly |
| `build-bringup-userspace.sh` | Static busybox and kernel probe |
| `build-accelerator-modules.sh` | BPU external modules |
| `build-nearlink.sh` | WS73 kernel modules |
| `build-settings-hap.sh` | Compatibility wrapper for `build-hap.py settings` |
| `build-pintool-hap.sh` | Build and sign the PinTool HAP from `apps/rdkhm-pintool` |
| `gen-gpio-map.py` | Validate the 40-pin map and emit the bring-up TSV |
| `gen-pin-data.py` | Generate the ArkTS pin table for the PinTool HAP |
| `sdk-home.py` | Print/create the hvigor-compatible SDK root |
| `test-gpio-daemon.py` | GPIO socket service protocol smoke test |
| `check-hap-signatures.py` | Verify HAPs use the official OpenHarmony release key |
| `check-patch-coverage.py` | Reject orphan patch files and manifest drift |
| `check-patch-format.py` | Validate patch mail headers and diff format |
| `check-access-token-abi.py` | Check the access-token ioctl ABI against the kernel |
| `check-composer-abi.py` | Check required composer VDI exports |
| `make-openharmony-image.sh` | Assemble the SD image |
| `verify-openharmony-image.py` | Offline image verifier |
| `test-audio.sh`, `test-nearlink.sh` | Board/host regression helpers |
| `test-accelerators.py`, `test-accelerator-socket.py` | Accelerator runtime and socket tests |
| `test-*.py` | Offline regression tests |

## Board access and deployment

| Script | Role |
| --- | --- |
| `deploy-composer-fix.sh` | Legacy dry-run-first composer hot deploy; prefer `./rdkhm deploy` |
| `deploy-nearlink-fix.sh` | Legacy WS73 module staging; prefer `./rdkhm deploy` |
| `deploy-boot-audio-fix.sh` | Legacy audio library deploy; prefer `./rdkhm deploy` |
| `collect-board-logs.sh` | Read-only board log capture |
| `board-input-test.sh` | UI snapshot and input observation |
| `serial-monitor.py` | Serial console capture |
| `classify-board-log.py`, `summarize-board-capture.py` | Log triage |

Naming rules: `build-*`, `prepare-*`, `deploy-*`, `verify-*`, `check-*`,
`board-*`. New scripts must source `env.sh` and use the exported paths.
