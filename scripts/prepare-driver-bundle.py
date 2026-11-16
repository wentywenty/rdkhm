#!/usr/bin/env python3
"""Stage selected X5 modules with dependencies and pinned firmware assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    workspace = Path(__file__).resolve().parents[1]
    obj = workspace / "out/kernel/obj"
    release = (obj / "include/config/kernel.release").read_text().strip()
    bundle = workspace / "out/driver-bundle"
    stage = workspace / "out/driver-bundle.tmp"
    if stage.exists():
        shutil.rmtree(stage)
    module_dir = stage / f"lib/modules/{release}"
    module_dir.mkdir(parents=True)
    normalize = lambda name: name.replace("-", "_")
    modules = {}
    for line in (obj / "modules.order").read_text().splitlines():
        path = obj / line
        if not path.is_file():
            raise RuntimeError(f"Build modules first: missing {path}")
        name = normalize(path.stem)
        if name in modules:
            raise RuntimeError(f"Ambiguous module name: {name}")
        modules[name] = path
    builtin = {normalize(Path(line).stem) for line in (obj / "modules.builtin").read_text().splitlines()}
    ordered = []
    visiting = set()
    seen = set()

    def visit(name):
        name = normalize(name)
        if name in seen or name in builtin:
            return
        if name in visiting:
            raise RuntimeError(f"Module dependency cycle: {name}")
        if name not in modules:
            raise RuntimeError(f"Missing module dependency: {name}")
        visiting.add(name)
        path = modules[name]
        # kmod otherwise resolves same-named host builtins before reading the file.
        vermagic = run("modinfo", "-k", release, "-F", "vermagic", str(path)).split()
        if not vermagic or vermagic[0] != release:
            raise RuntimeError(f"Wrong kernel release: {path}")
        for dependency in run("modinfo", "-k", release, "-F", "depends", str(path)).split(","):
            if dependency:
                visit(dependency)
        visiting.remove(name)
        seen.add(name)
        ordered.append(name)
        shutil.copyfile(path, module_dir / f"{name}.ko")

    selection = json.loads((workspace / "config/driver-modules.json").read_text())
    for name, path in selection.get("external", {}).items():
        if name in modules or not (workspace / path).is_file():
            raise RuntimeError(f"Missing or conflicting external module: {name}")
        modules[name] = workspace / path
    for name in selection["autoload"]:
        visit(name)
    autoload = ordered.copy()
    for name in selection.get("manual", []):
        visit(name)
    manual = [name for name in ordered if name not in autoload]
    (module_dir / "modules.load").write_text("".join(f"{name}.ko\n" for name in autoload))
    (module_dir / "modules.manual").write_text("".join(f"{name}.ko\n" for name in manual))
    (module_dir / "modules.order").write_text("".join(f"{name}.ko\n" for name in ordered))
    shutil.copyfile(obj / "modules.builtin", module_dir / "modules.builtin")
    shutil.copyfile(obj / "modules.builtin.modinfo", module_dir / "modules.builtin.modinfo")
    checked = subprocess.run(["depmod", "-e", "-F", str(obj / "System.map"), "-b", str(stage), release],
                             capture_output=True, text=True, check=True)
    if checked.stderr.strip():
        raise RuntimeError(f"Module symbol/dependency check failed: {checked.stderr}")
    firmware_dir = stage / "etc/firmware"
    firmware_dir.mkdir(parents=True)
    shutil.copyfile(workspace / "out/nearlink/ws73_cfg.ini", stage / "etc/ws73_cfg.ini")
    lock = json.loads((workspace / "config/firmware-lock.json").read_text())
    for entry in lock["files"]:
        source = workspace / "sources/driver-firmware" / entry["name"]
        if sha(source) != entry["sha256"]:
            raise RuntimeError(f"Firmware checksum mismatch: {source}")
        target = firmware_dir / entry["name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    accelerator = workspace / "out/accelerator-runtime"
    accelerator_manifest = json.loads((accelerator / "manifest.json").read_text())
    for path, expected in accelerator_manifest["files"].items():
        source = accelerator / path
        if sha(source) != expected:
            raise RuntimeError(f"Accelerator runtime checksum mismatch: {path}")
        target = stage / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(accelerator / "manifest.json", stage / "etc/rdkhm-accelerators.json")
    manifest = {
        "kernel_release": release,
        "kernel_sha256": sha(obj / "arch/arm64/boot/Image"),
        "kernel_config_sha256": sha(obj / ".config"),
        "autoload": autoload,
        "manual": manual,
        "executables": accelerator_manifest["executables"],
        "accelerator_sources": accelerator_manifest["sources"],
        "firmware_provenance": lock["provenance"],
        "files": {str(p.relative_to(stage)): sha(p) for p in sorted(stage.rglob("*")) if p.is_file()},
    }
    (stage / "etc/rdkhm-drivers.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if bundle.exists():
        shutil.rmtree(bundle)
    stage.rename(bundle)
    print(f"Staged {len(ordered)} modules and {len(lock['files'])} firmware files for {release}")


if __name__ == "__main__":
    main()
