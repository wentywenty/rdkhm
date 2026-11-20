#!/usr/bin/env python3
"""Reject patch files that are not listed in config/patches.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / "config/patches.json").read_text())
    listed = {entry["patch"] for entries in data["collections"].values() for entry in entries}
    globbed = set(data.get("globs", {}))
    missing = []
    for patch in sorted((ROOT / "patches").rglob("*.patch")):
        relative = patch.relative_to(ROOT / "patches").as_posix()
        if relative.startswith("optional/"):
            continue
        if relative.split("/", 1)[0] in globbed:
            continue
        if relative not in listed:
            missing.append(relative)
    if missing:
        for name in missing:
            print(f"FAIL orphan patch (not in config/patches.json): {name}")
        return 1
    total = len(list((ROOT / "patches").rglob("*.patch")))
    print(f"PASS: {len(listed)} patches are listed in config/patches.json "
          f"({total} files present; optional/globbed files are not required)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
