#!/usr/bin/env python3
"""Inspect a regular SD image file without loop devices or root privileges."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    workspace = Path(__file__).resolve().parents[1]
    image = workspace / "out/images/rdkhm-x5-bringup-0.1.img"
    table = json.loads(run("sfdisk", "--json", str(image)))["partitiontable"]
    assert table["label"] == "dos" and table["sectorsize"] == 512
    parts = table["partitions"]
    assert len(parts) == 2
    assert (parts[0]["start"], parts[0]["size"], parts[0]["type"]) == (8192, 524288, "c")
    assert (parts[1]["start"], parts[1]["size"], parts[1]["type"]) == (532480, 524288, "83")
    assert parts[1]["bootable"] and image.stat().st_size == 516 * 1024 * 1024
    expected_hash = image.with_suffix(".img.sha256").read_text().split()[0]
    assert digest(image) == expected_hash
    with tempfile.TemporaryDirectory(prefix="verify-", dir=workspace / "out/images") as temp:
        temp = Path(temp)
        rootfs = temp / "rootfs.img"
        with image.open("rb") as source, rootfs.open("wb") as dest:
            source.seek(parts[1]["start"] * 512)
            remaining = parts[1]["size"] * 512
            while remaining:
                data = source.read(min(remaining, 1024 * 1024))
                assert data, "Truncated rootfs"
                dest.write(data)
                remaining -= len(data)
        print(run("e2fsck", "-fn", str(rootfs)))
        mapping = {
            "/boot/Image": workspace / "out/kernel/obj/arch/arm64/boot/Image",
            "/sbin/init": workspace / "bringup/init",
            "/bin/busybox": workspace / "out/bringup-bin/busybox",
            "/bin/kernel-probe": workspace / "out/bringup-bin/kernel-probe",
            "/boot/hobot/x5-rdk.dtb": workspace / "out/kernel/obj/arch/arm64/boot/dts/hobot/x5-rdk.dtb",
            "/boot/hobot/x5-rdk-v1p0.dtb": workspace / "out/kernel/obj/arch/arm64/boot/dts/hobot/x5-rdk-v1p0.dtb",
        }
        for index, (inside, original) in enumerate(mapping.items()):
            extracted = temp / f"file-{index}"
            run("debugfs", "-R", f"dump {inside} {extracted}", str(rootfs))
            assert digest(extracted) == digest(original), inside
            stat = run("debugfs", "-R", f"stat {inside}", str(rootfs))
            assert "User:     0" in stat and "Group:     0" in stat, stat
        console = run("debugfs", "-R", "stat /dev/console", str(rootfs))
        assert "character special" in console and "05:01" in console, console
        shell = run("debugfs", "-R", "stat /bin/sh", str(rootfs))
        assert 'Fast link dest: "busybox"' in shell, shell
        stage = run("debugfs", "-R", "cat /etc/rdkhm-stage", str(rootfs))
        assert "No OpenHarmony userspace" in stage
        boot = temp / "boot.scr"
        run("debugfs", "-R", f"dump /boot/boot.scr {boot}", str(rootfs))
        print(run("mkimage", "-l", str(boot)))
    print("PASS: partition layout, filesystem, ownership, device nodes, artifact hashes, boot script")
    print("NOT TESTED: X5 boot, kernel ABI runtime, HDMI, OpenHarmony services")


if __name__ == "__main__":
    main()
