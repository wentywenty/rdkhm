# X5 standard-system integration

## Reference

The local reference is `/home/robo/roboparty_repo/bsp/roboparty_build`:

- `config/boards/rdk-x5.csc`: QSPI firmware, ARM64 and ttyS0 at 115200.
- `config/sources/families/hobot-x5.conf`: 4 MiB gap, CONFIG FAT32, active ext4 root.
- `config/bootscripts/boot-hobot-x5.cmd`: board-ID DTB selection and kernel addresses.

That BSP pins kernel `6177afbf829f16c742199c708d44ad2358ac377a`.
RDKHM currently retains its earlier pinned `b2edb450c6eaef1c7277885d49f74efb6088b634`.
The reference checkout is unchanged. Its Ubuntu binary packages are not OH musl libraries.

## Display and input

The product selects `drivers_peripheral_display_vdi_default` and installs both VDI libraries.
The patch uses the newer `buffer/vdi_base` and `composer/vdi_base` sources.
It does not use the legacy `hal/default_standard` Hisilicon physical-address allocator.

For `rdk_x5`, allocation uses DRM dumb buffers and PRIME on `/dev/dri/card0`.
Composition requests client rendering for every layer and submits the client buffer to a primary plane.
Selection uses DRM `possible_crtcs`, not Rockchip `NAME` or `PLANE_MASK` properties.
No GPU or vendor 2D blitter is loaded. The initial scope is one connected HDMI output.
The target kernel's Verisilicon driver exposes atomic modesetting and GEM/PRIME mmap.

Both AArch64 VDI libraries compile. HDMI, buffer lifetime, hotplug and fence behavior require later board validation.
Optional metadata/image-layout operations still return unsupported in the upstream default VDI.

The product retains `ace_enable_gpu` for shared rendering types and interfaces.
Both OpenGL and Vulkan backends remain disabled, as do parallel rendering and profiling.
The raster surface fallback is selected without these backends.
`RSDividedRenderUtil::CreateBufferDrawParam` sets `useCPU` when EGLImage is disabled.
`RSRenderEngine::DrawWithParams` then uses `DrawBuffer` for client composition.
RenderContext exists for shared callers, but its EGL/Vulkan initialization is skipped.
This does not provide software GPU emulation or guarantee GPU-only effects work.
The retained compatibility patch also repairs several declarations in fully GPU-disabled builds.

HCS creates composer, allocator, WLAN/WPA/hostapd, Audio HDI and USB serial DDK hosts.
Input uses the upstream `udriver` passthrough implementation.
The input device manager and MMI/libinput consume Linux `/dev/input` events.
Kernel UHID, uinput, FUSE, software sync and DMA-BUF heaps are built in.
The driver bundle adds dependency-ordered modules and firmware before OH init.
See [drivers.md](drivers.md) for per-device coverage and remaining HDI work.

## System and applications

Product init config supplies device permissions and starts the USB setup service.
USB setup uses an existing UDC; it does not change a host port's role.
`persist.rdkhm.usb.controller` can select a controller when several exist.
HDC uses FunctionFS and upstream readiness triggers. TCP transport is disabled.
USB identifiers are development identifiers, not production assignments.

Same-release prebuilt HAPs supply Launcher, SystemUI and Settings.
Their install lists and permission declarations come from the reference product.
All source repositories have completed `git lfs pull`, including these HAPs.
The power-dialog HAP compiles after installing source-generated system API declarations.

The SDK archive is the official 6.0 API 20 public release. The pinned source's SDK generator
provides system declarations through `ohos_declaration_ets_api`; raw source declarations are not copied directly.
This is a local SDK for the system build, not a separately validated SDK distribution.

Host Clang uses the workspace's GCC 11 view, including the Koala native generator.
Ruby is extracted into the workspace. Host packages and the reference BSP are unchanged.

## SD image assembly

Run `bash scripts/make-openharmony-image.sh` after the complete `images` build succeeds.
The script requires the real system, vendor and userdata images.
Optional product and engineering images are embedded when upstream generated them.
Missing images with a corresponding staged partition directory cause an error.

| Partition | Contents |
| --- | --- |
| 1 | 256 MiB CONFIG FAT32 at 4 MiB |
| 2 | Active ext4 system/root, X5 kernel, DTBs, boot script and bootstrap |
| 3 | Read-only ext4 vendor |
| 4 | Writable ext4 userdata with fscrypt enabled |

Existing product and engineering images remain separate filesystems, mounted read-only through loop devices.
The current product generates only `eng_system`; unused product partitions remain empty root directories.
The bootstrap identifies the root block device from mountinfo, then mounts vendor and data from that same device.
U-Boot passes the root PARTUUID. No disk formatting happens during boot.
Upstream filesystem metadata is preserved by extending the system image and injecting only boot files.
SELinux policy generation is enabled for this product. The X5 overlay adds
labels for `/dev/galcore`, `/dev/bpu*`, `/dev/video*` and the manual accelerator
wrapper, with minimum development IO rules. These rules still require AVC
review on a booted board before enforcing a production policy.

The previous `rdkhm-x5-bringup-0.1.img` remains a BusyBox-only image with the earlier kernel.
It is not updated by compiling new kernel or userspace artifacts.
