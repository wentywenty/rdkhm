echo "RDKHM OpenHarmony development image"
if test "${hb_board_id}" = "0x0301"; then
    setenv fdtfile x5-rdk.dtb
else
    if test "${hb_board_id}" = "0x0302"; then
        setenv fdtfile x5-rdk-v1p0.dtb
    else
        echo "Unrecognized RDK X5 board ID"
        exit
    fi
fi
if part uuid ${devtype} ${devnum}:${devplist} rdkhm_rootuuid; then
    setenv bootargs "console=tty1 console=ttyS0,115200 earlycon=uart8250,mmio32,0x32120000,115200 root=PARTUUID=${rdkhm_rootuuid} rootwait rootfstype=ext4 rw init=/rdkhm/init ohos.boot.hardware=rdk_x5 hardware=rdk_x5 selinux=1 enforcing=0 mtdparts=spi7.0:0x700000@0x0(miniboot),0x180000@0x700000(ubootenv)"
    if ext4load ${devtype} ${devnum}:${devplist} ${fdt_addr_r} ${prefix}hobot/${fdtfile}; then
        if ext4load ${devtype} ${devnum}:${devplist} ${kernel_addr_r} ${prefix}Image; then
            booti ${kernel_addr_r} - ${fdt_addr_r}
        fi
    fi
fi
echo "RDKHM boot failed"
