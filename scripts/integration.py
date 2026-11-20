#!/usr/bin/env python3
"""Run existing build stages and retain honest, per-run evidence."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import tarfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import components
from workspace import ROOT, KEYS, environment


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def plan(root, target):
    config = json.loads((root / "config/build/pipeline.json").read_text())
    stages = config["profiles"].get(target, [target])
    if any(stage not in config["stages"] for stage in stages):
        raise ValueError(f"Unknown target: {target}")
    return [(stage, command) for stage in stages for command in config["stages"][stage]]


def integration_files(root):
    files = {}
    for name in ("rdkhm", "build", ".gitignore", ".gitattributes", "README.md", "STATUS.md",
                 "apps", "config", "env.sh", "scripts", "patches", "overlay", "bringup", "tests", "docs"):
        base = root / name
        paths = base.rglob("*") if base.is_dir() else [base]
        for path in sorted(paths):
            if "__pycache__" in path.parts or path.name == "workspace.local.json":
                continue
            relative = str(path.relative_to(root))
            if relative == "overlay/device/board/drobotics/rdk_x5/nearlink/ssap":
                continue
            if path.is_symlink():
                # Generated links point into disposable source trees.
                files[relative] = {"symlink": os.readlink(path)}
            elif path.is_file():
                files[relative] = {"sha256": sha(path), "mode": oct(path.stat().st_mode & 0o777)}
    return files


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def source_audit(root, destination):
    manifest = root / "config/sources/openharmony.lock.xml"
    if not manifest.exists():
        return None
    projects = [(p.attrib.get("path", p.attrib["name"]), p.attrib["revision"])
                for p in ET.parse(manifest).getroot().findall("project")]
    oh_tree = Path(environment(root)["RDKHM_OH_TREE"])
    diff_dir = destination / "source-diffs"
    diff_dir.mkdir()

    def inspect(project):
        name, revision = project
        path = oh_tree / name
        head = git(path, "rev-parse", "HEAD")
        record = {"path": name, "expected_revision": revision, "actual_revision": head}
        if head:
            record["status"] = git(path, "status", "--porcelain", "--untracked-files=normal")
            diff = subprocess.run(["git", "-C", str(path), "diff", "--binary", "HEAD"], capture_output=True, check=True).stdout
            if diff:
                output = diff_dir / (hashlib.sha256(name.encode()).hexdigest() + ".patch")
                output.write_bytes(diff)
                record["tracked_diff"] = str(output.relative_to(destination))
                record["tracked_diff_sha256"] = sha(output)
        return record

    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(inspect, projects))
    write_json(destination / "openharmony-source-state.json", records)
    return {"projects": len(records),
            "revision_mismatches_or_missing": sum(p["actual_revision"] != p["expected_revision"] for p in records),
            "dirty_projects": sum(bool(p.get("status")) for p in records)}


def snapshot(root, destination, env):
    files = integration_files(root)
    records = {}
    sources_manifest = root / "config/sources/repo.xml"
    if sources_manifest.is_file():
        for project in ET.parse(sources_manifest).getroot().findall("project"):
            name = project.attrib["path"]
            path = root / "sources" / name
            records[name] = {"name": project.attrib.get("name"),
                             "remote": project.attrib.get("remote"),
                             "expected_revision": project.attrib["revision"],
                             "actual_revision": git(path, "rev-parse", "HEAD"),
                             "status": git(path, "status", "--porcelain", "--untracked-files=normal")}
    data = {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "observed-workspace-snapshot", "integration_files": files,
        "integration_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "git_head": git(root, "rev-parse", "HEAD"), "git_status": git(root, "status", "--porcelain"),
        "settings": {key: env[key] for key in sorted(KEYS) if key in env},
        "pinned_repositories": records,
        "limits": ["Snapshot alone does not prove an existing image was built from these inputs.",
                   "Ignored/untracked upstream file contents and host reproducibility are not certified.",
                   "Filesystem UUIDs and timestamps are not yet deterministic."]
    }
    manifest = root / "out/openharmony-resolved.xml"
    if manifest.is_file():
        shutil.copyfile(manifest, destination / "openharmony-resolved.xml")
        data["resolved_manifest_sha256"] = sha(manifest)
    for tool in ("gcc", "aarch64-linux-gnu-gcc", env.get("CROSS_COMPILE", "aarch64-none-linux-gnu-") + "gcc"):
        if shutil.which(tool, path=env.get("PATH")):
            version = subprocess.run([tool, "--version"], capture_output=True, text=True, env=env, check=True)
            data.setdefault("tool_versions", {})[tool] = version.stdout.splitlines()[0]
    if shutil.which("dpkg-query"):
        with (destination / "host-packages.tsv").open("w") as output:
            subprocess.run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"], stdout=output, check=True)
    archive = destination / "integration.tar.gz"
    with tarfile.open(archive, "w:gz", dereference=False) as output:
        for name in files:
            output.add(root / name, arcname="rdkhm/" + name, recursive=False)
    data["integration_archive_sha256"] = sha(archive)
    data["openharmony_source_audit"] = source_audit(root, destination)
    write_json(destination / "snapshot.json", data)
    return data


def new_run(root):
    parent = root / "out/runs"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=parent))


def doctor(root, env):
    failed = []
    tools = ["git", "repo", "git-lfs", "make", "gcc", "g++", "cmake", "ninja", "curl",
             "patch", "bison", "flex", "bc", "rsync", "fakeroot", "mke2fs", "debugfs", "e2fsck",
             "resize2fs", "mkimage", "sfdisk", "mkfs.vfat", "fsck.vfat", "mcopy", "mtype",
             "fdtget", "simg2img", "modinfo",
             "depmod", "readelf", "dpkg-deb", "aarch64-linux-gnu-gcc"]
    cross = env.get("CROSS_COMPILE", "aarch64-none-linux-gnu-")
    tools += [cross + "gcc"]
    for tool in tools:
        if not shutil.which(tool, path=env.get("PATH")):
            failed.append("missing executable: " + tool)
    if not shutil.which("java", path=env.get("PATH")):
        print("WARN: java not found; signed HAP builds need a JRE or --no-sign")
    bsp = Path(env.get("RDKHM_BSP", str(root / "thirdparty/reference-bsp")))
    reference = Path(env.get("RDKHM_NEARLINK_REFERENCE", str(root / "thirdparty/reference-nearlink")))
    archive = Path(env.get("RDKHM_WS73_ARCHIVE",
                           str(root / "thirdparty/downloads/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz")))
    for path in (bsp / "packages/bsp/hobot-x5/vendor/etc/firmware", reference, archive):
        if not path.exists():
            failed.append("missing input: " + str(path))
    if archive.is_file() and sha(archive) != "94a02d3a8031482827ebf323261ac596b8c2b63c10e0188f6f58beefa2f18f65":
        failed.append("WS73 archive checksum mismatch")
    for message in failed:
        print("FAIL " + message)
    print(f"Host preflight: {len(failed)} failure(s). This is not a full build qualification.")
    return bool(failed)


def run_pipeline(root, target, env):
    commands = plan(root, target)
    destination = new_run(root)
    report = {"target": target, "status": "running", "steps": [], "board_validation": "not-run"}
    print(f"Run evidence: {destination}", flush=True)
    write_json(destination / "run.json", report)
    try:
        before = snapshot(root, destination, env)
        audit = before.get("openharmony_source_audit")
        if target == "build" and audit and audit["revision_mismatches_or_missing"]:
            raise RuntimeError("OpenHarmony checkouts differ from the project lock; inspect snapshot before syncing")
        for index, (stage, command) in enumerate(commands):
            entry = {"stage": stage, "command": command, "status": "running"}
            report["steps"].append(entry)
            write_json(destination / "run.json", report)
            print(f"[{stage}] {shlex.join(command)}", flush=True)
            with (destination / f"{index:02d}-{stage}.log").open("w") as log:
                result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            entry.update(status="passed" if result.returncode == 0 else "failed", returncode=result.returncode)
            if result.returncode:
                raise RuntimeError(f"Stage {stage} failed; see {destination}")
        report["status"] = "passed"
        report["integration_changed_during_run"] = before["integration_files"] != integration_files(root)
        after = destination / "after"
        after.mkdir()
        snapshot(root, after, env)
        if any(stage in ("image", "verify") for stage, _ in commands):
            artifact = root / "out/images/rdkhm-x5-openharmony-dev.img"
            report["artifact"] = {"path": str(artifact.relative_to(root)), "sha256": sha(artifact),
                                  "bytes": artifact.stat().st_size}
            report["input_coverage"] = "full-pipeline" if target in ("all", "build") else "existing-build-outputs"
    except BaseException as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        write_json(destination / "run.json", report)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=[
        "doctor", "plan", "run", "snapshot", "check", "components", "build", "package", "deploy"])
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("board", nargs="?", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--serial-confirmed", action="store_true",
                        help="confirm serial console access for components that require it")
    args = parser.parse_args()
    if args.command in ("plan", "run") and args.target is None:
        args.target = "build"
    try:
        env = environment()
        if args.command == "components":
            components.listing()
            return 0
        if args.command == "plan":
            for stage, command in plan(ROOT, args.target):
                print(f"{stage}: {shlex.join(command)}")
            return 0
        if args.command == "doctor":
            return int(doctor(ROOT, env))
        if args.command == "check":
            for path in sorted((ROOT / "scripts").glob("*.sh")):
                subprocess.run(["bash", "-n", str(path)], check=True)
            required_bringup = (
                "boot/openharmony-init", "boot/load-drivers.sh", "status/hdmi-status.sh",
                "status/touch-status.sh", "status/camera-codec-status.sh", "status/hardware-status.sh",
                "status/capture-hilog.sh", "network/rdkhm-bluetooth-init.sh",
                "network/rdkhm-ws73-probe.sh", "status/system-security-status.sh",
                "status/screen-status.sh", "status/audio-status.sh", "status/boot-diagnostics.sh",
                "gpio/gpio-status.sh",
            )
            image_builder = (ROOT / "scripts/make-openharmony-image.sh").read_text()
            for name in required_bringup:
                path = ROOT / "bringup" / name
                if not path.is_file():
                    raise ValueError(f"Missing bring-up artifact: {path}")
                if path.suffix == ".sh" or name in ("boot/openharmony-init", "boot/load-drivers.sh"):
                    subprocess.run(["bash", "-n", str(path)], check=True)
                if f"bringup/{name}" not in image_builder:
                    raise ValueError(f"Image builder does not inject bring-up artifact: bringup/{name}")
            patch_markers = {
                "patches/display/0002-composer-c-entrypoints.patch": "RegRefreshCallback",
                "patches/display/0004-drm-power-and-present.patch": "DISPLAY_NOT_SUPPORT",
                "patches/graphic2d/0003-app-server-drawable-split.patch": "SetDrawableGenerationEnabled",
                "patches/audio/0003-default-effect-channel.patch": "no audioEffectChain",
                "patches/bundlemanager/0001-optional-bms-extension.patch": "optional bms extension not present",
                "patches/resourceschedule/0001-pin-auth-secon.patch": "u:r:pin_auth_host:s0",
                "patches/resourceschedule/0002-bundle-active-optional.patch": "Missing product config is optional",
                "patches/audio/0004-optional-running-lock.patch": "runningLock_ == nullptr",
                "patches/media-foundation/0001-avbuffer-default-memory-type.patch": "default virtual allocation",
                "patches/dsoftbus/0001-optional-client-plugin.patch": "optional libdsoftbus_client_plugin",
                "patches/device-manager/0002-optional-resident-log.patch": "optional dm service resident",
                "patches/device-profile/0001-optional-sync-adapter.patch": "optional dp sync adapter",
                "patches/security-component/0001-optional-enhance-log.patch": "optional enhance lib",
                "patches/security-component/0002-device-auth-syscap.patch": "SystemCapability.Security.DeviceAuth",
                "patches/settings/0003-nearlink-settings-page.patch": "app.string.nearlinkTab",
                "patches/camera/0001-lazy-save-asset.patch": "getSaveCameraAsset",
                "patches/camera/0002-vdi-basic-stream-config.patch": "basicConfigurations.push_back(ohosFormat)",
                "patches/camera/0003-init-race.patch": "platformCapability.mCameraCount === 0",
                "patches/launcher/0003-style-config-fallback.patch": "PageDesktopGridStyleConfig.getInstance()",
                "patches/photos/0002-defer-media-library.patch": "initMediaLibrary",
            }
            patch_manifest = json.loads((ROOT / "config/patches.json").read_text())
            listed_patches = {entry["patch"] for entries in patch_manifest["collections"].values()
                              for entry in entries}
            for entries in patch_manifest["collections"].values():
                for entry in entries:
                    if not (ROOT / "patches" / entry["patch"]).is_file():
                        raise ValueError(f"Patch manifest references a missing file: {entry['patch']}")
            rt_defconfig = ROOT / "config/kernel/hobot_x5_rdk_ubuntu_rt_defconfig"
            if not rt_defconfig.is_file():
                raise ValueError(f"Missing opt-in RT defconfig: {rt_defconfig}")
            if "CONFIG_PREEMPT_RT=y" not in rt_defconfig.read_text():
                raise ValueError("RT defconfig does not enable CONFIG_PREEMPT_RT")
            rt_entries = patch_manifest["collections"].get("kernel-rt") or []
            if not any(entry["patch"] == "optional/preempt-rt/patch-6.1.83-rt28.patch"
                       for entry in rt_entries):
                raise ValueError("config/patches.json does not expose the optional RT patch")
            kernel_builder = (ROOT / "scripts/build-kernel.sh").read_text()
            for token in ("hobot_x5_rdk_ubuntu_defconfig", "hobot_x5_rdk_ubuntu_rt_defconfig",
                          "CONFIG_PREEMPT_RT=y"):
                if token not in kernel_builder:
                    raise ValueError(f"Kernel builder does not handle RT profile: {token}")
            for relative, marker in patch_markers.items():
                patch = ROOT / relative
                if not patch.is_file() or marker not in patch.read_text():
                    raise ValueError(f"Missing patch marker: {relative} ({marker})")
                if relative.endswith("0002-composer-c-entrypoints.patch") and \
                        "GetDisplaySupportedColorGamuts" not in patch.read_text():
                    raise ValueError("Composer patch does not export color gamuts")
                patch_id = relative[len("patches/"):]
                if patch_id not in listed_patches:
                    raise ValueError(f"Patch is not listed in config/patches.json: {relative}")
            kernel_markers = {
                "patches/kernel/0006-accesstoken-ioctl-noise.patch": "ENOTTY",
            }
            for relative, marker in kernel_markers.items():
                patch = ROOT / relative
                if not patch.is_file() or marker not in patch.read_text():
                    raise ValueError(f"Missing kernel patch marker: {relative} ({marker})")
                if relative[len("patches/"):] not in listed_patches:
                    raise ValueError(f"Kernel patch is not listed in config/patches.json: {relative}")
            image_builder = (ROOT / "scripts/make-openharmony-image.sh").read_text()
            if "ams_extension_config.json" not in image_builder:
                raise ValueError("Image builder does not install ams_extension_config.json")
            if "libdisplay_buffer_vdi_impl_default" not in image_builder:
                raise ValueError("Image builder does not install the default buffer VDI")
            if not (ROOT / "scripts/build-settings-hap.sh").is_file():
                raise ValueError("Missing Settings HAP build script")
            image_haps = json.loads(
                (ROOT / "config/build/haps.json").read_text()).get("image", {})
            for app, filename in (("settings", "Settings.hap"),
                                  ("launcher", "Launcher.hap"),
                                  ("camera", "Camera.hap"),
                                  ("photos", "Photos.hap"),
                                  ("contacts", "Contacts.hap"),
                                  ("mms", "Mms.hap")):
                if image_haps.get("apps", {}).get(app) != filename:
                    raise ValueError(
                        f"HAP image mapping is missing {app} -> {filename}")
            if not image_haps.get("modules", {}).get("systemui"):
                raise ValueError("HAP image mapping is missing SystemUI modules")
            if not any(entry.get("name") == "rdkhm_pintool"
                       for entry in image_haps.get("extra", [])):
                raise ValueError("HAP image mapping does not install the PinTool HAP")
            if "image_haps.py" not in image_builder:
                raise ValueError("Image builder does not use the shared HAP manifest")
            verifier = (ROOT / "scripts/verify-openharmony-image.py").read_text()
            if "image_haps" not in verifier or "--accept-allowlist" not in verifier:
                raise ValueError("Image verifier does not use the shared HAP manifest")
            for name in ("libdisplay_buffer_vdi_impl_default.z.so", "libdisplay_buffer_vdi_impl.z.so"):
                if name not in verifier:
                    raise ValueError(f"Image verifier does not cover {name}")
            subprocess.run(["python3", str(ROOT / "scripts/check-patch-coverage.py")], check=True)
            subprocess.run(["python3", str(ROOT / "scripts/gen-gpio-map.py"),
                            str(ROOT / "config/gpio/rdk_x5_40pin.json"), "--check"], check=True)
            if "out/bringup-bin/rdkhm-gpio-daemon" not in image_builder:
                raise ValueError("Image builder does not install the GPIO daemon")
            subprocess.run(["python3", str(ROOT / "scripts/test-gpio-daemon.py")], check=True)
            subprocess.run(["python3", str(ROOT / "scripts/check-patch-format.py")], check=True)
            for path in sorted((ROOT / "config").rglob("*.json")):
                json.loads(path.read_text())
            for name, component in components.load().items():
                if not component.get("build"):
                    raise ValueError(f"Component has no build commands: {name}")
                for command in component["build"]:
                    if command and command[0] == "bash" and command[1].startswith("scripts/"):
                        if not (ROOT / command[1]).is_file():
                            raise ValueError(f"Missing component build script: {command[1]}")
                deploy_config = component.get("deploy") or {}
                kind = deploy_config.get("kind")
                if kind not in ("libs", "modules", "image", None):
                    raise ValueError(f"Unsupported deploy kind for {name}: {kind}")
                if "serial_required" in deploy_config:
                    if not isinstance(deploy_config["serial_required"], bool):
                        raise ValueError(f"serial_required must be boolean: {name}")
                    if kind not in ("libs", "modules"):
                        raise ValueError(f"serial_required only applies to libs/modules: {name}")
            haps = json.loads((ROOT / "config/build/haps.json").read_text())
            oh_tree = Path(env["RDKHM_OH_TREE"])
            for name, app in haps.get("apps", {}).items():
                for key in ("dir", "product"):
                    if not app.get(key):
                        raise ValueError(f"HAP entry missing {key}: {name}")
                if not isinstance(app.get("verified"), bool):
                    raise ValueError(f"HAP entry missing verified flag: {name}")
                # Only validate against sources when they are checked out; a
                # fresh workspace without sources must still pass `check`.
                app_dir = oh_tree / app["dir"]
                profile = app_dir / "build-profile.json5"
                if profile.is_file():
                    block = re.search(r'"products"\s*:\s*\[(.*?)\]', profile.read_text(), re.S)
                    declared = re.findall(r'"name"\s*:\s*"([^"]+)"', block.group(1)) if block else []
                    if app["product"] not in declared:
                        raise ValueError(
                            f"HAP {name} product '{app['product']}' is not declared in {profile}: "
                            f"{declared or 'no products block'}")
                elif app_dir.is_dir():
                    raise ValueError(f"HAP source has no build-profile.json5: {app_dir}")
            pipeline = json.loads((ROOT / "config/build/pipeline.json").read_text())
            haps_stage = pipeline["stages"].get("haps", [])
            hap_builds = {command[2] for command in haps_stage
                          if len(command) > 2 and command[0] == "python3"
                          and command[1] == "scripts/build-hap.py"}
            image_haps = haps.get("image", {})
            missing_hap_builds = [name for name in image_haps.get("apps", {})
                                  if name not in hap_builds]
            if missing_hap_builds:
                raise ValueError("Image HAPs missing from the haps stage: "
                                 + ", ".join(sorted(missing_hap_builds)))
            for name in image_haps.get("modules", {}):
                if name not in hap_builds:
                    raise ValueError(f"Image HAP module source missing from the haps stage: {name}")
            if any(extra.get("name") == "rdkhm_pintool"
                   for extra in image_haps.get("extra", [])):
                if not any("scripts/build-pintool-hap.sh" in command for command in haps_stage):
                    raise ValueError("PinTool is in the image manifest but not in the haps stage")
            for stage, commands in pipeline["stages"].items():
                for command in commands:
                    if len(command) >= 2 and command[1].startswith("scripts/"):
                        if not (ROOT / command[1]).is_file():
                            raise ValueError(f"Pipeline stage {stage} references a missing script: {command[1]}")
            for profile, stage_names in pipeline["profiles"].items():
                for stage in stage_names:
                    if stage not in pipeline["stages"]:
                        raise ValueError(f"Pipeline profile {profile} references an unknown stage: {stage}")
            sources_manifest = ET.parse(ROOT / "config/sources/repo.xml").getroot()
            source_paths = []
            for project in sources_manifest.findall("project"):
                relative = Path(project.attrib.get("path", ""))
                revision = project.attrib.get("revision", "")
                if not relative.parts or relative.is_absolute() or ".." in relative.parts or \
                        relative.parts[0] not in ("oh", "rdk", "deps"):
                    raise ValueError(f"Source path is outside oh/rdk/deps: {project.attrib.get('path')}")
                if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
                    raise ValueError(f"Unpinned source project: {project.attrib.get('path')}")
                if not project.attrib.get("name") or not project.attrib.get("remote"):
                    raise ValueError(f"Source project lacks name/remote: {project.attrib.get('path')}")
                source_paths.append(relative.as_posix())
            if len(set(source_paths)) != len(source_paths):
                raise ValueError("Duplicate project paths in config/sources/repo.xml")
            for first in source_paths:
                for second in source_paths:
                    if first != second and (second + "/").startswith(first + "/"):
                        raise ValueError(f"Nested repo projects are unsupported: {first} / {second}")
            manifest = ET.parse(ROOT / "config/sources/openharmony.lock.xml").getroot()
            for project in manifest.findall("project"):
                revision = project.attrib.get("revision", "")
                if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
                    raise ValueError(f"Unpinned OH project: {project.attrib['name']}")
            subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_integration.py"], cwd=ROOT, check=True)
            print("Integration checks passed")
            return 0
        if args.command == "snapshot":
            destination = new_run(ROOT)
            snapshot(ROOT, destination, env)
            print(destination)
            return 0
        if args.command in ("build", "package", "deploy") and not args.target:
            raise ValueError("component command needs a name; run `./rdkhm components`")
        (ROOT / "out").mkdir(exist_ok=True)
        with (ROOT / "out/.integration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.command == "build":
                return components.build(args.target, env)
            if args.command == "package":
                return components.package(args.target)
            if args.command == "deploy":
                return components.deploy(args.target, args.board, env, args.apply,
                                         args.serial_confirmed)
            if args.target in ("all", "build") and doctor(ROOT, env):
                return 1
            return run_pipeline(ROOT, args.target, env)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error))
        return 1
