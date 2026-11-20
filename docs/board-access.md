# RDKHM 板端登录与调试

本文只记录开发访问方式，不保存密码、私钥、API key 或 HDC 认证材料。

## HDC 客户端

主机客户端固定使用：

```sh
source env.sh    # 导出 RDKHM_HDC
HDC=$RDKHM_HDC
$HDC version
$HDC tconn <board-ip>:5555
$HDC list targets
$HDC -t <board-ip>:5555 shell id
```

当前板端应使用 TCP `5555`。IP 由现场 DHCP/网络环境决定，不能硬编码到镜像。

## 板端启动 HDC

通过串口 `ttyS0`、115200 或其他本地 shell 执行：

```sh
param set const.security.developermode.state true
param set persist.hdc.port 5555
param set persist.hdc.mode.tcp enable
service_control start hdcd
```

验证：

```sh
ps -A | grep hdcd
cat /proc/net/tcp | grep 15B3
```

如果服务配置没有启动，可临时运行：

```sh
/system/bin/hdcd -t -l 5 >/data/hdcd.log 2>&1 &
```

`5555` 的十六进制端口是 `15B3`。`adb connect` 不适用于该 HDC TCP 端口。

## USB HDC

产品 init 在 `post-fs-data` 中启动 `rdkhm-usb`。源码中的
`rdkhm-usb.sh` 会先检查 `/proc/mounts`，避免对已经挂载的 `/config`
configfs 重复 mount，并把 `os_desc/b.1` 和 functionfs mount 做成幂等。

USB HDC gadget 标识为 `1d6b:0104`。在接 USB 的主机上应能看到对应的
`lsusb` 条目，`hdc list targets` 也应出现 USB target。

板端检查：

```sh
lsusb
ls -l /dev/usb-ffs/hdc
ls /config/usb_gadget/g1
cat /sys/class/udc/*/state
param get sys.usb.controller
param get sys.usb.configfs
```

2026-11-19 20:54 的统一构建镜像（kernel #6）冷启动后，
`/config/usb_gadget/g1`、`/dev/usb-ffs/hdc/ep0..ep2`、UDC `configured`
和 hdcd 的 USB endpoint 均已在没有手动执行脚本的情况下就绪。
构建主机没有枚举到该 USB gadget，主机侧结果需要在物理连接板子的 PC 上确认。
详见 [board-validation-20261119.md](board-validation-20261119.md)。

## SSH

当前镜像没有配置可依赖的 SSH 服务。曾经测试过 `22` 端口被拒绝或超时，因此登录流程应以串口和 HDC 为准。

## 常用只读命令

```sh
hdc -t TARGET shell 'uptime; date; uname -a; cat /proc/sys/kernel/random/boot_id'
hdc -t TARGET shell '/rdkhm/hdmi-status.sh'
hdc -t TARGET shell '/rdkhm/touch-status.sh'
hdc -t TARGET shell '/rdkhm/camera-codec-status.sh'
hdc -t TARGET shell '/rdkhm/system-security-status.sh'
hdc -t TARGET shell '/rdkhm/screen-status.sh'
hdc -t TARGET shell '/rdkhm/screen-status.sh --capture'   # 会唤醒屏幕并写截图/布局
hdc -t TARGET shell 'cat /data/rdkhm-logs/boot-status.txt'
hdc -t TARGET file recv /data/rdkhm-logs/hilog-current.txt ./hilog-current.txt
```

完整采集：

```sh
bash scripts/collect-board-logs.sh <board-ip>:5555
```

采集和部署脚本现在必须显式传入 `target:port`，不再使用历史默认 IP。
`scripts/deploy-composer-fix.sh` 默认只打印计划，`--apply` 才会替换 composer
库并重启服务；使用前必须有串口保底。
脚本输出到 `out/board-logs/<timestamp>/`，包含 boot id、内核日志、hilog、进程、挂载、显示、触摸、设备、网络、服务、窗口和屏幕信息。

## 失联排查顺序

1. 串口确认系统是否仍在运行。
2. 检查 `ps -A | grep hdcd` 和 `cat /proc/net/tcp | grep 15B3`。
3. 检查 `ip addr`、默认路由和网线/Wi-Fi 状态。
4. 确认当前 IP，不要假设历史地址仍有效。
5. 先恢复 HDC，再做任何驱动加载；不要在无串口保底时加载 WS73 模块。

## 安全边界

板测默认只读。禁止在没有明确批准和串口保底的情况下执行刷盘、重启、`smode`、模块加载、网络切换或服务替换。任何密钥应通过本机权限文件或外部密码管理器提供，不写入本文档和镜像。
