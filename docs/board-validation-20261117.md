# X5 板测记录：2026-11-17

## 目标

验证新刷入镜像是否包含自启动诊断，并采集 HDC、HDMI、触摸、摄像头、Composer、GPU 和安全状态。

## 连接

- 目标：`<board-ip>:5555`
- 协议：OpenHarmony HDC TCP
- 结果：`hdc tconn` 成功，shell 和文件接收成功
- 运行时间：约 36 分钟
- SSH：未作为验证路径

## 镜像特征

板端存在：

```text
/rdkhm/boot-diagnostics.sh
/data/rdkhm-logs/boot-status.txt
```

因此这次镜像包含自启动诊断组件。报告启动时刻约为开机后 38 秒。

本次记录缺少镜像 SHA256 和 boot_id。镜像构建时间为 17:20，早于
`patches/display/0007-composer-release-entrypoint.patch`（18:14）和
`hardware-status.sh` 的 BusyBox 修复（18:37），因此被测镜像不含这两项改动；
这两项需在下一版镜像中复测。

## 通过项

- Linux 6.1.83-rdkhm 启动。
- HDMI connector `connected`、`enabled`，EDID 256 字节。
- `/dev/dri/card0`、`renderD128`、`/dev/galcore`、`/dev/bpu` 存在。
- `render_service`、`composer_host`、Launcher 运行。
- QDtech MPI5001 触摸设备为 `event1`。
- 手动启动 `hdcd` 后 HDC TCP 5555 可用。冷启动 38 秒自检仍为
  `hdcd:missing` / `HDC_TCP_5555=not-listening`，自启动尚未验证。
- WS73 固件文件存在。

## 未通过或未完成

- `/dev/video*` 不存在，摄像头和 VPU 不能验收。
- WS73 `plat_soc`、`wifi_soc`、`ble_soc`、`sle_soc` 均未加载。
- SELinux `enforcing=0`，只属于开发模式。
- Composer 日志仍报告 `DisplayComposerImplRelease` 缺失、刷新回调为空、`PreProcessLayersComp=-3`。
- GPU backend 缺少 `libgraphic_innovation.z.so`，GPU context 为空。
- 背光设置返回 `ec=-5`。
- `/rdkhm/hardware-status.sh` 因目标 BusyBox 禁用 `$((...))` 在 38 秒自检中
  退出，运行报告不完整；工作区已改为 `expr`，待下一版镜像验证。

## 20:32 复查（同一旧镜像）

- boot_id：`4f8e7768-06b6-4448-9866-2b503ec88e96`，内核 `6.1.83-rdkhm #9`
- HDC TCP 已监听，`hdcd` 存在
- 锁屏 UI 布局完整（`06:00`、`2026年11月17日`、`屏幕锁定中`），但 `snapshot_display` 全黑
- PowerMgr 初始 `SLEEP`（30 秒超时）；`power-shell wakeup` 后 RS `powerStatus=ON`，抓图仍全黑
- `SURFACE_NODE[ScreenLockWindow]` 为 `Frame[-inf]`、`VisibleRegion [Empty]`
- `FrameBufferSurface` 队列为空；`PreProcessLayersComp` 返回 -3（`layerIdMap_` 为空）
- 应用进程报 `RSRenderNodeDrawableAdapter::OnGenerate`（type 1/4225/129）和 `InitRenderParams failed`
- 证据：`out/board-logs/20261117-203238/`（含 `screen5.jpeg`、`layout.json`）

## 日志追溯补充

- access_token `TYPE=84` 是 `TCGETS`（0x54），属于无关 tty 探测，
  不是 token ABI 错误；已加内核 patch 降噪。
- bootanimation 视频失败链：`libdisplay_buffer_vdi_impl.z.so` 缺失 →
  metadata `RegisterBuffer` 失败 → `AllocSurfaceBuffer` 失败 →
  `Start codec failed: cannot allocate buffers`；已补镜像注入。
- 黑屏链：应用 `OnGenerate/InitRenderParams failed` → RS `layerIdMap_` 为空 →
  `PreProcessLayersComp -3` → `ScreenLockWindow` 无有效 Frame/buffer。
  已加 `graphic2d/0003`，待刷写验证。
- `pin_auth_host`/`usb_serial_host`/`teecd` 是 init/sandbox/TEE 噪声，
  与首帧黑屏分开处理。

## 后续镜像（未刷写）

2026-11-17 晚增量重建了 OpenHarmony `images` 目标，并用
`./rdkhm run package` 重新组装、验证：

- 镜像 SHA256：`4368578ffed5043c1ac74be22556f61b1bf99a52c435e18928b6905b955a6727`
- 运行证据：`out/runs/20261118T053124Z-0nkn4n3v`
- 新增内容：`DisplayComposerImplRelease`、render-service guards、
  `hardware-status.sh` 的 BusyBox 安全算术、`screen-status.sh` 和 bootanimation 配置
- 离线验证：174 项打包文件比较、composer service 导出和 access-token ABI 通过
- 尚未刷写，因此本页上面的板端结论仍只对应旧镜像

## 日志位置

- `out/board-logs/<board-ip>/boot-status.txt`
- `out/board-logs/<board-ip>/hilog-current.txt`

## 复测命令

```sh
source env.sh && HDC=$RDKHM_HDC
$HDC tconn <board-ip>:5555
$HDC -t <board-ip>:5555 shell '/rdkhm/hdmi-status.sh'
$HDC -t <board-ip>:5555 shell '/rdkhm/touch-status.sh'
$HDC -t <board-ip>:5555 shell 'grep -E -i "DisplayComposerImplRelease|RegRefreshCallback|PreProcessLayersComp|gpuContext|SetDisplayBacklight" /data/rdkhm-logs/hilog-current.txt | tail -80'
```


## 2026-11-18 临时板端验证（旧镜像 + 热替换库）

- 板卡：`<board-ip>:5555`，boot_id 仍为 `4f8e7768-06b6-4448-9866-2b503ec88e96`，内核 `#9`。
- 临时部署：`librender_service_base`、composer VDI、buffer VDI metadata 兼容版、5 个
  可选库 stub、`libtask_controller`、syscap 文件；原始文件备份在
  `/data/rdkhm-live-backup-20261118-001247/`。
- 结果：
  - `libtask_controller` 被 `concurrent_task_service` 加载，日志出现
    `TaskControllerInterface load function success.`。
  - 5 个 stub 的 `dlopen`/`dlsym` 全部通过（`/data/local/tmp/dlcheck`）。
  - RenderService 不再出现 `OnGenerate`/`InitRenderParams` 失败。
  - `ScreenLockWindow` 有 buffer，`FrameBufferSurface` 有 buffer；
    800x480 锁屏截图可见，见 `out/board-logs/20261118-live/screen-final.jpeg`。
  - 屏幕 `powerStatus=ON`，`backlight=255`。
- 尚未验证：刷写后的冷启动、`DeviceAuth` syscap（旧系统 param 服务仍需重启/刷写）、
  tracefs/PSI/RTG proc 节点、长时间稳定性。
- 新镜像：`4368578f...`，仅组装和离线 verifier 已通过，尚未刷写。


## 2026-11-18 tracing-enabled 启动 panic

- 新内核 `6.1.83-rdkhm #12` 首次启动约 2.4s 时 panic：
  `trace_event_eval_update()` 空指针，调用链来自
  `trace_module_notify` → `load_module`，模块为 `aic8800_bsp(+)`。
- 根因：启用 `CONFIG_TRACING`/`CONFIG_FTRACE` 后，模块 trace eval map
  进入 `trace_event_eval_update()`，代码未防御空 map 项/空 event class。
- 修复：`patches/kernel/0008-trace-eval-null-guard.patch`，保留
  tracefs/PSI 配置，添加 map、map entry 和 event class 空值保护。
- 新镜像 `4368578f...` 已组装并通过 174 项 verifier；板卡当前无法通过
  HDC 进入，需重新刷写该镜像验证冷启动。
- 完整启动日志：`out/board-logs/20261118-panic/boot.log`


## 2026-11-18 新镜像启动验证

- 板卡：`<board-ip>:5555`，内核 `6.1.83-rdkhm #13`，boot_id
  `cc4072bb-5c0b-4813-aa0c-2c15e1a470d1`。
- `trace_event_eval_update` panic 未再出现，`aic8800_bsp` 已加载。
- `libtask_controller` 被 `concurrent_task_service` 加载。
- 5 个可选 stub 文件存在；`SystemCapability.Security.DeviceAuth=true`。
- `/proc/pressure/{cpu,io,irq,memory}`、`/sys/kernel/tracing`、debugfs 均存在。
- 音频卡 `duplexaudio` 已注册，`designware_i2s`/`es8326` 已加载。
- `power-shell wakeup` 后屏幕 `POWER_STATUS_ON`，800x480 锁屏可见：
  `out/board-logs/20261118-new-image/screen-lock.jpeg`。
- 仍有问题：
  - `/proc/thread-self/sched_qos_ctrl` 缺失；`0009` 已改为不受
    `CONFIG_SCHED_DEBUG` 控制，待下一次刷写验证。
  - `hdcd` 在本次启动中后启动，冷启动自动监听仍需复测。
  - SELinux 仍 permissive，AVC/audit backlog 仍存在。
