# galcore DMA-BUF ERR_PTR panic - 2026-11-20

This record covers the boot panic observed on the serial console after the
2026-11-20 image was flashed. The panic is in `galcore`, not in `hmdfs`.

## Symptom

Serial capture:

```text
[   38.892184] Unable to handle kernel NULL pointer dereference at virtual address 0000000000000007
[   38.892232] Internal error: Oops: 0000000096000004 [#1] PREEMPT SMP
[   38.892323] CPU: 4 PID: 389 Comm: ld-linux-aarch6 Tainted: P O 6.1.83-rdkhm #10
[   38.892339] pc : _DmabufAttach+0x98/0x300 [galcore]
[   38.892525] Call trace:
[   38.892528]  _DmabufAttach+0x98/0x300 [galcore]
[   38.892572]  gckOS_WrapMemory+0xb8/0x234 [galcore]
[   38.892614]  gckVIDMEM_NODE_WrapUserMemory+0x208/0x340 [galcore]
[   38.892656]  gckKERNEL_Dispatch+0x1e0/0x1634 [galcore]
[   38.892742]  drv_ioctl+0x3cc/0x524 [galcore]
[   38.901938] Kernel panic - not syncing: Oops: Fatal exception
```

The board rebooted after the panic. Full capture:
`out/board-logs/serial-20261120-panic.log`.

## Root cause

`hmdfs.ko` loaded successfully:

```text
hmdfs: hmdfs_init_configfs() init configfs
Modules linked in: ... hmdfs
```

The crash is a missing `ERR_PTR` check in
`drivers/misc/verisilicon/gc8000l/hal/os/linux/kernel/allocator/default/gc_hal_kernel_allocator_dmabuf.c`.

`_DmabufAttach()` called `dma_buf_map_attachment()`, which returned an error
pointer (`ERR_PTR(-5)` rather than `NULL`). The old code only checked `!sgt`
and then dereferenced `sgt->orig_nents`:

```text
x27 = 0xfffffffffffffffb   (sgt)
0xfffffffffffffffb + 12 = 0x7
```

That is exactly the fault address `0x7`.

## Fix

Patch: `patches/kernel/0020-galcore-dmabuf-errptr.patch`

SHA256: `cd722918cf568038e1f2e5c94732f9aed031af5541ecaebd4429151a691844fa`

The patch:

- rejects `IS_ERR(dma_buf_attach(...))`
- rejects `IS_ERR(dma_buf_map_attachment(...))`
- releases the DMA-BUF reference and detaches the attachment on error
- keeps the `dmabuf == NULL` path safe

The patch is listed in `config/patches.json`.

## Build and offline verification

Rebuilt:

- `out/kernel/obj/drivers/misc/verisilicon/gc8000l/galcore.ko`
- `out/driver-bundle/lib/modules/6.1.83-rdkhm/galcore.ko`
  - SHA256 `ee1b6a82857ecfb66616f525b2223ad647723b3f2a137f5c5837b0694c9f905b`
- `out/images/rdkhm-x5-openharmony-dev.img`
  - SHA256 `582d2b1e2bb74f3db281ddc7c394fba61aa2ef0b75d9f8b87e514433fb61d4d5`

`scripts/verify-openharmony-image.py` passes:

```text
PASS: MBR, checksum, four filesystems and 224 packaged artifact comparisons
```

A full `./rdkhm run build` was also attempted. The OpenHarmony ninja build completed, but the stage returned failure at `deps_guard`; the later HAP rebuild was blocked by SDK API mismatches (`print`, `vpn`, `notificationManager`). The final image therefore reuses the already signed HAP set from `2026-11-20 12:19`; it is not a full HAP rebuild. The image still contains the new kernel Image and galcore module.

## Not validated

- The new image has **not been flashed**.
- The serial boot after this galcore patch has **not been tested**.
- The accelerator daemon may still report a DMA-BUF failure; the expected
  behavior is now a clean error return instead of a kernel panic.
- If the daemon still prevents desktop startup for a different reason, capture
  the next serial trace before making another image.

## Reproduce

```sh
JOBS=16 bash scripts/build-kernel.sh modules
python3 scripts/prepare-driver-bundle.py
bash scripts/make-openharmony-image.sh
python3 scripts/verify-openharmony-image.py
```
