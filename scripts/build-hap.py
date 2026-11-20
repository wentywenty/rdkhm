#!/usr/bin/env python3
"""Build, sign and stage one HAP from the patched OpenHarmony tree."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from hvigor_sdk import ensure_sdk_home
from workspace import ROOT, environment


def _first(paths):
    for path in paths:
        if path and path.is_file():
            return path
    return None


def _ensure_sdk_home(root, sdk):
    """Serialize SDK symlink creation across parallel app builds."""
    lock_path = Path(root) / "out/.hap-sdk.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return ensure_sdk_home(root, sdk)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _normalize_hvigor_config(app_dir, tools):
    config = app_dir / "hvigor/hvigor-config.json5"
    plugin = tools / "command-line-tools/hvigor/hvigor-ohos-plugin"
    desired = ('{\n  "modelVersion": "6.0.2",\n  "dependencies": {\n'
               f'    "@ohos/hvigor-ohos-plugin": "file:{plugin}"\n'
               '  }\n}\n')
    if not config.is_file():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(desired)
        print(f"Created hvigor config: {config}")
        return
    text = config.read_text()
    if '"hvigorVersion"' in text or '"@ohos/hvigor-ohos-plugin": "3.0.9"' in text:
        config.write_text(desired)
        print(f"Upgraded hvigor config: {config}")
        return
    updated = text
    if "file:" in updated and str(plugin) not in updated:
        updated = re.sub(r'("@ohos/hvigor-ohos-plugin"\s*:\s*)"file:[^"]*"',
                         lambda match: match.group(1) + f'"file:{plugin}"', updated)
    # hvigor rejects a hvigor-config modelVersion that differs from
    # oh-package.json5; _upgrade_oh_package pins the latter to 6.0.2.
    updated = re.sub(r'("modelVersion"\s*:\s*)"[^"]*"', r'\1"6.0.2"', updated)
    if updated != text:
        config.write_text(updated)
        print(f"Updated hvigor config: {config}")


def _upgrade_build_profile(app_dir):
    profile = app_dir / "build-profile.json5"
    if not profile.is_file():
        return
    text = profile.read_text()
    updated = re.sub(r'("(?:compile|compatible|target)SdkVersion"\s*:\s*)(\d+)',
                     lambda match: match.group(1) + ("20" if int(match.group(2)) < 20 else match.group(2)),
                     text)
    if updated != text:
        profile.write_text(updated)
        print(f"Upgraded SDK levels: {profile}")


def _upgrade_oh_package(app_dir):
    root_package = app_dir / "oh-package.json5"
    if not root_package.is_file():
        root_package.write_text('{\n  "modelVersion": "6.0.2",\n'
                                f'  "name": "{app_dir.name}",\n'
                                '  "version": "1.0.0",\n  "dependencies": {}\n}\n')
        print(f"Created root oh-package: {root_package}")
    changed = 0
    for package in app_dir.rglob("oh-package.json5"):
        if any(part in {".hvigor", "oh_modules", "node_modules", "build"} for part in package.parts):
            continue
        text = package.read_text()
        if '"modelVersion"' in text:
            updated = re.sub(r'("modelVersion"\s*:\s*)"[^"]*"', r'\1"6.0.2"', text)
        else:
            updated = re.sub(r"\{", '{\n  "modelVersion": "6.0.2",', text, count=1)
        if updated != text:
            package.write_text(updated)
            changed += 1
    if changed:
        print(f"Upgraded {changed} oh-package modelVersion file(s)")


def _node_dir(tree):
    root = tree / "prebuilts/build-tools/common/nodejs"
    current = root / "current"
    if current.is_dir():
        return current
    candidates = sorted(root.glob("node-v*-linux-x64"))
    if not candidates:
        raise RuntimeError(f"Missing node runtime under {root}")
    return candidates[-1]


def _write_local_properties(app_dir, sdk, node_dir):
    content = f"sdk.dir={sdk}\nnodejs.dir={node_dir}\n"
    path = app_dir / "local.properties"
    if not path.is_file() or path.read_text() != content:
        path.write_text(content)
    return path


OFFICIAL_KEY_ALIAS = "openharmony application release"
OFFICIAL_LEAF_FINGERPRINT = (
    "8E:93:86:3F:C3:2E:E2:38:06:0B:F6:9A:9B:37:E2:60:8F:FF:B2:1F:93:C8:62:DD:51:1C:BA:C9:F3:00:24:B5")


def _key_alias(env):
    return env.get("RDKHM_HAP_KEY_ALIAS", OFFICIAL_KEY_ALIAS)


def _official_materials(env):
    tree = Path(env["RDKHM_OH_TREE"])
    keystore = _first([
        Path(env["RDKHM_HAP_KEYSTORE"]) if env.get("RDKHM_HAP_KEYSTORE") else None,
        tree / "developtools/hapsigner/dist/OpenHarmony.p12",
        tree / "applications/standard/launcher/signature/OpenHarmony.p12",
    ])
    cert = _first([
        Path(env["RDKHM_HAP_CERT"]) if env.get("RDKHM_HAP_CERT") else None,
        tree / "developtools/hapsigner/dist/OpenHarmonyApplication.pem",
        tree / "applications/standard/launcher/signature/OpenHarmonyApplication.cer",
    ])
    if not keystore or not cert:
        raise RuntimeError(
            "Official OpenHarmony signing material is missing; expected "
            "developtools/hapsigner/dist/OpenHarmony.p12 and OpenHarmonyApplication.pem")
    return keystore, cert


def _profile_for(app_dir, app, env):
    if env.get("RDKHM_HAP_PROFILE"):
        profile = Path(env["RDKHM_HAP_PROFILE"])
        if not profile.is_file():
            raise RuntimeError(f"RDKHM_HAP_PROFILE does not exist: {profile}")
        return profile
    signature_dirs = [app_dir / name for name in ("signature", "sign", "signs")
                      if (app_dir / name).is_dir()]
    profiles = [path for directory in signature_dirs for path in sorted(directory.glob("*.p7b"))]
    if not profiles:
        raise RuntimeError(
            f"No signing profile for {app}; add a bundle-matched .p7b under "
            f"{app_dir}/signature (see docs/hap-signing.md)")
    return next((path for path in profiles if path.name == f"{app}.p7b"), profiles[0])


def _sign_tool(env):
    tree = Path(env["RDKHM_OH_TREE"])
    tools = Path(env["RDKHM_COMMAND_LINE_TOOLS"])
    return _first([
        Path(env["RDKHM_HAP_SIGN_TOOL"]) if env.get("RDKHM_HAP_SIGN_TOOL") else None,
        tree / "prebuilts/ohos-sdk/linux/20/toolchains/lib/hap-sign-tool.jar",
        tools / "command-line-tools/sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar",
    ])


def _cert_fingerprint(path):
    if shutil.which("openssl") is None:
        raise RuntimeError("openssl not found; required to verify the official signer")
    result = subprocess.run(
        ["openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"],
        capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"cannot read certificate: {path}")
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", result.stdout)
    if not match:
        raise RuntimeError(f"cannot parse certificate fingerprint: {path}")
    return match.group(1).upper()


def _hap_leaf_fingerprint(hap, env):
    if shutil.which("java") is None:
        return None
    sign_tool = _sign_tool(env)
    if not sign_tool:
        return None
    with tempfile.TemporaryDirectory(prefix="hap-verify-") as tmp:
        chain = Path(tmp) / "chain.cer"
        result = subprocess.run(
            ["java", "-jar", str(sign_tool), "verify-app", "-inFile", str(hap),
             "-outCertChain", str(chain), "-outProfile", str(Path(tmp) / "profile.p7b")],
            capture_output=True)
        if result.returncode or not chain.is_file():
            return None
        try:
            return _cert_fingerprint(chain)
        except RuntimeError:
            return None


def _official_fingerprint(env):
    override = env.get("RDKHM_HAP_EXPECTED_FINGERPRINT")
    if override:
        return override.strip().upper()
    tree = Path(env["RDKHM_OH_TREE"])
    reference = tree / "applications/standard/hap"
    candidates = [reference / name for name in ("Launcher.hap", "SystemUI.hap", "Settings.hap")]
    candidates += sorted(reference.glob("*.hap"))
    seen = set()
    for hap in candidates:
        if hap in seen or not hap.is_file():
            continue
        seen.add(hap)
        fingerprint = _hap_leaf_fingerprint(hap, env)
        if fingerprint:
            return fingerprint
    return OFFICIAL_LEAF_FINGERPRINT


def _is_officially_signed(hap, env):
    try:
        expected = _official_fingerprint(env)
    except RuntimeError:
        return False
    fingerprint = _hap_leaf_fingerprint(hap, env)
    return fingerprint is not None and fingerprint == expected


def _sign_hap(unsigned, app_dir, app, env):
    if shutil.which("java") is None:
        raise RuntimeError("java not found; install a JRE (or use --no-sign for debugging only)")
    sign_tool = _sign_tool(env)
    if not sign_tool:
        raise RuntimeError("hap-sign-tool.jar not found; cannot sign with the official key")
    keystore, cert = _official_materials(env)
    profile = _profile_for(app_dir, app, env)
    alias = _key_alias(env)
    key_pwd = env.get("RDKHM_HAP_KEY_PWD")
    store_pwd = env.get("RDKHM_HAP_STORE_PWD")
    if not key_pwd or not store_pwd:
        raise RuntimeError(
            "Set RDKHM_HAP_KEY_PWD and RDKHM_HAP_STORE_PWD in config/workspace.local.json")
    signed = unsigned.with_name(f"{unsigned.stem}-signed.hap")
    log_path = ROOT / "out/logs" / f"sign-hap-{app}.log"
    command = ["java", "-jar", str(sign_tool), "sign-app", "-mode", "localSign",
               "-signAlg", "SHA256withECDSA", "-keyAlias", alias,
               "-keyPwd", key_pwd, "-keystorePwd", store_pwd,
               "-keystoreFile", str(keystore), "-appCertFile", str(cert),
               "-profileFile", str(profile), "-inFile", str(unsigned),
               "-outFile", str(signed)]
    with log_path.open("w") as log:
        log.write(" ".join(command) + "\n")
        log.flush()
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"HAP signing failed; see {log_path}")
    os.replace(signed, unsigned)
    if not _is_officially_signed(unsigned, env):
        raise RuntimeError(f"Official signature verification failed: {unsigned}; see {log_path}")
    print(f"Signed {unsigned} with official key alias {alias}")
    return unsigned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default="settings")
    parser.add_argument("--force", action="store_true",
                        help="build an app whose SDK/product path is not verified")
    parser.add_argument("--no-sign", action="store_true", help="keep the HAP unsigned")
    parser.add_argument("--list", action="store_true", help="list registered HAP projects")
    parser.add_argument("--all", action="store_true", help="build every registered HAP")
    parser.add_argument("--only", metavar="NAMES",
                        help="comma-separated app subset for --all")
    parser.add_argument("--jobs", type=int, default=1, metavar="N",
                        help="parallel app builds with --all (default: 1)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be >= 1")
    if args.only and not args.all:
        parser.error("--only requires --all")
    if args.no_sign:
        print("WARN: --no-sign produces unsigned HAPs; never use them in an image", flush=True)
    apps = json.loads((ROOT / "config/build/haps.json").read_text())["apps"]
    if args.list:
        for name in sorted(apps):
            entry = apps[name]
            print(f"{name:28} product={entry['product']:8} "
                  f"verified={str(entry['verified']):5} {entry.get('bundle', '')}")
        return 0
    if args.all:
        names = sorted(apps)
        if args.only:
            requested = {item for item in args.only.replace(",", " ").split() if item}
            unknown = sorted(requested - set(apps))
            if unknown:
                parser.error(f"unknown --only apps: {', '.join(unknown)}")
            names = [name for name in names if name in requested]
            if not names:
                parser.error("--only selected no apps")

        def command_for(name):
            command = [sys.executable, str(Path(__file__)), name]
            if args.force:
                command.append("--force")
            if args.no_sign:
                command.append("--no-sign")
            return command

        if args.jobs > 1:
            # Serialize the shared SDK symlink setup before workers start.
            env = environment()
            _ensure_sdk_home(ROOT, Path(env["RDKHM_OH_SDK"]))

        results = []
        if args.jobs == 1:
            for name in names:
                print(f"===== {name} =====", flush=True)
                results.append((name, subprocess.run(command_for(name)).returncode))
        else:
            def run_one(name):
                result = subprocess.run(command_for(name), capture_output=True, text=True)
                return name, result.returncode, result.stdout, result.stderr

            print(f"Building {len(names)} HAPs with {args.jobs} workers", flush=True)
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {pool.submit(run_one, name): name for name in names}
                for future in as_completed(futures):
                    name, code, output, errors = future.result()
                    print(f"===== {name} {'OK' if code == 0 else 'FAILED'} =====", flush=True)
                    if output:
                        print(output, end="")
                    if errors:
                        print(errors, end="", file=sys.stderr)
                    results.append((name, code))
        failed = sorted(name for name, code in results if code)
        print(f"Built {len(results) - len(failed)}/{len(results)} HAPs; "
              f"failed: {', '.join(failed) if failed else 'none'}")
        return 1 if failed else 0
    if args.app not in apps:
        raise ValueError(f"Unknown HAP app: {args.app}; configured: {', '.join(sorted(apps))}")
    entry = apps[args.app]
    if not entry.get("verified") and not args.force:
        raise RuntimeError(
            f"HAP '{args.app}' has no verified SDK/product configuration; "
            f"use --force only after confirming the matching SDK version")
    env = environment()
    tree = Path(env["RDKHM_OH_TREE"])
    tools = Path(env["RDKHM_COMMAND_LINE_TOOLS"])
    app_dir = tree / entry["dir"]
    sdk = Path(env["RDKHM_OH_SDK"])
    sdk_home = _ensure_sdk_home(ROOT, sdk)
    node_dir = _node_dir(tree)
    node_bin = node_dir / "bin"
    hvigorw = tools / "command-line-tools/bin/hvigorw"
    for path, label in ((app_dir, "app source"), (sdk, "SDK"),
                        (sdk_home, "SDK home"),
                        (node_bin / "node", "node"), (hvigorw, "hvigorw")):
        if not path.exists():
            raise RuntimeError(f"Missing {label}: {path}")

    _normalize_hvigor_config(app_dir, tools)
    _upgrade_build_profile(app_dir)
    _upgrade_oh_package(app_dir)
    local_properties = _write_local_properties(app_dir, sdk_home, node_dir)
    print(f"Generated {local_properties}", flush=True)

    logs = ROOT / "out/logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"build-hap-{args.app}.log"
    command = [str(hvigorw), "assembleHap", "--mode", "module",
               "-p", f"product={entry['product']}", "-p", "debuggable=false", "--no-daemon"]
    run_env = env.copy()
    run_env["PATH"] = f"{node_bin}:{run_env.get('PATH', '')}"
    run_env["NODE_HOME"] = str(node_dir)
    run_env["OHOS_SDK_HOME"] = str(sdk_home)
    run_env["OHOS_BASE_SDK_HOME"] = str(sdk_home)
    local_deps = False
    for package in app_dir.rglob("oh-package.json5"):
        if any(part in {".hvigor", "oh_modules", "node_modules", "build"}
               for part in package.parts):
            continue
        text = package.read_text()
        # Local modules appear as either "file:../x" or a plain "../x" path.
        if '"file:' in text or re.search(r'":\s*"?(?:file:)?\.\.?/', text):
            local_deps = True
            break
    if local_deps:
        ohpm = _first([tools / "command-line-tools/bin/ohpm",
                       tools / "command-line-tools/ohpm/bin/ohpm"])
        if not ohpm:
            raise RuntimeError(f"ohpm client not found under {tools}")
        ohpm_log = logs / f"ohpm-{args.app}.log"
        print(f"{ohpm} install --all", flush=True)
        with ohpm_log.open("w") as log:
            result = subprocess.run([str(ohpm), "install", "--all"], cwd=app_dir,
                                    env=run_env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"ohpm install failed; see {ohpm_log}")
    print(" ".join(command), flush=True)
    with log_path.open("w") as log:
        result = subprocess.run(command, cwd=app_dir, env=run_env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"HAP build failed; see {log_path}")

    outputs = sorted(app_dir.glob("**/build/default/outputs/*/*.hap"),
                     key=lambda path: path.stat().st_mtime)
    if not outputs:
        raise RuntimeError(f"No HAP produced under {app_dir}; see {log_path}")
    modules = entry.get("modules") or {}
    if modules:
        module_dir = ROOT / "out/haps" / args.app
        module_dir.mkdir(parents=True, exist_ok=True)
        for target_name, source_name in modules.items():
            matches = [path for path in outputs if path.name == source_name]
            if not matches:
                signed_name = source_name.replace("-unsigned", "-signed")
                matches = [path for path in outputs if path.name == signed_name]
            if not matches:
                raise RuntimeError(f"Missing module output {source_name} under {app_dir}")
            source = matches[0]
            target = module_dir / target_name
            shutil.copyfile(source, target)
            print(f"Staged {target} from {source.relative_to(app_dir)}")
            if not args.no_sign and not _is_officially_signed(target, env):
                _sign_hap(target, app_dir, args.app, env)
        entry_hap = module_dir / "SystemUI.hap"
        if args.app == "systemui" and entry_hap.is_file():
            shutil.copyfile(entry_hap, ROOT / "out/haps/systemui.hap")
        return 0
    entry_phone = [path for path in outputs if "entry" in path.parts and "phone" in path.parts]
    product_phone = [path for path in outputs
                     if "product" in path.parts and "phone" in path.parts]
    phone_builds = [path for path in outputs if "phone" in path.parts or "phone" in path.name]
    candidates = entry_phone or product_phone or phone_builds or outputs
    unsigned_candidates = [path for path in candidates if path.name.endswith("-unsigned.hap")]
    chosen = (unsigned_candidates or candidates)[-1]
    destination_dir = ROOT / "out/haps"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{args.app}.hap"
    shutil.copyfile(chosen, destination)
    print(f"Built {destination} from {chosen.relative_to(app_dir)}")
    if not args.no_sign:
        if _is_officially_signed(destination, env):
            print(f"Keeping official signature: {destination}")
            (ROOT / "out/logs" / f"sign-hap-{args.app}.log").write_text(
                "verify-app success; kept the official OpenHarmony signature\n")
        else:
            _sign_hap(destination, app_dir, args.app, env)
    else:
        print("WARN: --no-sign leaves the HAP unsigned; do not use it in an image", flush=True)
    if args.app == "settings":
        # Image assembly consumes this legacy path; keep both HAP entry points
        # producing the same artifact.
        staged = ROOT / "out/settings/Settings.hap"
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(destination, staged)
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        staged.with_suffix(".hap.sha256").write_text(f"{digest}  {staged}\n")
        print(f"Staged {staged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
