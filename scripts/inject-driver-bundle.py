#!/usr/bin/env python3
"""Inject a verified driver bundle into a raw vendor ext4 image."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def run(image, command, write=False):
    return subprocess.check_output(["debugfs", *(["-w"] if write else []), "-R", command, str(image)],
                                   text=True, stderr=subprocess.STDOUT)


def main():
    workspace = Path(__file__).resolve().parents[1]
    image = Path(sys.argv[1]).resolve()
    bundle = workspace / "out/driver-bundle"
    manifest = json.loads((bundle / "etc/rdkhm-drivers.json").read_text())
    kernel = workspace / "out/kernel/obj/arch/arm64/boot/Image"
    if hashlib.sha256(kernel.read_bytes()).hexdigest() != manifest["kernel_sha256"]:
        raise RuntimeError("Driver bundle is stale; rebuild it for the current kernel")
    config = workspace / "out/kernel/obj/.config"
    if hashlib.sha256(config.read_bytes()).hexdigest() != manifest["kernel_config_sha256"]:
        raise RuntimeError("Driver bundle is stale; kernel configuration changed")
    for rel, expected in manifest["files"].items():
        if hashlib.sha256((bundle / rel).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Driver bundle changed: {rel}")
    with tempfile.TemporaryDirectory(prefix="inject-drivers-", dir=workspace / "out") as temp:
        extracted = Path(temp) / "extracted"
        for path in sorted(bundle.rglob("*")):
            relative = "/" + str(path.relative_to(bundle))
            if path.is_dir():
                run(image, f"mkdir {relative}", True)
                continue
            # Only the dedicated driver paths are replaced on a reassembly.
            run(image, f"rm {relative}", True)
            run(image, f"write {path} {relative}", True)
            mode = "0100755" if relative[1:] in manifest.get("executables", []) else "0100644"
            for field, value in (("uid", "0"), ("gid", "0"), ("mode", mode)):
                run(image, f"set_inode_field {relative} {field} {value}", True)
            extracted.unlink(missing_ok=True)
            run(image, f"dump {relative} {extracted}")
            if extracted.read_bytes() != path.read_bytes():
                raise RuntimeError(f"Injected file differs: {relative}")
    print("Verified driver bundle injection")


if __name__ == "__main__":
    main()
