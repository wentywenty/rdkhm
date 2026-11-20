#!/usr/bin/env python3
"""Component-scoped build, package and controlled board deploy."""
import hashlib
import json
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from workspace import ROOT

STATUS_MARKER = "__RDKHM_STATUS:"
KERNEL_RELEASE = "${KERNEL_RELEASE}"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value):
    """Expand the kernel-release placeholder in a component path."""
    if "${" not in value:
        return value
    if KERNEL_RELEASE not in value:
        raise RuntimeError(f"Unsupported placeholder in path: {value}")
    remaining = value.replace(KERNEL_RELEASE, "")
    if "${" in remaining:
        raise RuntimeError(f"Unsupported placeholder in path: {value}")
    release_file = ROOT / "out/kernel/obj/include/config/kernel.release"
    if not release_file.is_file():
        raise RuntimeError(f"Missing kernel release; build the kernel first: {release_file}")
    release = release_file.read_text().strip()
    if not release:
        raise RuntimeError(f"Empty kernel release: {release_file}")
    return value.replace(KERNEL_RELEASE, release)


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load():
    data = json.loads((ROOT / "config/build/components.json").read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported config/build/components.json schema")
    return data["components"]


def get(name):
    components = load()
    if name not in components:
        raise ValueError(f"Unknown component: {name}; run `./rdkhm components`")
    return components[name]


def listing():
    for name, component in load().items():
        kind = (component.get("deploy") or {}).get("kind", "-")
        print(f"{name:14} {kind:10} {component.get('description', '')}")


def _run_dir(name):
    base = ROOT / "out/components" / name
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    return Path(tempfile.mkdtemp(prefix=stamp, dir=base))


def _run_commands(commands, env, log_path):
    with log_path.open("w") as log:
        for command in commands:
            line = shlex.join(command)
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f"Failed ({result.returncode}): {line}")


def build(name, env):
    component = get(name)
    commands = component.get("build") or []
    if not commands:
        raise ValueError(f"Component {name} has no build commands")
    run_dir = _run_dir(name)
    report = {"component": name, "operation": "build", "status": "running", "commands": commands}
    write_json(run_dir / "run.json", report)
    try:
        _run_commands(commands, env, run_dir / "build.log")
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        write_json(run_dir / "run.json", report)
    print(f"Build evidence: {run_dir}")
    return 0


def package(name):
    component = get(name)
    artifacts = (component.get("package") or {}).get("artifacts") or []
    if not artifacts:
        raise ValueError(f"Component {name} has no package artifacts")
    run_dir = _run_dir(name)
    stage = ROOT / "out/stage" / name
    if stage.is_symlink() or stage.is_file():
        stage.unlink()
    elif stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files = []
    for item in artifacts:
        relative_path = resolve_path(item["path"])
        source = ROOT / relative_path
        if not source.exists():
            raise RuntimeError(f"Missing artifact; build {name} first: {source}")
        relative = item.get("stage", source.name)
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        record = dict(item)
        record["path"] = relative_path
        record["stage"] = Path(relative).as_posix()
        if target.is_file():
            record["sha256"] = sha(target)
            record["bytes"] = target.stat().st_size
        files.append(record)
    manifest = {"component": name, "created_utc": datetime.now(timezone.utc).isoformat(), "files": files}
    write_json(stage / "manifest.json", manifest)
    shutil.copyfile(stage / "manifest.json", run_dir / "manifest.json")
    for record in files:
        digest = record.get("sha256", "-")[:16]
        print(f"  {digest}  {record['stage']} -> {record.get('remote', '(stage only)')}")
    print(f"Staged {len(files)} artifact(s): {stage}")
    return 0


def _hdc(env):
    candidates = []
    if env.get("RDKHM_HDC"):
        candidates.append(Path(env["RDKHM_HDC"]))
    if env.get("RDKHM_OH_SDK"):
        candidates.append(Path(env["RDKHM_OH_SDK"]) / "toolchains/hdc")
    for local in candidates:
        if local.is_file():
            return str(local)
    found = shutil.which("hdc", path=env.get("PATH"))
    if found:
        return found
    raise RuntimeError(f"hdc client not found: {candidates[-1] if candidates else 'hdc'}")


def _hdc_send(hdc, board, local, remote):
    result = subprocess.run(["timeout", "60", hdc, "-t", board, "file", "send", str(local), remote],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"hdc file send failed: {local} -> {remote}\n{result.stdout}{result.stderr}")


def _remote(hdc, board, command, timeout=45):
    script = f"set -e; {{ {command}; }}; result=$?; echo {STATUS_MARKER}$result"
    result = subprocess.run(["timeout", str(timeout), hdc, "-t", board, "shell", script],
                            capture_output=True, text=True)
    text = result.stdout.replace("\r", "")
    status = None
    body = []
    for line in text.splitlines():
        if line.startswith(STATUS_MARKER):
            status = line[len(STATUS_MARKER):].strip()
        else:
            body.append(line)
    if result.returncode or status != "0":
        detail = "\n".join(body + ([result.stderr.strip()] if result.stderr.strip() else []))
        raise RuntimeError(f"Remote command failed: {command}\n{detail}")
    return "\n".join(body)


def _verify_remote_sha(hdc, board, remote, expected):
    output = _remote(hdc, board, f"/rdkhm/busybox sha256sum {remote}")
    fields = output.split()
    if not fields or fields[0] != expected:
        raise RuntimeError(f"Remote checksum mismatch: {remote}")


def _deploy_libs(hdc, board, config, manifest, stage, remote_stage):
    installs = [record for record in manifest["files"]
                if record.get("remote") and record.get("deploy", True) and record.get("sha256")]
    if not installs:
        raise RuntimeError("No deployable libraries in the staged manifest")

    for record in installs:
        local = stage / record["stage"]
        remote_temp = f"{remote_stage}/{local.name}"
        _hdc_send(hdc, board, local, remote_temp)
        _verify_remote_sha(hdc, board, remote_temp, record["sha256"])

    modules = []
    for module in config.get("modules") or []:
        local = ROOT / resolve_path(module["path"])
        if not local.is_file():
            raise RuntimeError(f"Missing module: {local}")
        remote_temp = f"{remote_stage}/{local.name}"
        _hdc_send(hdc, board, local, remote_temp)
        _verify_remote_sha(hdc, board, remote_temp, sha(local))
        modules.append((module["name"], remote_temp))

    for directory in config.get("directories") or []:
        _remote(hdc, board, f"mkdir -p {directory} && chmod 0711 {directory}")

    installed = []
    mounts = sorted({record.get("mount", "/") for record in installs})
    try:
        for mount in mounts:
            _remote(hdc, board, f"/rdkhm/busybox mount -o remount,rw {mount}")
            for record in [item for item in installs if item.get("mount", "/") == mount]:
                local = stage / record["stage"]
                destination = record["remote"]
                backup = f"{remote_stage}/original/{local.name}"
                _remote(hdc, board,
                        f"if test -f {destination}; then /rdkhm/busybox cp -p {destination} {backup}; fi")
                _remote(hdc, board,
                        f"/rdkhm/busybox cp {remote_stage}/{local.name} {destination}.rdkhm-new"
                        f" && chmod 0644 {destination}.rdkhm-new"
                        f" && chown root:root {destination}.rdkhm-new"
                        f" && /rdkhm/busybox mv {destination}.rdkhm-new {destination}")
                _verify_remote_sha(hdc, board, destination, record["sha256"])
                installed.append((destination, backup))
            _remote(hdc, board, f"/rdkhm/busybox mount -o remount,ro {mount}")
        for module_name, remote_temp in modules:
            _remote(hdc, board,
                    f"if test ! -d /sys/module/{module_name}; then /rdkhm/busybox insmod {remote_temp}; fi")
        for action, service in config.get("restart") or []:
            _remote(hdc, board, f"service_control {action} {service}")
            if action == "stop":
                time.sleep(1)
    except BaseException:
        for destination, backup in reversed(installed):
            try:
                _remote(hdc, board,
                        f"if test -f {backup}; then /rdkhm/busybox cp -p {backup} {destination}; fi")
            except Exception:
                pass
        for mount in mounts:
            try:
                _remote(hdc, board, f"/rdkhm/busybox mount -o remount,ro {mount}")
            except Exception:
                pass
        raise


def _deploy_modules(hdc, board, config, manifest, stage, remote_stage):
    records = manifest["files"]
    config_record = next((record for record in records
                          if record.get("remote") and record.get("deploy", True)), None)
    module_records = [record for record in records if record["stage"].endswith(".ko")]
    for record in module_records + ([config_record] if config_record else []):
        local = stage / record["stage"]
        remote_temp = f"{remote_stage}/{local.name}"
        _hdc_send(hdc, board, local, remote_temp)
        if record.get("sha256"):
            _verify_remote_sha(hdc, board, remote_temp, record["sha256"])

    if config_record:
        local = stage / config_record["stage"]
        destination = config_record["remote"]
        mount = config_record.get("mount", "/vendor")
        backup = f"{remote_stage}/original/{local.name}"
        _remote(hdc, board,
                f"if test -f {destination}; then /rdkhm/busybox cp -p {destination} {backup}; fi")
        _remote(hdc, board, f"/rdkhm/busybox mount -o remount,rw {mount}")
        try:
            _remote(hdc, board,
                    f"/rdkhm/busybox cp {remote_stage}/{local.name} {destination} && chmod 0644 {destination}")
        finally:
            _remote(hdc, board, f"/rdkhm/busybox mount -o remount,ro {mount}")

    modules = {Path(record["stage"]).stem: record for record in module_records}
    for module_name in config.get("load_order") or []:
        record = modules.get(module_name)
        if not record:
            raise RuntimeError(f"Missing staged module: {module_name}")
        local = stage / record["stage"]
        remote_temp = f"{remote_stage}/{local.name}"
        _remote(hdc, board,
                f"if test ! -d /sys/module/{module_name}; then /rdkhm/busybox insmod {remote_temp}; fi")


def check_serial_confirmation(name, config, apply, serial_confirmed):
    if config.get("serial_required") and apply and not serial_confirmed:
        raise ValueError(
            f"{name}: deploy requires serial console access; "
            "re-run with --apply --serial-confirmed after confirming the serial console")


def deploy(name, board, env, apply, serial_confirmed=False):
    component = get(name)
    config = component.get("deploy") or {}
    kind = config.get("kind")
    if kind in (None, "none"):
        raise ValueError(f"Component {name} has no deploy definition")
    if kind == "image":
        message = f"{name}: hot deploy is not supported: {config.get('reason', 'assemble the image instead')}"
        if apply:
            raise ValueError(message)
        print(message)
        return 0
    if kind not in ("libs", "modules"):
        raise ValueError(f"Unsupported deploy kind for {name}: {kind}")

    stage = ROOT / "out/stage" / name
    manifest_path = stage / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Run `./rdkhm package {name}` first")
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["files"]:
        local = stage / record["stage"]
        if record.get("sha256") and sha(local) != record["sha256"]:
            raise RuntimeError(f"Staged artifact changed after packaging: {record['stage']}")

    if not board:
        raise ValueError("deploy needs <component> <target:port>")
    print(f"component: {name} ({kind})")
    print(f"board:     {board}")
    print(f"mode:      {'apply' if apply else 'dry-run'}")
    for record in manifest["files"]:
        if record.get("remote") and record.get("deploy", True):
            print(f"  {record.get('sha256', '-')[:16]}  {record['stage']} -> {record['remote']}")
    if kind == "modules":
        print("  insmod order: " + ", ".join(config.get("load_order") or []))
    if config.get("serial_required"):
        print("serial:    required (--serial-confirmed is needed with --apply)")
    if not apply:
        print("dry-run only; confirm serial access before adding --apply")
        return 0
    check_serial_confirmation(name, config, apply, serial_confirmed)

    hdc = _hdc(env)
    _remote(hdc, board, "id")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    remote_stage = f"/data/rdkhm-fixes/{name}-{stamp}"
    _remote(hdc, board, f"mkdir -p {remote_stage}/original")
    if kind == "libs":
        _deploy_libs(hdc, board, config, manifest, stage, remote_stage)
    else:
        _deploy_modules(hdc, board, config, manifest, stage, remote_stage)
    print(f"Deployed {name}. Remote backup: {remote_stage}/original")
    return 0
