#!/usr/bin/env python3
"""Verify that HAPs carry the official OpenHarmony release signature."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from workspace import ROOT, environment

OFFICIAL_LEAF_FINGERPRINT = (
    "8E:93:86:3F:C3:2E:E2:38:06:0B:F6:9A:9B:37:E2:60:8F:FF:B2:1F:93:C8:62:DD:51:1C:BA:C9:F3:00:24:B5")


def _first(paths):
    for path in paths:
        if path and path.is_file():
            return path
    return None


def _sign_tool(env):
    tree = Path(env["RDKHM_OH_TREE"])
    tools = Path(env["RDKHM_COMMAND_LINE_TOOLS"])
    return _first([
        Path(env["RDKHM_HAP_SIGN_TOOL"]) if env.get("RDKHM_HAP_SIGN_TOOL") else None,
        tree / "prebuilts/ohos-sdk/linux/20/toolchains/lib/hap-sign-tool.jar",
        tools / "command-line-tools/sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar",
    ])


def _fingerprint(path):
    result = subprocess.run(
        ["openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"],
        capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"cannot read certificate: {path}")
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", result.stdout)
    if not match:
        raise RuntimeError(f"cannot parse certificate fingerprint: {path}")
    return match.group(1).upper()


def _hap_leaf_fingerprint(hap, sign_tool):
    with tempfile.TemporaryDirectory(prefix="hap-verify-") as tmp:
        chain = Path(tmp) / "chain.cer"
        result = subprocess.run(
            ["java", "-jar", str(sign_tool), "verify-app", "-inFile", str(hap),
             "-outCertChain", str(chain), "-outProfile", str(Path(tmp) / "profile.p7b")],
            capture_output=True)
        if result.returncode or not chain.is_file():
            return None
        try:
            return _fingerprint(chain)
        except RuntimeError:
            return None


def _official_fingerprint(env, sign_tool):
    override = env.get("RDKHM_HAP_EXPECTED_FINGERPRINT")
    if override:
        return override.strip().upper()
    reference = Path(env["RDKHM_OH_TREE"]) / "applications/standard/hap"
    candidates = [reference / name for name in ("Launcher.hap", "SystemUI.hap", "Settings.hap")]
    candidates += sorted(reference.glob("*.hap"))
    seen = set()
    for hap in candidates:
        if hap in seen or not hap.is_file():
            continue
        seen.add(hap)
        fingerprint = _hap_leaf_fingerprint(hap, sign_tool)
        if fingerprint:
            return fingerprint
    return OFFICIAL_LEAF_FINGERPRINT


def _allowlist(workspace):
    """Fingerprints preinstall trusts, keyed by bundle name."""
    allowed = {}
    base = workspace / "overlay/vendor/drobotics/rdk_x5/preinstall-config"
    for name in ("install_list_capability.json", "install_list_permissions.json"):
        path = base / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text())
        items = data.get("install_list", []) if isinstance(data, dict) else data
        for item in items or []:
            bundle = item.get("bundleName")
            if not bundle:
                continue
            for signature in item.get("app_signature", []):
                normalized = signature.replace(":", "").upper()
                if re.fullmatch(r"[0-9A-F]{64}", normalized):
                    allowed.setdefault(bundle, set()).add(normalized)
    return allowed


def _bundle_name(hap):
    try:
        with zipfile.ZipFile(hap) as archive:
            data = json.loads(archive.read("module.json"))
        return data.get("app", {}).get("bundleName")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("haps", nargs="*", help="HAP files; default: out/haps and out/settings")
    parser.add_argument("--accept-allowlist", action="store_true",
                        help="also accept signers bound to the bundle in the preinstall allowlist")
    args = parser.parse_args()
    env = environment()
    if shutil.which("java") is None:
        raise RuntimeError("java not found; cannot verify HAP signatures")
    if shutil.which("openssl") is None:
        raise RuntimeError("openssl not found; cannot compare signing certificates")
    sign_tool = _sign_tool(env)
    if not sign_tool:
        raise RuntimeError("hap-sign-tool.jar not found")
    expected = _official_fingerprint(env, sign_tool)

    if args.haps:
        paths = [Path(item) for item in args.haps]
    else:
        paths = sorted((ROOT / "out/haps").rglob("*.hap"))
        settings = ROOT / "out/settings/Settings.hap"
        if settings.is_file():
            paths.append(settings)
    paths = [path for path in paths if path.is_file()]
    if not paths:
        print("No HAPs found to verify")
        return 0

    allowed = _allowlist(ROOT) if args.accept_allowlist else {}
    failures = 0
    for hap in paths:
        fingerprint = _hap_leaf_fingerprint(hap, sign_tool)
        ok = fingerprint == expected
        trusted = "official"
        if not ok and args.accept_allowlist and fingerprint:
            normalized = fingerprint.replace(":", "").upper()
            if normalized in allowed.get(_bundle_name(hap), set()):
                ok = True
                trusted = "allowlist"
        try:
            label = str(hap.relative_to(ROOT))
        except ValueError:
            label = str(hap)
        print(("PASS " if ok else "FAIL ") + label
              + (" [allowlist]" if ok and trusted == "allowlist" else ""))
        failures += 0 if ok else 1
    trusted_by = ("the official OpenHarmony key or the image allowlist"
                  if args.accept_allowlist else "the official OpenHarmony key")
    print(f"Checked {len(paths)} HAPs: {failures} not signed by {trusted_by}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
