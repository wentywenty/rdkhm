#!/usr/bin/env python3
"""Check the assembled SD file against the actual kernel and OH build outputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    workspace = Path(__file__).resolve().parents[1]
    image = workspace / "out/images/rdkhm-x5-openharmony-dev.img"
    package = workspace / "sources/openharmony-full/out/rdk_x5/packages/phone"
    kernel = workspace / "out/kernel/obj/arch/arm64/boot"
    kernel_config = run("bash", str(workspace / "sources/x5-kernel/scripts/extract-ikconfig"),
                        str(kernel / "Image")).splitlines()
    for setting in ("CONFIG_ANDROID_BINDER_IPC=y", "# CONFIG_ANDROID_BINDERFS is not set",
                    'CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"'):
        require(setting in kernel_config, f"Missing legacy Binder configuration: {setting}")
    require(image.is_file(), "Expected a regular image file")
    table = json.loads(run("sfdisk", "--json", str(image)))["partitiontable"]
    require(table["label"] == "dos" and table["sectorsize"] == 512, "Invalid MBR")
    parts = table["partitions"]
    require(len(parts) == 4, "Expected CONFIG/system/vendor/data partitions")
    require(parts[0]["start"] == 8192 and parts[0]["size"] == 524288
            and parts[0]["type"] == "c", "Invalid CONFIG partition")
    require(parts[1]["start"] == 532480 and parts[1].get("bootable"), "Invalid boot partition")
    end = 8192
    for index, part in enumerate(parts):
        require(part["start"] >= end and part["size"] > 0, "Overlapping partitions")
        require(part["start"] % 2048 == 0 and part["size"] % 2048 == 0, "Unaligned partition")
        if index:
            require(part["type"] == "83", "Expected Linux partition")
        end = part["start"] + part["size"]
    require(end * 512 == image.stat().st_size, "Image length does not match partition table")
    require(digest(image) == image.with_suffix(".img.sha256").read_text().split()[0], "SD checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="verify-oh-", dir=image.parent) as temp:
        temp = Path(temp)
        filesystems = {}
        for name, part in zip(("config", "system", "vendor", "userdata"), parts):
            target = temp / f"{name}.img"
            run("dd", f"if={image}", f"of={target}", "bs=1M",
                f"skip={part['start'] // 2048}", f"count={part['size'] // 2048}",
                "conv=sparse", "status=none")
            filesystems[name] = target
            if name == "config":
                run("fsck.vfat", "-n", str(target))
                require("RDKHM status" in run("mtype", "-i", str(target), "::STATUS.txt"), "Missing status")
            else:
                print(run("e2fsck", "-fn", str(target)).strip())

        mapping = {
            ("system", "/boot/Image"): kernel / "Image",
            ("system", "/rdkhm/init"): workspace / "bringup/openharmony-init",
            ("system", "/rdkhm/load-drivers.sh"): workspace / "bringup/load-drivers.sh",
            ("system", "/rdkhm/hdmi-status.sh"): workspace / "bringup/hdmi-status.sh",
            ("system", "/rdkhm/touch-status.sh"): workspace / "bringup/touch-status.sh",
            ("system", "/rdkhm/capture-hilog.sh"): workspace / "bringup/capture-hilog.sh",
            ("system", "/rdkhm/busybox"): workspace / "out/bringup-bin/busybox",
        }
        for name in ("x5-rdk", "x5-rdk-v1p0"):
            mapping[("system", f"/boot/hobot/{name}.dtb")] = kernel / f"dts/hobot/{name}.dtb"
        for name in ("init", "appspawn", "hdcd", "render_service", "samgr", "hilogd", "hilog"):
            mapping[("system", f"/system/bin/{name}")] = package / f"system/bin/{name}"
        for path in ("lib/ld-musl-aarch64.so.1", "lib64/platformsdk/libace.z.so",
                     "lib64/libaccountmgr.z.so", "lib64/libsink_adapter.z.so", "lib64/libmodule-hdi-sink.z.so",
                     "etc/selinux/targeted/policy/policy.31",
                     "etc/audio/alsa/share/alsa.conf"):
            mapping[("system", f"/system/{path}")] = package / "system" / path
        for bundle, name in (("launcher", "Launcher"), ("systemui", "SystemUI")):
            path = f"system/app/com.ohos.{bundle}/{name}.hap"
            mapping[("system", f"/{path}")] = package / path
        for path in (
            "lib64/libdisplay_composer_vdi_impl_default.z.so",
            "lib64/chipset-sdk/libdisplay_buffer_vdi_impl_default.z.so",
            "lib64/passthrough/indirect/libhdi_input_udriver.z.so",
            "lib64/passthrough/libinput_interfaces_service_1.0.z.so",
            "etc/hdfconfig/hdf_default.hcb", "etc/init/hdf_devhost.cfg",
            "etc/init.rdk_x5.cfg", "etc/ueventd.config", "bin/rdkhm-usb.sh",
            "lib64/libwifi_hdi_c_device.z.so", "lib64/libwpa_hdi_c_device.z.so",
            "lib64/libchip_hdi_driver.z.so", "lib64/libhostapd_hdi_c_device.z.so",
            "lib64/libwifi_driver_client.z.so",
            "lib64/libusb_serial_ddk_driver.z.so", "lib64/libusb_serial_ddk_service_1.0.z.so",
            "lib64/libaudio_primary_driver.z.so", "lib64/libaudio_primary_impl_vendor.z.so",
            "lib64/libaudio_render_adapter.z.so", "lib64/libaudio_capture_adapter.z.so",
            "lib64/libasound.so", "etc/hdfconfig/audio_adapter.json",
            "etc/hdfconfig/alsa_adapter.json", "etc/audio/audio_policy_config.xml",
            "lib64/librdkhm_ssap.so",
        ):
            mapping[("vendor", f"/{path}")] = package / "vendor" / path
        bundle = workspace / "out/driver-bundle"
        manifest = json.loads((bundle / "etc/rdkhm-drivers.json").read_text())
        require(manifest["kernel_sha256"] == digest(kernel / "Image"), "Drivers target a different kernel")
        require("designware_i2s" in manifest["autoload"], "Missing I2S CPU DAI autoload")
        for name in ("plat_soc", "wifi_soc", "ble_soc", "sle_soc"):
            require(name in manifest.get("manual", []) and name not in manifest["autoload"],
                    f"WS73 must remain manual until the loading failure is diagnosed: {name}")
        for path, expected in manifest["files"].items():
            original = bundle / path
            require(digest(original) == expected, f"Driver source checksum mismatch: {path}")
            mapping[("vendor", f"/{path}")] = original
        mapping[("vendor", "/etc/rdkhm-drivers.json")] = bundle / "etc/rdkhm-drivers.json"
        for name in ("sys_prod", "chip_prod", "eng_system", "eng_chipset"):
            original = package / f"images/{name}.img"
            if original.is_file():
                mapping[("system", f"/rdkhm/{name}.img")] = original

        for index, ((partition, path), original) in enumerate(mapping.items()):
            target = temp / f"artifact-{index}"
            run("debugfs", "-R", f"dump {path} {target}", str(filesystems[partition]))
            require(target.is_file() and digest(target) == digest(original), f"Artifact mismatch: {path}")
            if partition == "vendor" and path == "/etc/init.rdk_x5.cfg":
                jobs = json.loads(target.read_text())["jobs"]
                commands = [cmd for job in jobs if job["name"] == "post-fs-data" for cmd in job["cmds"]]
                for category in ("app", "service"):
                    for level in ("el3", "el4", "el5"):
                        require(f"mkdir /data/{category}/{level} 0711 root root" in commands,
                                f"Missing storage parent: {category}/{level}")
            if path == "/lib64/libdisplay_composer_vdi_impl_default.z.so":
                print(run("python3", str(workspace / "scripts/check-composer-abi.py"), str(target)).strip())
            if path.startswith("/boot/hobot/") and path.endswith(".dtb"):
                # Resolve the SoC bus path from the compiled DTB symbols.
                dc = run("fdtget", "-t", "s", str(target), "/__symbols__", "dc8000_nano").strip()
                sif = run("fdtget", "-t", "s", str(target), "/__symbols__", "vs_sif").strip()
                require(run("fdtget", "-t", "s", str(target), dc, "aux-names").strip() == "vs_sif",
                        f"Display still depends on an unused compositor: {path}")
                require(run("fdtget", "-t", "x", str(target), dc, "aux-devs").strip()
                        == run("fdtget", "-t", "x", str(target), sif, "phandle").strip(),
                        f"Display auxiliary phandle does not match SIF: {path}")
            if path.endswith(".hap"):
                with zipfile.ZipFile(target) as archive:
                    require(archive.testzip() is None, f"Invalid HAP ZIP: {path}")
            if path in ("/system/bin/init", "/system/bin/render_service"):
                require("AArch64" in run("readelf", "-h", str(target)), f"Wrong architecture: {path}")
            if path.endswith(".ko"):
                require("AArch64" in run("readelf", "-h", str(target)), f"Wrong module architecture: {path}")
            if partition == "vendor" and path.startswith("/lib64/rdkhm-accelerator/"):
                require("AArch64" in run("readelf", "-h", str(target)), f"Wrong runtime architecture: {path}")
            if partition == "vendor" and path[1:] in manifest.get("executables", []):
                info = run("debugfs", "-R", f"stat {path}", str(filesystems[partition]))
                require("0755" in info and "User:     0" in info, f"Wrong executable mode: {path}")
            if path == "/lib64/libwifi_driver_client.z.so":
                require("libnl" in run("readelf", "-d", str(target)), "WLAN is not using the Linux netlink backend")
            if path in ("/lib64/libaudio_render_adapter.z.so", "/lib64/libaudio_capture_adapter.z.so"):
                require("libasound.so" in run("readelf", "-d", str(target)), "Audio is not using ALSA")
                require("AArch64" in run("readelf", "-h", str(target)), "Wrong audio architecture")
            if path == "/etc/hdfconfig/alsa_adapter.json":
                require(json.loads(target.read_text())["adapters"] == [
                    {"name": "primary", "cardId": -1, "cardName": "duplexaudio"}],
                    "Audio must select the X5 codec by stable ALSA ID")
            if path.startswith(("/boot/", "/rdkhm/")):
                info = run("debugfs", "-R", f"stat {path}", str(filesystems[partition]))
                require("User:     0" in info and "Group:     0" in info, f"Wrong owner: {path}")
        boot = temp / "boot.scr"
        run("debugfs", "-R", f"dump /boot/boot.scr {boot}", str(filesystems["system"]))
        print(run("mkimage", "-l", str(boot)).strip())
        # mkimage's legacy script contains a 64-byte header and an 8-byte size table.
        require(boot.read_bytes()[72:] == (workspace / "bringup/openharmony-boot.cmd").read_bytes(),
                "Packaged boot commands differ from source")
        commands = (workspace / "bringup/openharmony-boot.cmd").read_text()
        require(" selinux=1 enforcing=0 " in commands and "selinux=0" not in commands,
                "OH init needs active SELinux with permissive bring-up policy")
    print(f"PASS: MBR, checksum, four filesystems and {len(mapping)} packaged artifact comparisons")
    print("NOT TESTED: X5 boot, HDMI/input, HDC enumeration, services and HAP execution")


if __name__ == "__main__":
    main()
