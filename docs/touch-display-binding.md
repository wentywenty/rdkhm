# Touch/display binding investigation - 2026-11-18

## Source finding

The legacy WindowManager publisher is
`foundation/window/window_manager/wmserver/src/input_window_monitor.cpp`,
`InputWindowMonitor::TraverseWindowNodes`. Upstream initialization omitted
`MMI::WindowInfo::displayId`, whose default is -1. MMI groups windows by this
field in `UpdateWindowsInfoPerDisplay`; `GetWindowInfoById` skips negative IDs.
This explains how evdev/MMI can receive touch while no window receives it.

The existing `patches/window-manager/0001-input-window-display-id.patch`
already copies the window's display ID. It is applied in the source checkout
and listed in preparation. It also existed in the 20261118T064654Z packaging
snapshot. This does NOT establish that the running board has the corresponding
compiled library, nor that a window's source display ID is valid at runtime.
Do not add a global `-1 -> 0` fallback: it could misroute multi-display input.

The SceneBoard path in `scene_session_dirty_manager.cpp` already fills this
field. Identify the active window-management path before interpreting logs.
TouchPointToDisplayPoint obtains a physical display using the device binding;
FindPhysicalDisplayInfo already falls back to the main group's first display.
The window's display ID and touch device's display selection are separate checks.

## Changes this session

- Added `0002-input-display-binding-test.patch`: tests the actual legacy window
  publisher for display 0, display 7 and a subsequent display migration.
- Extended `scripts/board-input-test.sh`: defaults to physical observation,
  captures MMI/window/display dumps, records user-reported image hash and boot
  IDs, and rejects results across a reboot. Click/swipe modes inject UI events
  and are not proof of the evdev path.
- No additional production fallback was added; the existing production fix
  must first be checked against the deployed artifact and fresh evidence.

## Board validation protocol

1. Connect HDC using the current IP. Record flashed image hash from the flashing
   record; a full SD-card hash after boot is not the original image hash.
2. Run `bash scripts/board-input-test.sh IP:5555 observe` while the screen is on.
   Physically tap and swipe, recording the exact gesture and visible outcome.
   Inspect InputKeyFlow, target display/window IDs and UI state changes.
3. Run explicit `click` and `swipe` modes to isolate framework delivery from
   USB/evdev. These use the existing 800x480 coordinates; adapt them if needed.
4. With the lockscreen visible, perform a physical unlock gesture and verify
   Launcher becomes the foreground window. A screenshot alone is insufficient.
5. Let normal screen timeout occur, record power state, and physically touch
   the panel. Verify wakeup and a subsequent tap reaches the foreground app.
   Do not substitute `power-shell wakeup` for proof of touch wakeup.
6. Repeat after reboot/hotplug once reboot stability is established. If boot ID
   changes during a test or HDC disconnects, classify that test as interrupted.

Acceptance requires valid registered display IDs for both event and window,
matching coordinates, UI delivery and visible results. Physical wakeup may
involve PowerMgr and USB wake capability beyond the window binding fix.

## Validation boundary

At investigation time `hdc list targets` was empty. No new board runtime,
unlock or wakeup result is claimed. The added C++ regression is source-only
until the OH unit-test target is built and run. No image or target build and
no board deployment were performed in this session.
