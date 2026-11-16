#!/usr/bin/env python3
"""Run existing build stages and retain honest, per-run evidence."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import tarfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

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
    config = json.loads((root / "config/pipeline.json").read_text())
    stages = config["profiles"].get(target, [target])
    if any(stage not in config["stages"] for stage in stages):
        raise ValueError(f"Unknown target: {target}")
    return [(stage, command) for stage in stages for command in config["stages"][stage]]


def integration_files(root):
    files = {}
    for name in ("rdkhm", ".gitignore", ".gitattributes", "README.md", "STATUS.md", "sources.lock.tsv",
                 "config", "scripts", "patches", "overlay", "bringup", "tests", "docs"):
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
    manifest = root / "config/openharmony.lock.xml"
    if not manifest.exists():
        return None
    projects = [(p.attrib.get("path", p.attrib["name"]), p.attrib["revision"])
                for p in ET.parse(manifest).getroot().findall("project")]
    diff_dir = destination / "source-diffs"
    diff_dir.mkdir()

    def inspect(project):
        name, revision = project
        path = root / "sources/openharmony-full" / name
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
    for line in (root / "sources.lock.tsv").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, url, revision = line.split()
        path = root / "sources" / name
        records[name] = {"url": url, "expected_revision": revision,
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
             "resize2fs", "mkimage", "sfdisk", "mkfs.vfat", "mcopy", "simg2img", "modinfo",
             "depmod", "readelf", "dpkg-deb", "aarch64-linux-gnu-gcc"]
    cross = env.get("CROSS_COMPILE", "aarch64-none-linux-gnu-")
    tools += [cross + "gcc"]
    for tool in tools:
        if not shutil.which(tool, path=env.get("PATH")):
            failed.append("missing executable: " + tool)
    bsp = Path(env.get("RDKHM_BSP", str(root / "sources/reference-bsp")))
    reference = Path(env.get("RDKHM_NEARLINK_REFERENCE", str(root / "sources/reference-nearlink")))
    archive = Path(env.get("RDKHM_WS73_ARCHIVE", str(bsp / "packages/blobs/ws73/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz")))
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
    parser.add_argument("command", choices=["doctor", "plan", "run", "snapshot", "check"])
    parser.add_argument("target", nargs="?", default="build")
    args = parser.parse_args()
    try:
        env = environment()
        if args.command == "plan":
            for stage, command in plan(ROOT, args.target):
                print(f"{stage}: {shlex.join(command)}")
            return 0
        if args.command == "doctor":
            return int(doctor(ROOT, env))
        if args.command == "check":
            for path in sorted((ROOT / "scripts").glob("*.sh")):
                subprocess.run(["bash", "-n", str(path)], check=True)
            for path in sorted((ROOT / "config").glob("*.json")):
                json.loads(path.read_text())
            manifest = ET.parse(ROOT / "config/openharmony.lock.xml").getroot()
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
        (ROOT / "out").mkdir(exist_ok=True)
        with (ROOT / "out/.integration.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.target in ("all", "build") and doctor(ROOT, env):
                return 1
            return run_pipeline(ROOT, args.target, env)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error))
        return 1
