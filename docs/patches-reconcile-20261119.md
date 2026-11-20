# Patch 去重 / reconcile — 2026-11-19

本页是对 `out/patch-*` 历史快照和 `.claude` 历史会话的只读 reconcile。
**没有修改 active `patches/`，没有改 manifest，没有编译镜像。**

## 结论

- active 构建集：**106 个 patch 文件**
  - 103 个 manifest 显式列出
  - 3 个 glob（`nearlink-bsp` 2 + `nearlink-ssap` 1）
- `out/patch-*`：**248 个 patch 文件（200+ 的来源）**
  - `patch-backup-20261119-152919`：73
  - `patch-backup-20261119-154609`：77
  - `patch-normalized`：88
  - `patch-reheader`：10
- 248 个文件去重后只有 **165 个唯一内容哈希**；其中：
  - 82 个内容在 active 中存在
  - **83 个是旧版本/重复内容**
  - **24 个 active 新内容不在这些备份中**
  - **76 个相同相对路径存在内容差异**（多为 active 的新版本）
- 因此“200 多个”是**历史快照文件数**，不是 106 之外的 200 个有效新 patch。
- active + 备份的相对路径并集是 **119**；没有发现另外 100 个未纳入的独立 patch。
- 另有 `out/reconcile` 7 个、`out/tmp-fresh-check` 8 个扁平化/临时副本，未计入
  上面的 248；它们同样是重复/临时产物，不是独立 patch 集。

## 备份中相对 active 缺失的语义 patch

按路径比较，只有 3 个旧命名不在 active：

| 备份旧 patch | 当前 canonical patch | 处理 |
| --- | --- | --- |
| `notes/0001-resource-completion.patch` | `haps/notes-resources.patch` | 旧命名，已被 canonical 替代 |
| `contacts/0001-arkts-compat-worker-ets.patch` | `haps/contacts-arkts-worker-migration.patch` | 旧命名，已被 canonical 替代 |
| `mms/0001-arkts-compat-worker-ets.patch` | `haps/mms-arkts-worker-migration.patch` | 旧命名，已被 canonical 替代 |

除此之外，`patch-backup-*` 中大量路径与 active 同名但内容不同，属于旧的
reheader/normalized 快照，不应整体覆盖 active。

## 历史会话扫描

本机 `.claude/projects/-home-robo-rdkhm`：

- 94 个 `.jsonl`，其中 5 个顶层会话（`ab45…`、`06a2…`、`7c049…`、
  `7960…`、`ead…`），其余为 subagent 日志。
- 会话中出现的 patch 引用：103 个唯一路径；其中 68 个与 active/备份相同，
  8 个只在 active，27 个是旧路径/临时路径。
- 未发现 8 个独立顶层会话目录；如果另外 8 个 AI 在其它机器或目录，
  本机日志没有覆盖，需提供路径。

27 个未匹配引用主要归为：

- `x5-kernel/*` → 已迁到 `kernel/*`
- `hdf-core/...` → 已迁到 `kernel/hdf-core/...`
- `settings/0002-nearlink-settings-page.patch` → 当前 `settings/0003-...`
- `call/0001-arkts-compat-and-scope-fixes.patch` → 当前 `call/0001-strict-null.patch`
- `haps/0001-build-config-upgrades.patch`、`haps/0001-hvigor-configs.patch`、
  `launcher/0003-hvigor-*` → 早期 build/hvigor 临时补丁
- `nearlink-bsp/0002-oal-print.patch`、`nearlink-bsp/0002-pm-open-debug.patch`
  → 早期调试 print patch，未进入 active
- `display/0099.patch`、`display/xyz.patch` → 会话中的示例/占位名

这些不是可直接合并的独立功能 patch；若要恢复其中某一项，需要从会话记录或
对应源码重新生成，而不是把旧快照批量拷回。

## 建议

1. 以 active 106 为构建基线；不整体合并 248 个备份。
2. 保留 3 个旧命名到 canonical 的映射；不再添加重复文件。
3. 如果确实存在另外 8 个 AI 的 patch 目录，请给出路径/主机；当前本机只有
   5 个顶层会话和 `out/patch-*` 四套快照。
4. 任何“恢复”动作先做内容 diff、干净 worktree apply 和 `./rdkhm check`，
   再决定是否进 manifest；当前未做任何 active 修改。

## 数据

- `out/reconcile-20261119/out-patch-dedup.json`
- `out/reconcile-20261119/session-refs.json`
