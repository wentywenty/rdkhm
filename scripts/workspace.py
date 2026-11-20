#!/usr/bin/env python3
"""Local settings shared by the CLI and Python preparation scripts."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH_KEYS = {
    "RDKHM_BSP", "RDKHM_NEARLINK_REFERENCE", "RDKHM_REGDB", "RDKHM_WS73_ARCHIVE",
    "RDKHM_TOOLS_DIR", "RDKHM_COMMAND_LINE_TOOLS", "RDKHM_OH_TREE", "RDKHM_OH_DEPS_TREE",
    "RDKHM_KERNEL_TREE", "RDKHM_OH_SDK", "RDKHM_HDC", "RDKHM_CACHE_DIR",
    "RDKHM_HAP_SIGN_TOOL", "RDKHM_HVIGOR_SDK",
}
KEYS = PATH_KEYS | {"CROSS_COMPILE", "JOBS", "SYNC_JOBS", "RDKHM_HOST_GCC_DIR",
                    "RDKHM_KERNEL_PROFILE", "RDKHM_HAP_KEY_ALIAS",
                    "RDKHM_HAP_KEY_PWD", "RDKHM_HAP_STORE_PWD"}
KERNEL_PROFILES = ("default", "rt")


def environment(root=ROOT):
    config = root / "config/workspace.local.json"
    values = json.loads(config.read_text()) if config.exists() else {}
    if not isinstance(values, dict) or set(values) - KEYS:
        raise ValueError("Invalid workspace settings; see config/workspace.example.json")
    env = os.environ.copy()
    for key, value in values.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"Expected nonempty string for {key}")
        env.setdefault(key, value)
    for key in PATH_KEYS:
        if key in env:
            path = Path(env[key]).expanduser()
            env[key] = str(path if path.is_absolute() else root / path)
    defaults = {
        "RDKHM_TOOLS_DIR": str(root / "thirdparty"),
        "RDKHM_OH_TREE": str(root / "sources/oh/openharmony-full"),
        "RDKHM_OH_DEPS_TREE": str(root / "sources/oh/openharmony"),
        "RDKHM_KERNEL_TREE": str(root / "sources/rdk/x5-kernel"),
    }
    for key, value in defaults.items():
        env.setdefault(key, value)
    env.setdefault("RDKHM_COMMAND_LINE_TOOLS",
                   str(Path(env["RDKHM_TOOLS_DIR"]) / "toolchains/command-line-tools-26"))
    env.setdefault("RDKHM_OH_SDK",
                   str(Path(env["RDKHM_OH_TREE"]) / "prebuilts/ohos-sdk/linux/20"))
    env.setdefault("RDKHM_HVIGOR_SDK",
                   str(root / "out/sdk" / f"openharmony-{Path(env['RDKHM_OH_SDK']).name}"))
    env.setdefault("RDKHM_HDC", str(Path(env["RDKHM_OH_SDK"]) / "toolchains/hdc"))
    env.setdefault("RDKHM_CACHE_DIR", str(Path(env["RDKHM_TOOLS_DIR"]) / "downloads"))
    env.setdefault("RDKHM_WS73_ARCHIVE",
                   str(Path(env["RDKHM_CACHE_DIR"]) / "ws73_sdk_linux_WS73_1.10.110_patched.tar.gz"))
    for key in ("JOBS", "SYNC_JOBS"):
        if key in env and (not env[key].isdigit() or int(env[key]) < 1):
            raise ValueError(f"{key} must be a positive integer")
    env.setdefault("RDKHM_KERNEL_PROFILE", "default")
    if env["RDKHM_KERNEL_PROFILE"] not in KERNEL_PROFILES:
        raise ValueError(f"RDKHM_KERNEL_PROFILE must be one of {', '.join(KERNEL_PROFILES)}")
    return env
