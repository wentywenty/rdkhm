# X5 硬件合成可行性评估

更新时间：2026-11-20

## 结论

**当前已刷镜像不能直接做 OpenHarmony 硬件合成，但技术路径已经打开。**

- OpenHarmony RenderService/Composer 仍然走 CPU（软件）合成；`render_service`
  没有打开 `/dev/galcore`，只有 `/dev/dri/card0` 的显示 fd。
- 厂商 EGL/GLES 是 glibc 二进制，无法直接加载进 musl 的 RenderService；
  只能像现在这样在独立的 glibc runtime 进程里使用。
- 离屏 GPU 已经验证可用：GC8000L、OpenGL ES 3.1、shader 编译/绘制/读回通过。
- 要变成“硬件合成”，需要增加一个**进程外 GPU 合成服务**：RenderService 或
  Composer 把图层和 client target 的 dma-buf/fence 传给 glibc GPU 进程，GPU 合成
  到 target，再由现有 DRM/KMS 路径显示。
- 显示控制器本身有 2 个 overlay plane（ARGB8888、支持缩放），所以还存在一条
  **KMS overlay 硬件合成**路径，但只适合少量图层，且需要改 composer 的多平面逻辑。

推荐先做 **进程外 GPU 合成**，保留软件合成作为回退。它不要求替换 OH 的 libc，
也不要求 RenderService 直接加载厂商库。

## 当前证据

| 项 | 状态 |
| --- | --- |
| GPU 离屏 context | `eglCreateContext`/`eglMakeCurrent` 通过 |
| GPU 渲染 | `GC8000L`，`OpenGL ES 3.1 V6.4.14.9.674707` |
| shader | GLSL ES 3.10，编译/链接/三角形绘制/像素读回通过 |
| `libGLSLC.so` | 已进入私有 runtime 和镜像 |
| dma-buf 导入 | `EGL_EXT_image_dma_buf_import`、`_modifiers` 存在 |
| fence | `EGL_KHR_fence_sync`、`EGL_ANDROID_native_fence_sync` 存在 |
| 离屏上下文 | `EGL_KHR_surfaceless_context` 存在 |
| BGRA | `GL_EXT_texture_format_BGRA8888`、`GL_EXT_read_format_bgra` 存在 |
| KMS overlay | DC8000 nano 有 2 个 overlay plane，支持 ARGB8888 和缩放 |
| OH 合成现状 | `RDK_X5_SOFTWARE_COMPOSITION`：所有层 CLIENT，单 primary plane，CPU 合成 |
| RenderService | 只打开 `/dev/dri/card0`，没有 `/dev/galcore` |

证据：

- `out/board-logs/20261120-gpu/gpu-test-20261120.log`
- `out/board-logs/20261120-gpu/egl-extensions.log`
- `docs/accelerators.md` 的 Board probe 2026-11-20

## 三条路线

### A. 进程外 GPU 合成（推荐）

```text
RenderService / HDI Composer (musl)
  |  client target dma-buf fd + layer fds + fences (SCM_RIGHTS)
  v
rdkhm_accel (glibc, /vendor/lib64/rdkhm-accelerator)
  |  EGLImage import (EGL_EXT_image_dma_buf_import[_modifiers])
  |  GLES2 FBO composite -> client target
  |  native fence fd back
  v
Composer DRM Apply / KMS (musl, card0)
```

优点：

- 不替换 OH 的 musl libc，不把 glibc 库塞进 RenderService。
- 复用已经存在的 `rdkhm_accel` 私有 runtime、SELinux domain 和 init-owned socket。
- GPU 只渲染到 dma-buf target，不抢 DRM master，显示仍由 composer 控制。
- 可以用软件合成做逐帧回退。

代价：

- 需要新增 compose 协议、fd/fence 传递、buffer 格式/stride/modifier 协商。
- 每帧有 IPC 和 fence 开销；小屏 800x480 可接受，需要实测。
- 需要改 composer（推荐）或 RenderService（改动更大）。

### B. KMS overlay 硬件合成

```text
layer buffers -> DRM overlay planes (2) + primary -> scanout
```

优点：

- 零拷贝、低功耗、没有 IPC。
- 不依赖 glibc GPU runtime。

限制：

- 只有 2 个 overlay plane；桌面/应用层数一多就要回退到 GPU 或 CPU。
- 需要实现 composer 的多平面选择、格式过滤、zpos、缩放和 fallback。
- X5 当前代码在软件合成模式下只使用一个 primary plane；overlay 路径需要重新验证。
- 对透明/混合/旋转等场景能力有限。

适合作为后续优化，而不是第一步。

### C. 保持软件合成

- 当前状态，已能显示 800x480 桌面/锁屏。
- 不作为“硬件合成”验收，但必须保留为回退路径。

## 推荐架构（A 路线的落地形态）

### 集成点

优先改 **Composer VDI**，而不是 RenderService：

1. Composer 已经拿到每个 layer 的 `BufferHandle`（含 dma-buf fd）和 client target。
2. 在 `PrepareDisplayLayers`/`Apply` 之前把“可 GPU 合成”的层打包发给
   `rdkhm_accel`，GPU 把结果写入 client target。
3. Composer 继续用现有 DRM Apply 显示 client target。
4. 任一步失败/超时，回退到现有软件合成。

这样 RenderService 的窗口/图层模型不变，变更集中在
`drivers/peripheral/display/composer`。

### 协议

复用 `rdkhm_accel` 的 socket，新增二进制 `RDKHM_WIRE_COMPOSE`（command 6）。
帧结构定义在 `bringup/probes/accel_wire.h`：

```text
header: magic=RDK1, version=1, command=6, fds=N
request: target fd index, target fence index, target format/size/stride/modifier,
         layer_count, flags
layers[]: fd index, fence fd index, format/size/stride/modifier,
          crop rect, dst rect, alpha, transform, blend
response: status, elapsed_ms, layers；输出 fence fd 随 SCM_RIGHTS 返回
```

约束：

- `RDKHM_WIRE_MAX_FDS=16`，`RDKHM_WIRE_MAX_LAYERS=8`；target 最大 4096x4096。
- fd 全部通过 `SCM_RIGHTS` 传递；daemon 在请求处理完后关闭接收到的 fd。
- 目前 `transform` 必须为 0；未知变换返回 `INVALID_PARAMETER`。
- 每次请求有 10 秒接收超时；输入 fence 等待上限 1 秒。
- 失败返回明确状态，客户端/composer 回退软件合成。

约束：

- fd 全部通过 `SCM_RIGHTS` 传递；接收端负责关闭。
- 单帧 buffer/图层数量、尺寸、stride 上限要校验。
- 每次请求有超时；GPU context 复用，不按帧创建。
- 失败必须返回明确错误码，composer 回退软件合成。

### Buffer / fence

- target 和 layer 使用 OH 现有 dma-buf；BGRA8888 线性布局优先。
- 通过 `EGL_EXT_image_dma_buf_import` 导入为纹理；用
  `glEGLImageTargetTexture2DOES` + FBO 渲染到 target。
- 输入 fence 用 `EGL_ANDROID_native_fence_sync` 等待；输出 fence 用
  `eglDupNativeFenceFDANDROID` 返回。
- 暂不支持 tiled/modifier 时，先拒绝并回退，不要静默画错。
- 需要验证 OH `BufferHandle` 的 format/stride/modifier 与 EGL import 参数映射。

### 显示 / DRM

- GPU 进程只做离屏渲染，不调用 `drmSetMaster`，不改 mode。
- 显示仍由 composer 的 `drmModeAtomicCommit` 完成。
- GPU 进程使用 `card0` 或 `renderD128` 都可验证；优先尝试 render node，
  避免和 composer 的 master/状态冲突。

## 分阶段计划

### P0：离屏双图层合成验证（S，已完成 2026-11-20）

- 探针：`bringup/probes/gpu-compose-test.c`，暂存为 runtime 内的
  `gpu-compose-test`，wrapper 入口 `rdkhm-accelerator --gpu-compose`
  （源码已入库；当前已刷镜像尚未包含，需下次镜像构建或临时推送）。
- 测试方法：64x64 target dma-buf；背景左绿右蓝；32x32 半透明红色前景；
  EGLImage 导入两个 layer，渲染到 target；读回三个采样点；测试
  `EGL_KHR_fence_sync` 和 native fence；记录合成耗时。
- 结果：
  - `dma_buf=1 modifiers=1 fence=1 native_fence=1`
  - FBO complete，shader 编译/链接通过
  - `left=0,255,0,255`，`blend=128,127,0,255`，`right=0,0,255,255`
  - `fence wait=1`，native fence fd 正常
  - `compose_ms=1.5~1.7`（64x64，两层）
  - `GPU_COMPOSE_PASS`
- 限制：GBM 返回的 modifier 是 `0xffffffffffffff`（MOD_INVALID），CPU
  mmap 参考比较被跳过；GPU 读回结果与预期一致。正式接入时需要显式线性
  modifier 或按实际 modifier 导入。
- 证据：`out/board-logs/20261120-gpu/gpu-compose-20261120.log`，源码/二进制
  同目录留档。

验收：已通过。失败时输出 `GPU_COMPOSE_FAIL` 和具体 EGL/GL 错误。

### P1：compose 协议 + GPU 进程实现（M，已完成原型 2026-11-20）

- `accelerator-daemon` 增加 `RDKHM_WIRE_COMPOSE`：最多 8 层、16 个 fd，
  校验 target/layer 尺寸、crop、stride、格式、fd index。
- 首次 compose 时初始化并复用 EGL/GLES/GBM context 和 shader program；
  每帧只用 EGLImage + FBO，不重复建 context。
- 输入 fence 用 `EGL_ANDROID_native_fence_sync` 等待；输出 fence 用
  `eglDupNativeFenceFDANDROID` 通过 SCM_RIGHTS 返回。
- 客户端：`bringup/probes/accel-compose-client.c`，分配 3 个 GBM buffer
  （target/背景/前景），发送 fd 和 layer 描述，等待输出 fence，map target
  对比像素。
- 板端验证（daemon 以 `--socket /data/local/tmp/...` 运行，不依赖镜像）：
  - 第一次 compose：`status=0 layers=2`，输出 fence 正常
  - 第二次 compose 把第一次的输出 fence 作为输入 fence（新连接）：
    `input_fence status=0 layers=2 elapsed=1ms`
  - `fence_ok=1 input_fence_ok=1 pixels_ok=1`
  - `GPU_COMPOSE_WIRE_PASS`
  - daemon 侧：冷启动首帧约 6–7ms，热帧约 1ms（64x64，两层）
- 当前 daemon 是“一连接一帧”模型；P2 接 composer 时需要改成持久连接或连接池。
- 证据：`out/board-logs/20261120-gpu/gpu-compose-wire-20261120.log`。
- 当前已刷镜像里的 daemon 仍是旧版；新 daemon/client 已进入
  `out/accelerator-runtime` 和 `out/driver-bundle`，下次镜像生效。

### P2：Composer 接入（L，源码已完成，未板测）

- 新增 composer 侧客户端 `gpu_compose_client.{h,cpp}`，直接用 musl socket +
  SCM_RIGHTS 调用 `rdkhm_accel`，不加载厂商库。
- `HdiGfxComposition`：当 daemon 支持 `GPU_COMPOSE_CHECK` 且所有层都是
  `COMPOSITION_DEVICE` 时，保留 DEVICE 选择，不让 RenderService CPU 合成；
  否则回退现有 CLIENT 路径。
- `HdiDrmComposition`：在 DRM commit 前把 target（client layer buffer）和
  device layers 发给 daemon，等待输出 fence，再由现有 primary plane 显示。
- 失败处理：`GpuComposeClient::Disable()`，后续 Prepare 自动回退 CLIENT；
  当前失败帧可能显示旧 target。
- 安全条件：层数 ≤ 8、fd ≤ 16、只支持 `ROTATE_NONE`、blend 仅
  NONE/SRC/SRCOVER、BGRA/BGRX 等已映射格式；任何不满足都回退 CPU。
- 顺带修复 `Apply()` 的 `crtcOutFence` 类型：从 `int32_t` 改回 `uint64_t`，
  避免内核写 8 字节 out-fence 覆盖栈。
- 构建：`scripts/build-target.sh
  drivers/peripheral/display/composer/vdi_base:display_composer_vdi_impl_default`
  成功；`check-composer-abi.py` 通过（40 个 mandatory export）。
- 当前限制：
  - 只有“全部 DEVICE”的帧走 GPU；混合 CLIENT 层仍走 CPU。
  - target 目前使用 client layer 的单个 buffer（首帧或 RenderService 提供），
    没有双缓冲，可能有 tearing。
  - daemon 仍是“一连接一帧”，每帧新建连接。
  - GPU 路径尚未在板端 composer 中启用；需要部署新 composer 库和新 daemon。
- 板端验证前需要：新 daemon 进入 `/vendor`、composer 重启、并先解决
  account/hmdfs 冷启动问题。

### P3：性能与验收（L）

- 对比软件合成：CPU 占用、帧时间、功耗、温度。
- 验证无泄漏、无 AVC、无 GPU hang。
- 明确“硬件合成已启用”的日志和计数。
- 保留关闭开关。

## 验收标准

1. 板端 `GPU_COMPOSE_PASS`，输出像素与 CPU 参考一致或在约定阈值内。
2. Composer 实际走 GPU 分支的帧数可统计；失败自动回退。
3. 800x480 桌面/应用场景下，CPU 占用或帧时间有可测量改善。
4. 连续运行至少一轮 soak 无 GPU hang、无 fd/内存泄漏、无新增 AVC。
5. 软件合成回退可用，关闭 GPU 合成后行为与当前镜像一致。

## 风险

- **glibc/musl 边界**：不能把 vendor 库直接链进 OH 进程；必须保持进程隔离。
- **fd/fence 生命周期**：fd 泄漏、双关闭、fence 方向错误都会导致卡死。
- **buffer 布局**：stride/modifier/tiling 不匹配会花屏或渲染错误。
- **DRM master**：GPU 进程不能抢 master；否则 composer 显示会失败。
- **性能**：IPC + dma-buf 导入可能抵消收益；需要实测。
- **厂商二进制**：无源码，ABI/授权边界要单独评估。
- **前置阻塞**：当前镜像冷启动账号激活失败（hmdfs），桌面/HAP 级验收前需要先修复。

## 现在能立即做的

P0/P1 已完成：离屏双图层合成和 socket 协议都在板上通过。下一步 P2：

1. 在 composer VDI 里增加 GPU 合成分支，默认关闭，失败回退软件合成。
2. 把 composer 的 `BufferHandle` fd/stride/format 映射到 `COMPOSE` 请求。
3. 用关开关做 A/B：软件合成 vs GPU 合成，记录帧时间、CPU 占用和像素差异。
4. 当前已刷镜像需要先解决账号/hmdfs 冷启动问题，才能做桌面级验收。
