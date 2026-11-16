# Deferred hardware and runtime work

Engineering integration is the current focus. None of the items below is
considered complete solely because a module compiled or a library loaded.

| Priority | Work | Acceptance evidence |
| --- | --- | --- |
| P0 | Recover HDC at the board's current address | Remote shell and fresh boot ID/logs |
| P0 | Cold boot the updated image | Accounts, BMS, audio and display start without hot fixes |
| P0 | Launcher and lockscreen lifecycle | Visible, interactive desktop and ArkUI application |
| P1 | USB touch | Correct coordinates, gestures and application delivery |
| P1 | WS73 Wi-Fi/BLE/SLE | Firmware/interfaces, connection and real traffic; explain previous disconnect |
| P1 | Audio | Playback, capture and stable route changes |
| P1 | GPU | RenderService integration and hardware-rendered buffers displayed |
| P1 | NPU | Real model inference and NNRT integration |
| P2 | Camera and codec HDIs | Preview/capture and real hardware encode/decode streams |
| P2 | UART Bluetooth | Firmware initialization, discovery and connection |
| P2 | Network and USB | Boot connectivity, default route and serial-host service |
| P2 | SELinux and service permissions | Dedicated domains, correct labels and enforcing validation |
| P2 | Other system services | TEE, sandbox and memory-control configuration resolved |
| P3 | Soak and release acceptance | Repeated cold boots, hotplug, applications and sustained display |

Evidence from earlier board sessions remains in `out/board-logs/` and the
subsystem documents. See `STATUS.md` for the historical bring-up sequence.
