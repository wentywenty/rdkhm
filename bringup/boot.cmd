# RDK X5 only. Requires the existing X5 QSPI U-Boot distro boot flow.
echo "RDKHM experimental kernel bring-up image"
setenv fdtfile x5-rdk-v1p0.dtb
if test "${hb_board_id}" = "0x0301"; then
    setenv fdtfile x5-rdk.dtb
fi
if test "${hb_board_id}" != "0x0301"; then
    if test "${hb_board_id}" != "0x0302"; then
        echo "Unrecognized RDK X5 board ID; refusing automatic boot"
        exit
    fi
fi
setenv bootargs "console=tty1 console=ttyS0,115200 rootfstype=ext4 rw rootwait root=/dev/mmcblk${devnum}p${devplist} init=/sbin/init mtdparts=spi7.0:0x700000@0x0(miniboot),0x180000@0x700000(ubootenv)"
if ext4load ${devtype} ${devnum}:${devplist} ${fdt_addr_r} ${prefix}hobot/${fdtfile}; then
    if ext4load ${devtype} ${devnum}:${devplist} ${kernel_addr_r} ${prefix}Image; then
        booti ${kernel_addr_r} - ${fdt_addr_r}
    fi
fi
echo "RDKHM boot failed"
