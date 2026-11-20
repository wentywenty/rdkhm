# Deferred hardware and runtime work

Engineering integration is the current focus. None of the items below is
considered complete solely because a module compiled or a library loaded.

| Priority | Work | Acceptance evidence |
| --- | --- | --- |
| P0 | Make HDC start automatically on cold boot | HDC reachable without manual `service_control start hdcd` |
| P0 | Cold boot the updated image | Accounts, BMS, audio and display start without hot fixes |
| P0 | Launcher and lockscreen lifecycle | Visible, interactive desktop and ArkUI application |
| P1 | USB touch | Correct coordinates, gestures and application delivery |
| P1 | PinTool cold boot and preinstall | HAP visible after cold boot; UI can read/write a 40-pin GPIO |
| P1 | WS73 Wi-Fi/BLE/SLE | Firmware/interfaces, connection and real traffic; explain previous disconnect |
| P1 | Audio | Playback, capture and stable route changes |
| P1 | GPU | RenderService integration and hardware-rendered buffers displayed |
| P1 | NPU | Real model inference and NNRT integration |
| P2 | Camera and codec HDIs | Preview/capture and real hardware encode/decode streams |
| P2 | UART Bluetooth | Firmware initialization, discovery and connection |
| P2 | Network and USB | Boot connectivity, default route and serial-host service |
| P2 | SELinux and service permissions | Dedicated domains, correct labels and enforcing validation |
| P2 | GPIO service permission model | SA/HDI + SELinux; remove 0666/TCP unauthenticated access |
| P2 | 40-pin pinmux for blocked pins | DTB pinctrl or bus disable; verified electrical behavior |
| P2 | Other system services | TEE, sandbox and memory-control configuration resolved |
| P3 | Soak and release acceptance | Repeated cold boots, hotplug, applications and sustained display |

Evidence from earlier board sessions remains in `out/board-logs/` and the
subsystem documents. See `STATUS.md` for the historical bring-up sequence.

## User-tracked topics

The former top-level `todo` scratch list tracked: GPU, NPU, camera, USB
debugging, calendar, phone, 4G module, NearLink (WS73), rec module, CAN FD,
40-pin GPIO, lockscreen touch, password/TEE, Wi-Fi, native desktop, system
navigation, status bar. Fold each into the priority table above once it has
concrete acceptance evidence.
