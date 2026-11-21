# 全系统详细测试用例

配套文档：[全系统测试计划](system-test-plan-20261120.md)  
记录日期：2026-11-20。  
本文把测试计划展开到“命令、步骤、预期日志、失败判据、证据”级别。

## 0. 执行约定

### 0.1 变量

主机侧建议先定义：

```bash
BOARD=10.43.9.213:5555
HDC=hdc
HOSTLOG=$PWD/out/board-logs/$(date +%Y%m%d-%H%M%S)
mkdir -p "$HOSTLOG"
```

板端：

```bash
LOGDIR=/data/rdkhm-logs
```

### 0.2 结果标记

```text
PASS        功能完成，证据齐全
PARTIAL     枚举/部分场景通过，完整功能未通过
FAIL        已复现失败
BLOCKED     前置条件不满足，无法开始
UNVERIFIED  尚未执行
N/A         当前平台未集成
```

### 0.3 只读和受控操作

- 只读：`cat`、`ls`、`ps`、`dmesg`、`hilog`、`param get`、`bm dump`、
  `/rdkhm/*status*.sh`。
- 受控：打开设备、`insmod`、`ip link up`、`wpa_supplicant`、`hciattach`、
  `arecord`、`aplay`、`v4l2-ctl`、`can0 up`、GPIO export/set。
- 高风险：刷写、重启、改分区、改 SELinux、改网络默认路由。

受控操作前必须记录当前状态，操作后必须恢复。

### 0.4 每次测试必须记录

```text
case id:
result: PASS/PARTIAL/FAIL/BLOCKED/UNVERIFIED
boot_id:
kernel:
image sha256:
param enabled:
time:
command:
expected:
actual:
evidence:
notes:
```

## 1. 镜像与启动前检查

### IMG-01 镜像身份

**类型**：L0 离线  
**目的**：确认测试对象不是旧镜像。

主机：

```bash
cd /home/robo/rdkhm
sha256sum out/images/rdkhm-x5-openharmony-dev.img
cat out/images/rdkhm-x5-openharmony-dev.img.sha256
stat -c '%y %s %n' out/images/rdkhm-x5-openharmony-dev.img
cat out/images/rdkhm-x5-openharmony-dev.partitions.json
```

预期：

```text
两个 SHA256 完全一致
分區表为 DOS，4 个分区
system 起始 532480，vendor 起始 9445376
```

记录到 `HOSTLOG/image.txt`。

### IMG-02 镜像内 kernel

**目的**：避免“新镜像带旧 kernel”。

```bash
dd if=out/images/rdkhm-x5-openharmony-dev.img \
   of=/tmp/test-system.img bs=512 skip=532480 count=8912896
debugfs -R 'dump /boot/Image /tmp/test-Image' /tmp/test-system.img
sha256sum /tmp/test-Image out/kernel/obj/arch/arm64/boot/Image
```

预期：

```text
SHA256 一致
```

同时确认：

```bash
debugfs -R 'ls -l /boot' /tmp/test-system.img
```

### IMG-03 镜像内 HMDFS 和参数

```bash
dd if=out/images/rdkhm-x5-openharmony-dev.img \
   of=/tmp/test-vendor.img bs=512 skip=9445376 count=1048576
debugfs -R 'dump /system/etc/param/distributed_file.para /tmp/param' /tmp/test-system.img
debugfs -R 'ls -l /lib/modules/6.1.83-rdkhm' /tmp/test-vendor.img
debugfs -R 'dump /lib/modules/6.1.83-rdkhm/modules.load /tmp/modules.load' /tmp/test-vendor.img
debugfs -R 'dump /lib/modules/6.1.83-rdkhm/hmdfs.ko /tmp/hmdfs.ko' /tmp/test-vendor.img
modinfo /tmp/hmdfs.ko
```

HMDFS 专项镜像预期：

```text
param 中 enabled=true
modules.load 第一行是 hmdfs.ko
hmdfs.ko vermagic=6.1.83-rdkhm ...
```

保底镜像预期：

```text
param 中 enabled=false
```

### IMG-04 离线 verifier

```bash
python3 scripts/verify-openharmony-image.py
```

预期：

```text
PASS: MBR、checksum、filesystems、artifact comparisons
```

失败时不能直接板测；先确认是否并发 build 改了 packages。

## 2. 冷启动与系统基线

### SYS-01 冷启动

**类型**：L3  
**前置**：已确认镜像 SHA，已获准刷写/重启。

步骤：

1. 刷写或切换镜像。
2. 串口/HDC 连接。
3. 启动后等待 30–60 秒。
4. 采集：

```bash
cat /proc/sys/kernel/random/boot_id
uname -a
cat /proc/cmdline
cat /proc/uptime
dmesg
hilog -x
ps -A
```

预期：

```text
无 kernel panic
关键服务：init、appspawn、samgr、render_service、hdcd、systemui、launcher
无反复 crash/restart
```

失败判据：

```text
Kernel panic
init 起不来
关键服务反复退出
HDC 完全不可用
```

证据：

```bash
$HDC -t "$BOARD" shell dmesg > "$HOSTLOG/dmesg.txt"
$HDC -t "$BOARD" shell hilog -x > "$HOSTLOG/hilog.txt"
$HDC -t "$BOARD" shell ps -A > "$HOSTLOG/ps.txt"
```

### SYS-02 账号和 BMS

```bash
param get bootevent.account.ready
param get const.distributed_file_property.enabled
bm dump -a
```

预期：

```text
account.ready=true
当前用户=100（不是 -2）
bm dump 能看到 system/app 下的应用
```

失败时采集：

```bash
dmesg | grep -iE 'StorageDaemon|StartUser|HmdfsMount|account'
hilog -x | grep -iE 'account|StartUser|user 100|user -2|BMS'
```

### SYS-03 Launcher / SystemUI

只读检查：

```bash
ps -A | grep -E 'launcher|systemui|render_service|window'
hidumper -s RenderService -a "screen"
/rdkhm/screen-status.sh
```

受控截图：

```bash
/rdkhm/screen-status.sh --capture
```

预期：

```text
Launcher 在前台
桌面可见，图标可点
锁屏可解锁
```

注意：进程存在不等于窗口可见。必须截图或看物理屏。

### SYS-04 HDC 冷启动

```bash
ps -A | grep hdcd
cat /proc/net/tcp | grep ':15B3'
```

预期：

```text
hdcd 自动运行
5555 监听
USB/网络 HDC 均可连接
```

失败判据：

```text
需要手工 service_control start hdcd
```

### SYS-05 存储

```bash
df -h
mount | grep -E '/data|/storage'
ls -ld /data/service/el1/100 /data/service/el2/100 /data/service/el3/100
touch /data/local/tmp/rdkhm-write-test
dd if=/dev/zero of=/data/local/tmp/rdkhm-dd bs=1M count=32
rm /data/local/tmp/rdkhm-write-test /data/local/tmp/rdkhm-dd
```

预期：

```text
/data 可读写，空间正常
account 目录存在
无只读文件系统错误
```

### SYS-06 电源/息屏/唤醒

```bash
power-shell get
power-shell timeout 600000
power-shell wakeup
```

触摸或按键唤醒后再次截图。预期：

```text
30 秒默认息屏符合预期
wakeup 后屏幕亮
触摸能唤醒并送达应用
```

### SYS-07 SELinux

```bash
cat /sys/fs/selinux/enforce
cat /sys/fs/selinux/policy >/dev/null && echo policy-ok
/rdkhm/system-security-status.sh
hilog -x | grep 'avc:.*denied'
```

预期：

```text
记录当前 enforce 值（0/1）
无阻断关键服务的 AVC
```

不要为了“看起来干净”直接切 permissive；先记录。

## 3. 显示与输入

### HMI-01 HDMI/DRM

```bash
/rdkhm/hdmi-status.sh
for f in status enabled modes; do
  cat /sys/class/drm/card0-HDMI-A-1/$f
done
```

预期：

```text
status: connected
enabled: enabled
modes 非空
```

失败：

```text
connector-missing
status disconnected
enabled disabled
```

### HMI-02 首帧/黑屏

```bash
/rdkhm/screen-status.sh
/rdkhm/screen-status.sh --capture
```

检查：

```text
/data/rdkhm-logs/screen.jpeg
/data/rdkhm-logs/layout.json
```

预期：

```text
截图不是全黑
能看到锁屏或桌面
```

### HMI-03 触摸枚举

```bash
/rdkhm/touch-status.sh
cat /proc/bus/input/devices
ls -l /dev/input/event*
getevent -lp /dev/input/event1
```

预期：

```text
QDtech MPI5001 或实际触摸设备
event 节点存在
ABS_MT_POSITION_X/Y 能力存在
```

### HMI-04 触摸事件到 MMI

```bash
getevent -lt /dev/input/event1
```

同时：

```bash
hilog -x | grep -E 'InputKeyFlow|InputWindowsManager|MMI|multimodalinput'
```

预期：

```text
down/move/up 出现
InputKeyFlow 有事件
InputWindowsManager 不出现 invalid displayId:-1
```

失败判据：

```text
有 evdev 事件，但 MMI 无事件
只有 down，没有 up
displayId=-1 导致事件丢弃
```

### HMI-05 点击/滑动/解锁

步骤：

1. 亮屏。
2. 点击一个已知图标。
3. 上滑解锁。
4. 打开 Settings。
5. 返回桌面。

预期：

```text
点击响应
滑动跟手
解锁成功
应用打开/返回正常
```

### HMI-06 息屏唤醒

```bash
power-shell timeout 30000
# 等 30 秒确认息屏
# 触摸屏幕
```

预期：

```text
屏幕亮
触摸事件送达
不需要重启
```

### HMI-07 displayId 绑定

```bash
hilog -x | grep -E 'Failed to obtain physical|displayId|GetPhysicalDisplay|windowsPerDisplay'
```

预期：

```text
无 Failed to obtain physical(-1) display
无 invalid displayId:-1
```

### HMI-08 USB 键鼠

```bash
cat /proc/bus/input/devices
ls -l /dev/input/event*
```

插拔键鼠，检查：

```text
新 event 节点出现/消失
按键/移动能影响焦点
```

### HMI-09 HDMI 热插拔

受控步骤：

1. 显示正常时拔 HDMI。
2. 等待 5 秒。
3. 重新插入。
4. 检查是否恢复画面。

预期：

```text
不崩 render_service/composer
重新插入后恢复
```

失败时采集：

```bash
dmesg | tail -100
hilog -x | grep -E 'HDMI|drm|composer|RenderService'
```

## 4. 网络

### NET-01 以太网链路

```bash
ip link
ip addr
cat /sys/class/net/eth0/operstate 2>/dev/null
cat /sys/class/net/end0/operstate 2>/dev/null
```

预期：

```text
link up
有 IPv4 地址（DHCP）
```

### NET-02 以太网数据

```bash
ping -c 4 <gateway>
ping -c 4 <host>
```

预期：

```text
0% packet loss
```

### NET-03 Wi-Fi 打开

受控：

```bash
ifconfig wlan0 up
iw dev
```

已知失败基线：

```text
rwnx_open error waiting for close time out
cmd queue crashed
add_if: Status Error(255)
```

预期修复后：

```text
wlan0 up 成功
无 cmd queue crashed
```

### NET-04 Wi-Fi 扫描/连接

```bash
iw dev wlan0 scan | head
# 或使用 Settings/WLAN UI
```

连接后：

```bash
ip addr show wlan0
ping -c 4 <gateway>
```

预期：

```text
扫描到 AP
关联成功
DHCP 地址
可 ping
```

### NET-05 Wi-Fi 恢复

步骤：

1. down。
2. up。
3. 重复 5 次。
4. 再扫描/连接。

预期：

```text
不进入永久 CRASHED
能重新打开
```

### NET-06 蓝牙 probe

只读：

```bash
/rdkhm/bluetooth-init.sh --probe
```

预期：

```text
BT_FIRMWARE_PRESENT
BT_UART_CANDIDATE
```

失败：

```text
BT_UART_CANDIDATE: none
BT_ATTACH_BLOCKED
```

### NET-07 蓝牙 attach

受控，需要 DTS 确认的 UART/baud：

```bash
/rdkhm/bluetooth-init.sh --attach <hciattach> <uart> <baud>
```

随后：

```bash
hciconfig -a
# 或 bluetoothctl list
```

预期：

```text
controller 出现
能 scan
```

### NET-08 WS73/SLE probe

只读：

```bash
/rdkhm/ws73-probe.sh
```

预期：

```text
ffff:3733 present
firmware 4 个文件存在
```

### NET-09 SLE 打开

受控加载 `plat_soc + sle_soc` 后：

```bash
ls -l /dev/hwsle
# 运行已构建的 sle-adv-probe
```

预期：

```text
open 成功
sle btc open finish
sle set sle state 1
close 后 state 0
```

已知：

```text
DLI 广播命令只返回 PENDING
30 秒无 complete/ACB/ICB
无第二台 scanner
```

### NET-10 4G/LTE

只读：

```bash
lsusb
dmesg | grep -iE 'option|qmi|wwan|SIM7600'
ls /dev/ttyUSB* /dev/wwan* 2>/dev/null
ip link
```

预期：

```text
1e0e:9001 识别
ttyUSB* 创建
wwan0 创建
```

功能：

```bash
# 有 SIM 时
# ttyUSB2 上发 AT+CPIN? / AT+CSQ / AT+COPS?
# wwan0 上做数据连接
```

预期：

```text
SIM ready
注册成功
数据连接
```

无 SIM 时只能记录 BLOCKED，不能算通过。

## 5. 总线与 GPIO

### BUS-01 CAN 控制器

```bash
ip link show can0
ip -details link show can0
```

预期：

```text
can0 存在
bitrate/sample-point 合理
```

### BUS-02 CAN loopback

受控：

```bash
ip link set can0 down
ip link set can0 type can bitrate 500000 loopback on
ip link set can0 up
candump can0 &
cansend can0 123#1011121314151617
```

预期：

```text
收到 123 [8] 10 11 12 13 14 15 16 17
```

记录：

```text
CAN_TEST_PASS
```

### BUS-03 CAN-FD loopback

```bash
ip link set can0 down
ip link set can0 type can bitrate 500000 dbitrate 2000000 fd on loopback on
ip link set can0 up
cansend can0 123##1AABBCCDDEEFF0011
```

预期：

```text
FD 帧收到，flags 正确
```

记录：

```text
CANFD_TEST_PASS
```

### BUS-04 外部 CAN 总线

前置：

```text
第二节点
120Ω 终端电阻
正确 CANH/CANL
共地
```

步骤：

1. 两个节点同 bitrate。
2. 双向发送。
3. 观察错误计数：

```bash
ip -details -statistics link show can0
```

预期：

```text
双向收发
无持续 bus-off
错误计数不持续增长
```

### BUS-05 GPIO 枚举

```bash
/rdkhm/gpio list
/rdkhm/gpio show 7
```

预期：

```text
6 个 gpiochip
28 个信号针
Pin 7 对应 GPIO 420（以当前映射为准）
```

### BUS-06 GPIO 操作

受控：

```bash
/rdkhm/gpio export 7
/rdkhm/gpio set 7 1
/rdkhm/gpio get 7
/rdkhm/gpio set 7 0
/rdkhm/gpio get 7
/rdkhm/gpio unexport 7
```

预期：

```text
set/get 一致
无权限错误
结束后 unexport
```

### BUS-07 PinTool

```bash
bm dump -n com.rdkhm.pintool
```

启动 HAP 后检查：

```text
GPIO service connected
28 针列表可见
Pin 7 High/Low/Read 可用
```

失败判据：

```text
bundle not registered
UI 无法启动
```

### BUS-08 SPI

```bash
ls -l /dev/spidev*
ls /sys/bus/spi/devices
```

若设备存在：

```bash
# 使用项目提供的 spidev 测试程序
# 读写已知寄存器/回环
```

预期：

```text
设备 bind
传输返回正确数据
```

### BUS-09 I2C

```bash
ls -l /dev/i2c-*
# 如板端有 i2cdetect
i2cdetect -y <bus>
```

预期：

```text
总线存在
目标地址响应
```

### BUS-10 UART

```bash
ls -l /dev/ttyS* /dev/ttyUSB* /dev/ttyACM*
```

用已知回环或对端：

```text
发送数据
接收一致
无丢字节
```

### BUS-11 PWM

```bash
ls /sys/class/pwm
```

若存在：

```text
export
period/duty_cycle
enable
示波器/负载验证
```

### BUS-12 USB 串口

```bash
lsusb
dmesg | tail -50
ls -l /dev/ttyUSB* /dev/ttyACM*
```

预期：

```text
CH341/CP210x/FTDI/PL2303 识别
节点创建
```

功能：

```text
DDK 服务注册
应用有 ACCESS_DDK_USB_SERIAL 权限
打开/读写成功
```

## 6. 音频

### AUD-01 声卡枚举

```bash
/rdkhm/audio-status.sh
cat /proc/asound/cards
cat /proc/asound/pcm
ls -l /dev/snd
```

预期：

```text
duplexaudio/ES8326 存在
PCM playback/capture 节点存在
```

### AUD-02 播放

```bash
aplay -l
# 使用 48 kHz stereo S16LE 测试音频
aplay -D <device> test.wav
```

预期：

```text
真实声音
无 xrun/underflow 持续刷屏
audio_server 不崩
```

### AUD-03 录音

```bash
arecord -l
arecord -D <device> -f S16_LE -r 48000 -c 2 -d 5 /data/local/tmp/test.wav
```

预期：

```text
文件生成
能播放
有真实输入
```

### AUD-04 音量/静音

检查 ES8326 控件：

```bash
amixer -c <card> controls
amixer -c <card> cget 'HPL Playback Volume'
amixer -c <card> cset 'HPL Playback Volume' <value>
```

预期：

```text
左右声道写入正确
越界值被拒绝
静音行为符合策略
```

### AUD-05 耳机插拔

步骤：

1. 播放中插入耳机。
2. 拔出耳机。
3. 检查路由。

预期：

```text
jack 事件出现
声音切换到耳机/扬声器
无爆音/崩溃
```

### AUD-06 HDMI 音频

```text
HDMI 输出时选择 HDMI audio sink
播放测试音
```

预期：

```text
声音从 HDMI 输出
```

## 7. 摄像头、视频、GPU/NPU

### MED-01 USB 摄像头枚举

```bash
/rdkhm/camera-codec-status.sh
ls -l /dev/video*
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

预期：

```text
/dev/video0 存在
name 为实际 UVC 摄像头
支持格式/分辨率
```

### MED-02 预览

打开 Camera HAP：

```text
真实画面
无 LIFECYCLE_TIMEOUT
camera_host 不崩
```

### MED-03 格式协商

```bash
v4l2-ctl -d /dev/video0 --get-fmt-video
v4l2-ctl -d /dev/video0 --set-fmt-video=width=...,height=...,pixelformat=...
```

预期：

```text
set 后 get 返回请求格式或明确回退
```

### MED-04 拍照

步骤：

1. 预览。
2. 点击快门。
3. 检查生成文件。

预期：

```text
生成 JPEG/图片
文件大小正常
可解码
```

### MED-05 保存到 Photos

步骤：

1. 拍照。
2. 打开 Photos。
3. 检查缩略图/相册/详情。

预期：

```text
图片出现在图库
缩略图可显示
DataShare 查询正常
```

### MED-06 控制栏/布局

```bash
uitest dumpLayout -p /data/rdkhm-logs/camera-layout.json
```

预期：

```text
快门、切换、返回按钮存在
按钮在屏幕内
可点击
```

### MED-07 CSI 摄像头

当前状态：未集成。  
通过条件：

```text
DT 有 sensor
驱动 probe
camera HDI 注册
出流
```

未满足时标记 `N/A`，不要用 USB 摄像头结果代替。

### MED-08 编解码

```bash
# 使用项目 codec 测试/媒体播放器
# 检查 codec HDI 服务与能力
```

预期：

```text
实际码流解码
实际编码输出
无仅“库存在”结论
```

### MED-09 GPU

```bash
ls -l /dev/galcore /dev/dri/card0
# 运行项目构建的 gpu-probe / gpu-compose-test
```

预期：

```text
EGL/GLES context 创建
离屏渲染正确
OH native window/GBM 合成正确
```

### MED-10 NPU/BPU

```bash
ls -l /dev/bpu /dev/bpu_core0 2>/dev/null
lsmod | grep -E 'bpu|galcore'
```

运行模型探针：

```text
模型加载
输入/输出 tensor 正确
推理结果与参考一致
```

只有节点存在不算通过。

## 8. 应用功能

通用检查：

```bash
bm dump -a
bm dump -n <bundle>
ps -A | grep <process>
uitest dumpLayout -p /data/rdkhm-logs/layout.json
snapshot_display -i 0 -f /data/local/tmp/screen.jpeg
```

### APP-01 Settings

步骤：

1. 启动 Settings。
2. 检查主列表。
3. 进入 WLAN/蓝牙/星闪/移动网络。
4. 返回。

预期：

```text
主列表正常
星闪入口存在
进出页面不崩
settingEndText 不崩
```

### APP-02 Contacts

步骤：

1. 打开联系人。
2. 切换到拨号。
3. 点击数字。
4. 新建联系人。
5. 保存/返回。

预期：

```text
列表/空状态正常
拨号键盘显示
点击数字有输入
新建联系人页面可见
DataAbility 查询不超时
```

已知待查：拨号号码文本在 layout 中存在但截图不可见。

### APP-03 CallUI

步骤：

1. 从拨号发起呼叫（无 modem 时可观察 UI）。
2. 检查通话界面。
3. 返回。

预期：

```text
CallUI 启动
无 strict null/TS 崩溃
界面可返回
```

### APP-04 MMS

步骤：

1. 打开信息。
2. 新建会话。
3. 输入文本。
4. 观察发送状态。

预期：

```text
会话页面正常
输入可用
无崩溃
```

无 SIM/短信能力时只能验证 UI，标记 PARTIAL。

### APP-05 FilePicker

步骤：

1. 从文件选择入口打开 FilePicker。
2. 观察是否能列出文件。
3. 选择一个文件并返回 URI。

预期：

```text
不出现 bundle not exist
getFileAccessAbilityInfo 返回有效扩展
getRoots/loadContent 成功
```

已知阻塞：BMS 不返回 ExternalFileManager fileAccess 扩展。

### APP-06 Camera/Photos

见 MED-02 到 MED-06。

### APP-07 Notes

步骤：

1. 打开 Notes。
2. 新建。
3. 输入。
4. 保存。
5. 重新打开。

预期：

```text
编辑/保存/持久化
不黑屏、不崩
```

### APP-08 Calendar

步骤：

1. 打开日历。
2. 新建日程。
3. 保存并查看。

预期：

```text
页面/数据/持久化正常
```

### APP-09 Print/DLP/Screenshot/Security

分别检查：

```text
Print：服务存在、发现/添加打印机
DLP：权限/沙箱流程
Screenshot：截图文件生成
Security/Privacy：权限列表和隐私中心
```

无真实外设时标记 PARTIAL。

### APP-10 PIN/密码

步骤：

1. 设置 PIN/密码。
2. 锁屏。
3. 输入正确 PIN。
4. 输入错误 PIN。
5. 重试/超限。

预期：

```text
PIN 可设置
正确解锁
错误被拒绝
无 TEE 崩溃
```

当前 TEE 不匹配时标记 BLOCKED。

## 9. 稳定性与长稳

### STB-01 连续冷启动

重复 5 次：

```text
记录 boot_id
account.ready
BMS user
Launcher
```

通过：

```text
5/5 成功
无随机失败
```

### STB-02 HDC 长连接

```bash
# 主机侧保持 30 分钟
hdc -t "$BOARD" shell 'while true; do echo alive; sleep 5; done'
```

通过：

```text
30 分钟不中断
```

### STB-03 显示/触摸长稳

```text
30 分钟持续刷新/滑动
```

通过：

```text
无黑屏、无花屏、无输入丢失
```

### STB-04 网络长稳

```bash
ping -i 1 -c 1800 <target>
```

通过：

```text
无持续丢包/断链
```

### STB-05 CAN 长稳

持续收发 30 分钟：

```text
无 bus-off
错误计数不持续增长
```

### STB-06 音频/摄像头长稳

```text
连续播放/录音/预览各 30 分钟
```

通过：

```text
不崩、不泄漏、不出 xrun
```

### STB-07 异常断电

```text
运行中直接断电
重新上电
```

通过：

```text
文件系统可恢复
account 数据不丢
系统可启动
```

## 10. 证据采集模板

### 主机

```bash
mkdir -p "$HOSTLOG"
sha256sum out/images/rdkhm-x5-openharmony-dev.img | tee "$HOSTLOG/image.sha256"
cp out/images/rdkhm-x5-openharmony-dev.partitions.json "$HOSTLOG/"
```

### 板端

```bash
$HDC -t "$BOARD" shell 'cat /proc/sys/kernel/random/boot_id' > "$HOSTLOG/boot_id.txt"
$HDC -t "$BOARD" shell 'uname -a' > "$HOSTLOG/uname.txt"
$HDC -t "$BOARD" shell 'param get bootevent.account.ready' > "$HOSTLOG/account_ready.txt"
$HDC -t "$BOARD" shell 'param get const.distributed_file_property.enabled' > "$HOSTLOG/param.txt"
$HDC -t "$BOARD" shell 'bm dump -a' > "$HOSTLOG/bm.txt"
$HDC -t "$BOARD" shell 'ps -A' > "$HOSTLOG/ps.txt"
$HDC -t "$BOARD" shell 'dmesg' > "$HOSTLOG/dmesg.txt"
$HDC -t "$BOARD" shell 'hilog -x' > "$HOSTLOG/hilog.txt"
$HDC -t "$BOARD" shell '/rdkhm/boot-diagnostics.sh' > "$HOSTLOG/boot-diagnostics.txt" 2>&1
$HDC -t "$BOARD" shell '/rdkhm/screen-status.sh --capture' > "$HOSTLOG/screen.txt" 2>&1
```

### 截图/布局

```bash
$HDC -t "$BOARD" file recv /data/rdkhm-logs/screen.jpeg "$HOSTLOG/" || true
$HDC -t "$BOARD" file recv /data/rdkhm-logs/layout.json "$HOSTLOG/" || true
```

## 11. 结果判定

### 单次测试

```text
PASS:      步骤完成，预期结果和证据都满足
PARTIAL:   枚举/部分场景通过，完整链路未满足
FAIL:      已复现错误
BLOCKED:   前置条件不满足
UNVERIFIED:未执行
```

### 域级判定

一个域只有在以下条件都满足时才能标 PASS：

```text
驱动/服务枚举正常
受控功能正常
应用/框架链路正常
失败可恢复
证据齐全
```

### 全系统判定

```text
P0 全部 PASS
P1 按产品需求 PASS
无阻断级 AVC/panic/account 失败
多次冷启动稳定
```

## 12. 当前状态摘要

详见 [全系统测试计划](system-test-plan-20261120.md)。

当前最重要的未验证项：

```text
本轮镜像未刷写
HMDFS/account/user 100 未冷启动验证
Launcher/HDMI/触摸完整链路未验证
Wi-Fi/蓝牙/SLE/4G 功能未完成
音频播放/录音/路由未完整验证
摄像头拍照保存/Photos 未完成
TEE/PIN、FilePicker 仍阻塞
```

当前离线风险：

```text
完整 verifier 曾因并发 build 修改 packages 而失败
必须先保证构建环境只有一个 build
```

## 13. 测试记录示例

```text
case: HM-05
result: UNVERIFIED
boot_id: <待填>
kernel: <待填>
image sha256: 7948f022...
param enabled: true
command: param get bootevent.account.ready
expected: true
actual:
evidence:
notes: 镜像未刷；旧板端仍是 source-before-hmdfs
```

```text
case: BUS-02
result: PASS
boot_id: ...
kernel: 6.1.83-rdkhm
command: cansend can0 123#1011121314151617
expected: candump 收到相同帧
actual: CAN_TEST_PASS
evidence: out/logs/board-can-....
notes: 仅 loopback，外部总线未测
```

## 14. 相关文件

- [全系统测试计划](system-test-plan-20261120.md)
- [HMDFS 测试](hmdfs-testing-20261120.md)
- [板端验证 2026-11-19](board-validation-20261119.md)
- [驱动集成](drivers.md)
- [NearLink](nearlink.md)
- [GPIO](gpio.md)
- [Camera/Photos](camera-media-photos-20261119.md)
- [Boot/Audio](boot-audio-fixes.md)
- [Fastboot 刷写](fastboot-flashing.md)
