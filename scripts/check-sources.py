#!/usr/bin/env python3
"""Verify existing source checkouts against config/sources/repo.xml."""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = ET.parse(ROOT / "config/sources/repo.xml").getroot()
    projects = manifest.findall("project")
    failures = []
    for project in projects:
        relative = project.attrib["path"]
        expected = project.attrib["revision"]
        path = ROOT / "sources" / relative
        if not path.exists():
            failures.append(f"missing checkout: {relative}")
            continue
        result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                                capture_output=True, text=True)
        actual = result.stdout.strip()
        if result.returncode or actual != expected:
            failures.append(f"{relative}: {actual or 'not a git checkout'} != {expected}")
    for failure in failures:
        print("FAIL " + failure)
    print(f"Checked {len(projects)} source projects: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
