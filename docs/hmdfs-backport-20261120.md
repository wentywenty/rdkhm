# HMDFS 6.6 -> X5 6.1.83 backport

## 结论

源码已编译出 `hmdfs.ko`，并已放入 driver bundle 的 autoload 列表。  
但当前已刷板端内核仍是旧 `Image`（不带 `filemap_remove_folio` export），
`insmod` 失败：

```text
hmdfs: Unknown symbol filemap_remove_folio (err -2)
insmod: failed ... No such file or directory
```

因此 **还没有完成板端 mount/account 验证**。需要先用新内核 Image 启动板卡。

## 源码位置

```text
sources/rdk/x5-kernel/fs/hmdfs
```

来源：

```text
sources/oh/openharmony-full/kernel/linux/linux-6.6/fs/hmdfs
```

## 接入

- `fs/Kconfig`:
  ```text
  source "fs/hmdfs/Kconfig"
  ```
- `fs/Makefile`:
  ```text
  obj-$(CONFIG_HMDFS_FS) += hmdfs/
  ```
- `config/kernel/openharmony-base.config`:
  ```text
  CONFIG_HMDFS_FS=m
  CONFIG_HMDFS_FS_PERMISSION=y
  ```
- `config/kernel/modules.json`:
  ```json
  "autoload": ["hmdfs", ...]
  ```

`hmdfs` 放在 autoload 第一位，确保 StorageDaemon 启动前加载。

## 6.6 -> 6.1.83 API 适配

已处理：

- `struct mnt_idmap *idmap` -> `struct user_namespace *mnt_userns`
- `nop_mnt_idmap` -> `init_user_ns`
- `rename_data.old/new_mnt_idmap` -> `old/new_mnt_userns`
- `inode->__i_ctime` -> `inode->i_ctime`
- `#include <linux/filelock.h>` -> `linux/fs.h`（6.1 没有独立 filelock.h）
- `is_dot_dotdot()`：增加 hmdfs 本地 `hmdfs_is_dot_dotdot()`
- `kernel_tmpfile_open()` -> `vfs_tmpfile_open()`
- AEAD 回调签名 -> `struct crypto_async_request *`
- `copy_splice_read` -> `generic_file_splice_read`
- `__lookup_nosensitive()`：加 `__maybe_unused`
- 导出 `filemap_remove_folio()`（`mm/filemap.c`，`EXPORT_SYMBOL_GPL`）

## 构建结果

```text
out/kernel/obj/fs/hmdfs/hmdfs.ko
vermagic: 6.1.83-rdkhm SMP preempt mod_unload aarch64
```

```text
out/driver-bundle/lib/modules/6.1.83-rdkhm/hmdfs.ko
out/driver-bundle/lib/modules/6.1.83-rdkhm/modules.load
```

新内核 Image：

```text
out/kernel/obj/arch/arm64/boot/Image
```

`nm vmlinux | grep filemap_remove_folio` 已能看到导出符号。

## 板端当前结果

对当前已刷板端直接 `insmod`：

```text
hmdfs: Unknown symbol filemap_remove_folio (err -2)
```

原因：当前板端内核是旧的，新 Image 尚未刷入。  
这不是 HMDFS 源码编译错误，而是新内核 export 还未生效。

## 下一步

1. 需要用户确认后，构建/刷写一版带新内核和 driver bundle 的测试镜像。
2. 测试镜像必须让 `const.distributed_file_property.enabled=true`，
   才能实际走 hmdfs 路径；当前源码中的
   `dfs/0001-disable-hmdfs-for-bringup.patch` 是关闭 hmdfs 的保底方案。
3. 板端验证：
   ```text
   lsmod | grep hmdfs
   cat /proc/filesystems | grep hmdfs
   mount -t hmdfs ...
   bootevent.account.ready=true
   BMS 当前用户 = 100
   Launcher 启动
   ```

## 相关 patch / 配置

- `patches/kernel/0019-hmdfs-backport.patch`
- `config/kernel/openharmony-base.config`
- `config/kernel/modules.json`

测试计划和板端验收项见 [hmdfs-testing-20261120.md](hmdfs-testing-20261120.md)。
