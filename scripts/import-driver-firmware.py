#!/usr/bin/env python3
"""Capture firmware provenance once; subsequent imports enforce the lock."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import argparse
from workspace import environment


def main():
    workspace = Path(__file__).resolve().parents[1]
    env = environment()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bsp", type=Path, default=Path(env.get("RDKHM_BSP", str(workspace / "thirdparty/reference-bsp"))))
    parser.add_argument("--regdb", type=Path, default=Path(env.get("RDKHM_REGDB", "/lib/firmware")))
    parser.add_argument("--ws73", type=Path,
                        default=Path(env["RDKHM_KERNEL_TREE"]).parent / "ws73-bsp-94a02d3a/firmware/us")
    args = parser.parse_args()
    source = args.bsp / "packages/bsp/hobot-x5/vendor/etc/firmware"
    lock_path = workspace / "config/kernel/firmware-lock.json"
    lock = json.loads(lock_path.read_text())
    files = []
    for entry in lock["files"]:
        name = Path(entry["name"])
        if name.is_absolute() or ".." in name.parts:
            raise RuntimeError(f"Invalid firmware path: {name}")
        if name.parts[0] == "ws73":
            path = args.ws73 / name.name
        elif name.name in ("regulatory.db", "regulatory.db.p7s"):
            path = args.regdb / name.name
        else:
            path = source / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Firmware differs from pinned lock: {path}")
        files.append((name, path))
    target = workspace / "out/driver-firmware"
    target.mkdir(parents=True, exist_ok=True)
    for name, path in files:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    print(f"Imported {len(files)} pinned firmware assets")


if __name__ == "__main__":
    main()
