# Kernel port notes

Scope: X5 Linux 6.1.83, OpenHarmony 6.0 standard userspace prerequisites.
This is development code, not a security-reviewed or board-qualified release.

## Sources and changes

All non-OpenHarmony baseline revisions are recorded in `config/sources/repo.xml`;
the OpenHarmony tree is pinned by `config/sources/openharmony.lock.xml`. The existing local
RoboParty BSP was inspected only; the implementation uses a fresh official
D-Robotics kernel checkout.

- `drivers/accesstokenid`: imported from OH Linux 6.6 release source. Its
  NWEBSPAWN_UID (3081) is defined locally rather than changing generic uidgid.h.
- `task_struct.token/ftoken`: same per-task fields as the OH kernel.
- Binder: selectively port token capture, receive-side token storage, feature
  query ioctl 30 and access-token query ioctl 31 from OH Linux 6.6.
  Only feature bit 0 is advertised. Sender-info and transaction diagnostics
  extensions are not yet implemented. The token ioctl copies a zero-initialized
  per-thread structure, including reserved fields, and reports EFAULT on copy
  failure. Upstream copies only the two populated fields.
- Ashmem: imported `ashmem.c`, `ashmem.h`, `uapi/ashmem.h`, and
  `include/linux/memcheck.h` from the OH 6.0 RK3568 Linux 6.6 patch.
  Only these file additions were extracted, not the RK3568 platform patch.
  Adapt `vm_flags_clear` to the Linux 6.1 VMA flag API. Purgeable-memory and
  memory-tracing extensions remain disabled.
- X5 `camsys` is a mandatory source dependency in the vendor Kconfig tree,
  independently of whether camera support is used at runtime.
- The vendor DRM display controller and HDMI bridge drivers are built in to
  avoid depending on Ubuntu module-loading services for early display.
  This does not enable or prove GPU rendering.
- The vendor GC820 composition option is disabled: the built-in display driver
  otherwise refers to symbols in a modular N2D driver. The device-tree graph
  uses an RDK-specific auxiliary-device override retaining only SIF; direct
  display without GC820 composition still needs board-side validation.
- HDF core is linked using the upstream layout. The initial integration used an
  X5 HCS configuration with only the base host/kevent service; the current HCS
  also registers audio, USB serial, WLAN/WPA/hostapd, display composer, allocator
  and camera hosts. Their runtime behavior still requires board validation.
- Kernel HDF compilation uses Linux stdarg.h instead of libc headers, inline
  atomics instead of libgcc outline helpers, and GCC's comment-aware fallthrough
  diagnostic level. WERROR remains enabled.
- The separate HDF patch hides user-only constructor lookup and floating-point
  write functions under !__KERNEL__. The kernel only supports RAW SBuf, which
  does not implement these floating-point operations. Userspace definitions are
  unchanged. One intentional kernel fallthrough is explicitly annotated.

## First board boot: deferred display probe panic

The 2026-11-16 user-provided serial log reaches Linux 6.1.83-rdkhm,
initializes AccessToken/Ashmem and discovers the SD partitions. After
`vs-dc: Failed to get aux devices`, it panics at about 1.69 seconds in
`remove_nodes`, called by `devres_release_all` during deferred probe cleanup.
OpenHarmony init has not started at this point.

`dc_add_device` allocates each `dc_device` with `devm_kzalloc`, but the
`dc_get_all_devices` error path used plain `kfree`. That frees storage still
linked into the owning device's devres list. Patch
`patches/kernel/0003-display-deferred-probe-devres.patch` uses
`devm_kfree(dc_dev->dev, dc_dev)` to unlink the managed allocation before freeing
it. The preparation script applies this patch reproducibly. Deferred probing
remains enabled; this fix does not establish that all display dependencies
will subsequently bind or that HDMI will show the OpenHarmony UI.

The patched ARM64 Image builds successfully. The next user-provided boot log
passes the former panic, mounts all three Linux partitions, loads board modules
and reaches OpenHarmony second-stage init. It ends during parameter loading at
6.38 seconds, so it does not establish that init is stuck or services are ready.

## Second board boot: missing GC820 display dependency

The second log still repeats `Failed to get aux devices`. The inherited X5
device tree declares both SIF and GC820 as required display auxiliary devices,
while this port disables `CONFIG_VERISILICON_GC_PROC_SUPPORT` and does not load
the GC820 driver. The display driver's native primary-plane path is compiled
when that option is disabled, but probe still waits for every DT dependency.
Patch `0004-rdk-direct-scanout.patch` overrides the RDK auxiliary list to SIF
only, covering both RDK board revisions without changing other X5 boards.
The image verifier checks auxiliary names and the SIF phandle in both packaged
DTBs. Enabling GC820 composition later requires restoring its DT dependency.
HDMI modesetting and OpenHarmony UI output still require a new physical boot.

The same log's SELinux mount/load failures are consistent with the development
boot script's `selinux=0`; policy compilation is not runtime enforcement.

## Third serial excerpt: SELinux prevents service exec

The subsequent excerpt runs from 5.52 to 12.90 seconds and reaches the pre-init
job. It explicitly reports `failed to set secon` for ueventd and watchdog.
In OpenHarmony init's `services/modules/selinux/selinux_adp.c`,
`SetServiceContent` calls `_exit(INIT_EEXEC_CONTENT)` when `setexeccon` fails.
Thus these are fatal child-service errors even though PID 1 continues. A
`ServiceStart started info` message only confirms fork, not successful exec.
Disabled SELinux is incompatible with this enabled init plugin.

The development boot command now uses `selinux=1 enforcing=0`. The existing
kernel already has `CONFIG_SECURITY_SELINUX_DEVELOP=y`; the configuration
fragment now pins it explicitly. OpenHarmony's policy loader reads `enforcing`
from the kernel command line before its config-file default. This preserves
policy loading and context operations while permitting access denials during
bring-up. It is not an enforcing security configuration. No init checks are
bypassed. The image verifier compares the packaged policy and boot script and
requires this permissive command line.

Remaining messages include missing tracefs paths (FTRACE is disabled), an empty
bootstrap-managed fstab, incomplete service GID definitions, and serial/UDID
lookup against mmcblk0 rather than the actual boot SD. These require follow-up;
the excerpt ends mid-line and does not establish the final boot state. The
SELinux correction still needs a new board log showing policy load success
and actual service execution. This excerpt does not include early DRM probe
messages and cannot validate the prior HDMI dependency correction.

## Outstanding validation

### Binder device creation after SELinux bring-up

The log at `$RDKHM_BSP/log` confirms DRM initialization,
successful policy loading, and ueventd execution. At 14.61 seconds SAMGR reports
`set context fail!`, which comes from `IPCSkeleton::SetContextObject`, not SELinux
label setup. At 15.02 seconds init synchronously invokes sdc, which waits for
SAMGR. Earlier chmod operations report all three Binder devices missing.

This vendor kernel's `binder_init` calls `init_binder_device` only when
`CONFIG_ANDROID_BINDERFS` is disabled. The port had enabled BinderFS but supplied
no mount, so the configured device names alone did not create `/dev/binder`,
`/dev/hwbinder` or `/dev/vndbinder`. The configuration now disables BinderFS
and retains all three legacy device names. OH ueventd already supplies their
permissions. Bootstrap checks their character-device type before entering OH
init, and image verification rejects the incompatible configuration. Kernel
and module builds plus offline packaging checks do not prove SAMGR registration;
that requires the next physical boot.

- Runtime token inheritance, unauthorized ioctl rejection and Binder token
  propagation across synchronous, asynchronous and nested transactions.
- Ashmem mmap, protection masks, fork sharing and reclaim under memory pressure.
- Full OH userspace ABI/config requirements, not just these initial facilities.
- HDF runtime and X5-specific display/input services.
- Correct firmware/module packaging, device permissions and SELinux policy.

## Rollback

Port changes are confined to this workspace. Preserve the current working tree
and construct a fresh checkout from `config/sources/repo.xml` to recover the vendor
baseline. Do not reset unrelated BSP repositories. No flash or bootloader changes
have been made. Kernel patches are exported under `patches/` for review and
application to clean checkouts.


## Opt-in PREEMPT_RT profile

The default kernel build uses the vendor `hobot_x5_rdk_ubuntu_defconfig` and
does not apply the optional RT patch. The RT path is opt-in:

```sh
RDKHM_KERNEL_PROFILE=rt ./rdkhm run build
```

This selects `config/kernel/hobot_x5_rdk_ubuntu_rt_defconfig`,
applies `patches/optional/preempt-rt/patch-6.1.83-rt28.patch` through the
`kernel-rt` manifest collection, and requires `CONFIG_PREEMPT_RT=y` after
`olddefconfig`. Switching back to `default` makes `prepare-kernel.sh`
reverse-apply the optional patch. The patch applies cleanly to the current
kernel tree, but the resulting RT kernel has not been booted or validated on
the board; treat it as a separate profile, not the default image.

## TCAN4x5x SPI clock clamp (2026-11-19)

The X5 RDK device trees request an 18 MHz SPI clock for the TCAN4x5x, but the
TCAN4550 SPI interface is limited to 10 MHz. At 18 MHz the DEV_ID registers
read as zero and `m_can` reports `Failed to init module`.
`patches/kernel/0018-tcan-spi-max-speed.patch` clamps `spi->max_speed_hz` to
10 MHz in `tcan4x5x_can_probe()` before `spi_setup()` and logs the change.

On the board, the rebuilt module produced DEV_ID `0x4e414354 0x30353534`
("TCAN4550") and classic CAN plus CAN-FD loopback passed. The patch is in the
kernel manifest and applies cleanly to a clean tree. The 20:54 unified image
(kernel #6) includes it; cold-boot loopback tests pass without a manual module.
External bus validation remains outstanding.

## QoS/RTG compatibility layer

The X5 vendor kernel does not expose the Qualcomm-style
`/proc/thread-self/sched_qos_ctrl` and `/proc/self/sched_rtg_ctrl` entries that
OpenHarmony's `qos_manager`/`ffrt` expect. Patch
`patches/kernel/0007-rtg-qos-proc.patch` adds
`fs/proc/rtg_qos.c`, wires the entries into the per-tid/per-tgid proc tables,
and accepts the `0xCC` QoS and `0xAB` RTG-enable ioctl layouts.

QoS levels are mapped to the generic scheduler nice value; RTG enable is
recorded for ABI compatibility. This is explicitly **not** a vendor hardware
RTG scheduler, and the proc entries do not pretend to provide vendor frequency
or frame scheduling. A future vendor RTG patch should replace this layer and
the unit/board acceptance must check actual frame/QoS behavior.


### Tracing module-eval panic guard (2026-11-18)

Enabling tracing exposed a boot panic while `aic8800_bsp` was loaded:
`trace_event_eval_update()` dereferenced a null eval-map entry or event class.
`patches/kernel/0008-trace-eval-null-guard.patch` returns early for a null
map and skips null map entries/classes. This preserves
`CONFIG_TRACING`/`CONFIG_FTRACE` for tracefs while making module load safe.
