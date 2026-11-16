#!/usr/bin/env python3
"""Local settings shared by the CLI and Python preparation scripts."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH_KEYS = {"RDKHM_BSP", "RDKHM_NEARLINK_REFERENCE", "RDKHM_REGDB", "RDKHM_WS73_ARCHIVE"}
KEYS = PATH_KEYS | {"CROSS_COMPILE", "JOBS", "SYNC_JOBS", "RDKHM_HOST_GCC_DIR"}


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
    for key in ("JOBS", "SYNC_JOBS"):
        if key in env and (not env[key].isdigit() or int(env[key]) < 1):
            raise ValueError(f"{key} must be a positive integer")
    return env
