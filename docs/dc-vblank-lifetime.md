# DC VBlank crash after deferred binding

## Board evidence

The user reports the screen lighting up with the format-selection fix. The
captured log is retained in `out/logs/board-vblank-panic-before-fix.log`:

- 0.496s: DC component binds; HDMI encoder then returns -517 at 0.549s.
- 1.776s: DC binds again; DRM registration succeeds at 1.841s.
- 34.688s: NULL access at address 0x18, PC `__dc_proc_vblank+0x3c/0x80`.
- 34.956s: fatal interrupt exception and kernel panic.

Disassembly of the matching pre-fix vmlinux places `ldr x2, [x19, #24]` at
that PC; the log has x19=0. This is reading `dc_proc->info` through a NULL
list cursor, not dereferencing a NULL vblank callback. `camera_service` is
the interrupted task; the call chain is the DC IRQ handler.

## Source defect and change

`component_bind_all()` unwinds components when the HDMI bridge defers.
`vs_drm_bind()` then calls `drm_mode_config_cleanup()`, whose object destruction
callbacks free the DC plane, CRTC and writeback wrappers. Their `head` links
were not removed from `vs_dc`'s persistent lists. The DC device is only probed
once; rebinding appends new objects to those same lists. Interrupt traversal
can therefore access freed memory from the first attempt.

Kernel patch `0005-display-object-list-lifetime.patch` calls `list_del_init()`
in each wrapper destructor before processor destruction/freeing. Initialization
already makes these links self-referential, so cleanup of an initialized but
not yet linked object also remains valid. The change repairs list ownership;
it does not suppress VBlank callbacks or silently ignore corrupted pointers.

## Verification and limits

`tests/test-dc-object-lifetime.py` compiles the production destructor bodies
against the kernel's tools list implementation and small object fixtures.
It covers two objects per list, three bind/cleanup cycles for each object type,
and cleanup of an initialized unlinked object. The original source fails the
first owner-list assertion; the fix passes. This is a host lifecycle test,
not an interrupt concurrency or hardware scanout test.

The ARM64 kernel Image was rebuilt, and disassembly confirms the list unlink
before destruction. Driver manifest regeneration retains the existing modules:
this patch changes only internal built-in destructor bodies, with no exported
interface, kernel configuration or module release change. The assembled image
is checked against the new kernel and manifest by the image verifier.

Board acceptance: boot past the previous 35-second failure, leave the display
running for several minutes, and confirm no `__dc_proc_vblank` Oops or panic.
Then check actual UI interaction and USB touch delivery. Audio service faults
in the same capture are not fixed by this patch.
