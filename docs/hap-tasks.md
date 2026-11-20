# HAP 构建任务拆分

更新时间：2026-11-19

## 目标与基线

- 目标：`applications/standard` 下 22 个 HAP 源码工程全部能构建、签名并产出 HAP。
- 当前结果：**22/22 构建成功**；自 2026-11-19 起所有 HAP 统一使用官方
  OpenHarmony release key 签名，见 [hap-signing.md](hap-signing.md)。
- 统一入口：`./build hap <app> --force`
- 并行子集：`./build hap --all --force --jobs 2 --only settings,launcher,photos`
- 镜像构建的 `haps` stage 现在构建 `config/build/haps.json` 中 `image.apps`
  的全部 app，加上 SystemUI modules 和 PinTool；`image_haps.py --check`
  仍是镜像组装前的硬门禁
- 并行构建：`./build hap --all --force --jobs 2`（默认 1，保持串行；建议从 2 开始）
- 产物：`out/haps/<app>.hap`（已签名）
- 构建日志：`out/logs/build-hap-<app>.log`
- 签名日志：`out/logs/sign-hap-<app>.log`
- 注册表：`config/build/haps.json`
- patch 目录：`patches/haps/`
- patch 清单：`config/patches.json`
- notes/contacts/mms 的补丁已统一为 `patches/haps/` 下的 canonical 文件，
  `patches/notes/`、`patches/contacts/`、`patches/mms/` 已移除，避免重复应用

已构建（22）：

```
admin_provisioning  applications_auth_widget  calendardata  call
camera  contacts  dlp_manager  filepicker  launcher  mms  notes
permission_manager  photos  printspooler  screenlock  screenshot
security_privacy_center  settings  settings_data  systemui  theme
user_certificate_manager
```

板端已安装（2）：

```
contacts  mms
```

历史记录：contacts/mms 曾使用 `contacts/sign/`、`mms/signs/` 里的厂商 CA
材料签名。该策略已于 2026-11-19 废止；现在统一由 `build-hap.py` 使用官方
release key 重签，见 [hap-signing.md](hap-signing.md)。

## 通用规则

1. 只构建 HAP，不构建镜像、不刷板、不连接板卡。
2. 构建前由 `scripts/build-hap.py` 自动处理：
   - 创建/升级 `hvigor/hvigor-config.json5`
   - 升级 `build-profile.json5` 的 SDK level
   - 补全 `oh-package.json5` 的 `modelVersion`
   - 生成 `local.properties`
   - 生成 `out/sdk/openharmony-20` 新 SDK 布局
   - 构建后用 `hap-sign-tool.jar` 签名
3. 并行任务期间，`apply-patches.py --dry-run --only openharmony` 可能因其他人尚未完成的 patch（例如 `call/mobiledatasettings`）失败。这不能作为某个 app patch 的判断依据；单个 patch 用：
   ```sh
   git -C <repo> apply --reverse --check --ignore-whitespace <patch>
   git -C <repo> apply --check --ignore-whitespace <patch>
   ```
4. patch 只记录手工修改，不要包含：
   - `hvigor/hvigor-config.json5`（自动生成）
   - `local.properties`（机器相关）
   - `.hvigor/`、`oh_modules/`、`build/`（生成物）
   - 自动升级产生的 `oh-package.json5` / `build-profile.json5` SDK 字段
4. 每个任务完成标准：
   - `./build hap <app> --force` 成功
   - `out/haps/<app>.hap` 存在
   - 手工修改已生成 patch 并加入 `config/patches.json`
   - `python3 scripts/check-patch-coverage.py` 通过
   - `./rdkhm check` 通过

## 任务总表

| ID | 任务 | 难度 | 优先级 | 当前日志 |
| --- | --- | --- | --- | --- |
| T1 | notes 资源补全 | S | P0 | `out/logs/build-hap-notes.log` |
| T2 | printspooler 本地 HAR | M | P0 | `out/logs/build-hap-printspooler.log` |
| T3 | admin_provisioning 00308018 | M | P1 | `out/logs/build-hap-admin_provisioning.log` |
| T4 | theme 00308018 | M | P1 | `out/logs/build-hap-theme.log` |
| T5 | call strict-null | M | P1 | `out/logs/build-hap-call.log` |
| T6 | photos 资源 + ArkTS | L | P2 | `out/logs/build-hap-photos.log` |
| T7 | camera ArkTS | L | P2 | `out/logs/build-hap-camera.log` |
| T8 | contacts TS/ArkTS | L | P3 | `out/logs/build-hap-contacts.log` |
| T9 | mms TS/ArkTS | L | P3 | `out/logs/build-hap-mms.log` |
| T10 | systemui 资源类型 | M | P2 | `out/logs/build-hap-systemui.log` |
| T11 | 固化已有手工修复 patch | S | P1 | — |
| T12 | `out/haps` 接入镜像 | M | P2 | — |
| T13 | 板端安装/启动验证 | M | P3 | — |

---

## T1 notes 资源补全（S）

工程：`sources/oh/openharmony-full/applications/standard/notes`

状态：✅ 构建成功。

- HAP：`out/haps/notes.hap`
- patch：`patches/haps/notes-resources.patch`
- 修复内容：产品目录合并 `color_1`、完整 color/string、`float.json`、77 个
  media 资源，并补 5 个 permission 的 base 字符串；`base` 不再有缺资源警告

当前首个错误：

```
Unknown resource name '$color:color_1'
```

已知缺失资源示例：

```
$media:note
$color:color_1
divider_color_182431
notecontent_color_ffffff
```

做法：

1. 从 `out/logs/build-hap-notes.log` 提取所有 `Unknown resource` / `not defined`。
2. 在以下位置找同名资源：
   - `notes/common/resources/src/main/resources/base/`
   - `notes/common/resources/src/main/resources/dark/`
   - 其他 locale/qualifier 目录
3. 合并到 `notes/product/default/src/main/resources/` 对应目录。
4. 注意不要覆盖已有同名但语义不同的资源。
5. 若资源依赖未生效，检查 `notes/product/default/oh-package.json5` 的 `@ohos/source` 依赖。

验收：

```sh
./build hap notes --force
test -f out/haps/notes.hap
```

然后生成 patch。

---

## T2 printspooler 本地 HAR（M）

工程：`sources/oh/openharmony-full/applications/standard/printspooler`

当前错误：

```
Cannot find module '@ohos/ippprint' or its corresponding type declarations
```

相关文件：

- `printspooler/entry/oh-package.json5` 依赖 `file:../feature/ippPrint`
- `printspooler/feature/ippPrint/src/main/module.json5`：`"type": "har"`
- `printspooler/feature/ippPrint/oh-package.json5`：`"types": ""`、`"main": "index.ts"`

排查步骤：

1. 先确认本地 HAR 能单独构建：

   ```sh
   cd sources/oh/openharmony-full/applications/standard/printspooler/feature/ippPrint
   /home/robo/rdkhm/thirdparty/toolchains/command-line-tools-26/command-line-tools/bin/hvigorw \
     assembleHar --mode module -p product=default --no-daemon --stacktrace
   ```

2. 查找生成的 `.har` / `index.d.ts`。
3. 检查 `entry` 编译时是否把该 HAR 加入依赖闭包。
4. 必要时调整：
   - `feature/ippPrint/oh-package.json5` 的 `types`/`main`
   - `printspooler/build-profile.json5` 中 `ippPrint` 的 targets/applyToProducts
   - `entry/oh-package.json5` 的依赖路径

验收：

```sh
./build hap printspooler --force
test -f out/haps/printspooler.hap
```

---

## T3 admin_provisioning 00308018（M）

工程：`sources/oh/openharmony-full/applications/standard/admin_provisioning`

当前错误：

```
Error Code: 00308018 Unknown Error
The "data" argument must be of type string ... Received undefined
```

已尝试：

- 创建 root `oh-package.json5`
- 去掉 product 中无效的 `signingConfig`

排查：

1. 查看 `.hvigor/outputs/build-logs/` 细节。
2. 用 `--stacktrace --debug` 重跑 hvigorw。
3. 对比可构建工程（如 `settings`）的：
   - `AppScope/app.json5`
   - `build-profile.json5`
   - `entry/module.json5`
   - `entry/build-profile.json5`
4. 重点检查 `signingConfigs`、`srcEntry`、abilities、resources。

验收：

```sh
./build hap admin_provisioning --force
test -f out/haps/admin_provisioning.hap
```

---

## T4 theme 00308018（M）

工程：`sources/oh/openharmony-full/applications/standard/theme`

状态：✅ 已完成。

- 产物：`out/haps/theme.hap`（119K，已签名）
- patch：`patches/haps/theme-build-config.patch`
- 验证：`apply --reverse --check --ignore-whitespace` 通过
- 已修复：模块名下划线、app 级 SDK 移入 product、去掉 `arkEnable`、去掉无效 `signingConfig`

注意：`apply-patches.py --dry-run --only openharmony` 的并行失败与 theme 无关；theme 按单个 patch 验证。

---

## T5 call strict-null（M）

工程：`sources/oh/openharmony-full/applications/standard/call`

当前阶段：配置已通过，ArkTS 编译有 90 个错误，典型：

```
Object is possibly 'null' / 'undefined'
Type 'Resource | null' is not assignable to type 'Resource'
```

集中在：

- `mobiledatasettings/src/main/ets/pages/apnDetail.ets`
- 以及其他页面

做法：

1. 先从日志按文件聚合错误。
2. 确认 `buildOption.strictMode` 是否支持关闭 strict null；不支持就逐文件补判空或 `!`。
3. 优先生命周期短、影响面小的页面。

验收：

```sh
./build hap call --force
test -f out/haps/call.hap
```

---

## T6 photos（L）

状态：✅ 构建成功。

- HAP：`out/haps/photos.hap`（约 11.6M）
- patch：`patches/photos/0001-photos-resources.patch`
- 已做：补 `form_FormAbility_label`、合并 `photos/common/src/main/resources/base`
- 根因：缺 `oh_modules`，`@ohos/common`、`@ohos/browser` 等本地依赖未解析；
  `ohpm install --all` 后 153 个错误全部消失，不需要改 ArkTS 代码
- 构建：`./build hap photos`（`config/build/haps.json` 已标记 `verified: true`）

---

## T7 camera（L）

状态：构建成功；板端已验证到真实 USB camera 预览；控制栏/快门布局和拍照保存
仍未完成。当前详情以
[camera-media-photos-20261119.md](camera-media-photos-20261119.md) 为准。

- HAP：`out/haps/camera.hap`（约 0.97M）
  - SHA256：`b4895d43766d6f9b9590564009e9dea3e4aecfead6371ed270630110eaf506f5`
- patch：
  - `patches/haps/camera-build-config.patch`
  - `patches/camera/0001-lazy-save-asset.patch`
  - `patches/camera/0002-vdi-basic-stream-config.patch`
  - `patches/camera/0003-init-race.patch`
  - `patches/camera/0004-bringup-permission-gate.patch`
  - `patches/camera/0005-open-without-await.patch`
  - `patches/camera/0006-session-commit-timeout.patch`
- 构建：`./build hap camera`（无 `--force`）
- 板端：`bm install -p /data/local/tmp/camera-initrace.hap` 成功；进程存活，不再出现
  `LIFECYCLE_TIMEOUT`
- freeze 根因：`CameraService` 字段初始化时 `new SaveCameraAsset()`，构造中同步
  `UserFileManager.getUserFileMgr()` → DataShare/MediaLibrary，卡在
  `Executor::Stop`，主线程阻塞约 8s
- VDI 修复：USB V4L2 VDI 原来只写入一个 `RGBA_8888` 字节作为 basic config；
  改为按实际 UVC 格式生成 `[format,width,height]` 三元组
  - 板端 `Basic Stream Info Size` 从 0 变为 26
  - 热更新 `/vendor/lib64/libusb_camera_device_manager.z.so`，sha256
    `3abcf2efb3048b189c16705b1bcd5eec512320aea2f5ac58a6a5ae425d41afed`
  - 原库备份：`/data/rdkhm-fixes/camera-vdi-20261119-181431/original.z.so`
- 前台被抢占：`com.rdkhm.pintool` 和 SystemUI 控制中心会把 camera 在约 1.3s 内切到
  BACKGROUND；发 `Home` 键关闭控制中心后 camera 能保持 FOREGROUND
- 当前阻塞：camera 前台时 camera_service 为 1 active、0 session；app 日志没有
  `XComponent_onLoad` / `startPreview`，抓屏只有系统状态栏/导航栏，页面内容全黑。
  Launcher 抓屏正常，说明不是全局显示合成坏了，而是 camera 页面的
  XComponent/ArkUI 内容没有呈现；`camera0` surface 可能是旧进程残留
- 下一步：查 `XComponent` 在 800x480 下的 surface/onLoad，以及 camera 页面的布局
  （footBarHeight 906 等 phone 布局在横屏上的适配）
- 仍有编译告警（private property 初始化、`ButtonType` 等），不影响产物

---

## T8 contacts（L）

工程：`sources/oh/openharmony-full/applications/standard/contacts`

状态：✅ 构建成功。

- HAP：`out/haps/contacts.hap`（1.7M）
- patch：`patches/haps/contacts-arkts-worker-migration.patch`
- 签名：历史记录为厂商 CA；2026-11-19 起统一官方 release key（需重新构建，见 [hap-signing.md](hap-signing.md)）

原错误（已修复）：

```
Importing ArkTS files in JS and TS files is forbidden
At .../entry/src/main/ets/workers/base/Worker.ts
```

关键修复：

- `entry/src/main/module.json5` 增加
  `Api11ArkTSCheckMode = DoArkTSCheckInCompatibleModeInApi11`，把 1460 个
  严格 ArkTS 规则错误降到 43 个 TS→ArkTS 互操作错误；
- 剩余 13 个 `.ts` 迁为 `.ets`，同步 `module.json5` 的 `srcEntry`、
  `entry/build-profile.json5` 的 workers 和 `ThreadWorker` 路径；
- `AppScope/app.json5` 增加 `"singleton": true`。

---

## T9 mms（L）

工程：`sources/oh/openharmony-full/applications/standard/mms`

状态：✅ 构建成功。

- HAP：`out/haps/mms.hap`（1.4M）
- patch：`patches/haps/mms-arkts-worker-migration.patch`
- 签名：历史记录为厂商 CA；2026-11-19 起统一官方 release key（需重新构建，见 [hap-signing.md](hap-signing.md)）

关键修复：

- 与 T8 相同的 `Api11ArkTSCheckMode` 兼容模式；
- 7 个 `.ts` 迁为 `.ets`，同步 `srcEntry` / `srcEntrance` / workers /
  `ThreadWorker` 路径；
- 修复 `conversationController.ets` 的 `returen;` 拼写错误为 `return;`；
- `AppScope/app.json5` 增加 `"singleton": true`。

---

## T10 systemui（M）

工程：`sources/oh/openharmony-full/applications/standard/systemui`

现状：25 个资源类型错误，典型：

```
Unknown resource type 'color' / 'float'
features/volumepanelcomponent/src/main/ets/com/ohos/common/StyleConfiguration.ts
```

做法：

1. 按系统资源引用规则改 `$r('app.color...')` / `$r('sys.color...')`。
2. 优先 volumepanel、statusbar 组件。
3. 再跑全量编译。

---

## T11 固化已有手工修复为 patch（S）

状态：✅ 已完成。

已生成并接入 `config/patches.json`：

```
patches/haps/admin_provisioning-build-config.patch
patches/haps/applications_auth_widget-null-guards.patch
patches/haps/call-build-config.patch
patches/haps/camera-build-config.patch
patches/haps/printspooler-build-config.patch
patches/haps/systemui-build-config.patch
patches/haps/theme-build-config.patch
patches/haps/notes-resources.patch
patches/haps/contacts-arkts-worker-migration.patch
patches/haps/mms-arkts-worker-migration.patch
patches/photos/0001-photos-resources.patch
patches/call/0001-strict-null.patch
```

验证：

- `check-patch-format.py`：0 failure
- `check-patch-coverage.py`：PASS
- `./rdkhm check`：通过
- notes / contacts / mms 三个 canonical patch 均在干净 HEAD worktree 上
  `git apply --check` 通过，应用结果与当前工作树逐文件一致

历史：contacts 曾使用 `contacts/sign/`、mms 曾使用 `mms/signs/` 的厂商 CA
材料，由 hvigor 自动签名。2026-11-19 起已废止，统一改用官方 release key，
见 [hap-signing.md](hap-signing.md)。

生成 patch：

```sh
git -C sources/oh/openharmony-full/applications/standard/<app> diff --binary -- <files> \
  > patches/haps/<app>-<desc>.patch
```

接入 `config/patches.json` 的 `openharmony` collection，然后：

```sh
python3 scripts/apply-patches.py --record
python3 scripts/check-patch-coverage.py
./rdkhm check
```

---

## T12 `out/haps` 接入镜像（M）

状态：完成（代码侧）。统一清单在 `config/build/haps.json` 的 `image` 段，
由 `scripts/image_haps.py` 解析，镜像组装和校验共用同一份映射：

- 普通应用：`out/haps/<app>.hap` → `/system/app/<bundle>/<HapName>`
- Settings：优先 `out/settings/Settings.hap`，回退 `out/haps/settings.hap`
- SystemUI：`out/haps/systemui/<Module>.hap` → `/system/app/com.ohos.systemui/<Module>.hap`
- ScreenLock：`out/haps/screenlock.hap` → `.../SystemUI-ScreenLock.hap`
- PinTool：`out/haps/rdkhm_pintool.hap` 存在时注入，不存在则跳过

已接入 contacts/mms/call/filepicker 等全部有明确上游目录的构建产物。
未接入：admin_provisioning（镜像无对应目录）、theme（无对应 bundle 目录）、
permission_manager（当前只构建 feature 模块）、user_certificate_manager
（bundle 目录名不一致）。

缺失必需 HAP 时镜像组装直接失败，不再静默保留旧预置版本。
verifier 校验每个注入 HAP 的 ZIP 完整性（`module.json`、CRC）和文件一致性。

签名判定：注入的 HAP 必须由官方 release key 签名，或与
`install_list_capability.json` / `install_list_permissions.json` 中该 bundle 的
`app_signature` 一致（`check-hap-signatures.py --accept-allowlist`）。
当前 contacts/mms/callui/filepicker 和 camera 走 allowlist 分支，
其余走官方 release key；两者都不满足时镜像校验失败。

目标：

1. 将 `out/haps/<app>.hap` 映射到对应 bundle 的 `/system/app/com.ohos.*/`
2. 保留 Settings 的特殊处理
3. verifier 校验每个注入 HAP 的来源和 ZIP 完整性

验收：

```sh
./rdkhm package
python3 scripts/verify-openharmony-image.py
```

不刷板。

---

## T13 板端验证（M）

前置：T12 完成并得到镜像，或有可用 HDC。

状态：✅ contacts/mms 已安装到板端。

板卡：

```
10.43.9.213:5555   RDK-X5
boot_id 49dd3d69-3264-446e-80f7-aa67193d9af9
```

已安装：

```
com.ohos.contacts  /data/app/el1/bundle/public/com.ohos.contacts/entry.hap
  sha256 11de27c45f296f7130fb82745657147b5a231efc9f92b4c009acf2a953a64546

com.ohos.mms       /data/app/el1/bundle/public/com.ohos.mms/entry.hap
  sha256 d4b567846d56ca66b8464152d6b392482815d7670a7f3384d88c60e282cc3a4c
```

关键发现（历史记录；当前签名策略已改为统一官方 release key）：

- contacts/mms 的构建配置自带签名材料：
  - `applications/standard/contacts/sign/IDE.cer` + `OpenHarmony_stage.p12` + `contacts.p7b`
  - `applications/standard/mms/signs/IDE.cer` + `OpenHarmony.p12` + `com.ohos.mms.p7b`
- `IDE.cer` 指纹正是厂商 CA `04AC...`，hvigor 会自动用它签名
- 之前手工用 test key 重签覆盖了正确签名，导致 `install sign info inconsistent`
- 改为直接使用 hvigor 产物后，`bm install -p ... -u 0 -r` 成功

证据：

```
out/board-logs/hap-install-20261119/
  SHA256SUMS
  verify.txt
  install_list_capability.json   # 已恢复原样
  uninstall_list.json            # 已恢复原样
```

注意：按 `AGENTS.md`，刷写、重启、板端服务替换必须先获得明确批准，并准备串口。

注意：按 `AGENTS.md`，刷写、重启、板端服务替换必须先获得明确批准，并准备串口。

---

## 建议分派

| 小组 | 任务 |
| --- | --- |
| A（配置/资源） | T1、T2、T3、T4、T11 |
| B（ArkTS 中等） | T5、T10 |
| C（源码迁移） | T6、T7、T8、T9 |
| D（集成/验证） | T12、T13 |

依赖关系：

- T11 依赖 T1–T5 的阶段性成果。
- T12 依赖已成功的 HAP。
- T13 依赖 T12 和板卡访问批准。

## 命令速查

```sh
./build hap --list
./build hap --all --force
./build hap <app> --force
./build hap <app> --force --no-sign

tail -n 50 out/logs/build-hap-<app>.log
tail -n 20 out/logs/sign-hap-<app>.log

./rdkhm check
python3 scripts/check-patch-coverage.py
```
