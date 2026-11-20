#!/usr/bin/env python3
"""Resolve the unified HAP-to-system-image manifest.

The mapping lives under the top-level ``image`` key of
``config/build/haps.json`` so image assembly and verification share one
source of truth.  Sources are resolved in declaration order; the first
existing path wins (Settings falls back to ``out/haps``).
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest(workspace=ROOT):
    root = Path(workspace)
    registry = json.loads((root / "config/build/haps.json").read_text())
    apps = registry["apps"]
    spec = registry.get("image", {})
    base = spec.get("system_app_dir", "/system/app")
    optional = set(spec.get("optional", []))
    entries = []

    def add(app, filename, sources, is_optional, bundle=None):
        entries.append({
            "app": app,
            "bundle": bundle or apps[app]["bundle"],
            "dest": f"{base}/{bundle or apps[app]['bundle']}/{filename}",
            "sources": [Path(source) for source in sources],
            "optional": is_optional,
        })

    for app, filename in spec.get("apps", {}).items():
        if app == "settings":
            sources = [root / "out/settings/Settings.hap",
                       root / "out/haps/settings.hap"]
        else:
            sources = [root / "out/haps" / f"{app}.hap"]
        add(app, filename, sources, app in optional)

    for app, source_dir in spec.get("modules", {}).items():
        for module in apps[app].get("modules", {}):
            add(app, module, [root / source_dir / module], app in optional)

    for extra in spec.get("extra", []):
        entries.append({
            "app": extra["name"],
            "bundle": extra.get("bundle", ""),
            "dest": extra["dest"],
            "sources": [root / extra["source"]],
            "optional": bool(extra.get("optional")),
        })
    return entries


def source_of(entry):
    for path in entry["sources"]:
        if path.is_file():
            return path
    return None


def check(entries):
    problems = []
    destinations = {}
    for entry in entries:
        previous = destinations.get(entry["dest"])
        if previous:
            problems.append(
                f"duplicate destination {entry['dest']}: "
                f"{previous} and {entry['app']}")
        destinations[entry["dest"]] = entry["app"]
        source = source_of(entry)
        if source is None:
            if not entry["optional"]:
                problems.append(
                    f"missing required HAP for {entry['app']}: "
                    f"{entry['sources'][0]}")
            continue
        try:
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                if "module.json" not in names:
                    problems.append(f"missing module.json: {source}")
                bad = archive.testzip()
                if bad is not None:
                    problems.append(f"corrupt entry {bad}: {source}")
        except zipfile.BadZipFile:
            problems.append(f"not a valid HAP archive: {source}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--tsv", action="store_true",
                       help="print source<TAB>destination for present HAPs")
    group.add_argument("--json", action="store_true",
                       help="print the resolved manifest as JSON")
    group.add_argument("--check", action="store_true",
                       help="validate required sources and archive integrity")
    args = parser.parse_args()

    entries = manifest(ROOT)
    if args.check:
        problems = check(entries)
        for problem in problems:
            print(f"ERROR {problem}", file=sys.stderr)
        if problems:
            print(f"{len(problems)} image HAP problem(s)", file=sys.stderr)
            return 1
        print(f"Image HAP manifest OK: {len(entries)} entries")
        return 0

    resolved = []
    for entry in entries:
        source = source_of(entry)
        if source is None:
            if not entry["optional"]:
                print(f"ERROR missing required HAP for {entry['app']}: "
                      f"{entry['sources'][0]}", file=sys.stderr)
                return 1
            continue
        resolved.append({**entry, "source": source})

    if args.json:
        print(json.dumps([{
            "app": entry["app"],
            "bundle": entry["bundle"],
            "source": str(entry["source"]),
            "dest": entry["dest"],
            "optional": entry["optional"],
        } for entry in resolved], indent=2))
        return 0

    for entry in resolved:
        try:
            source = entry["source"].relative_to(ROOT)
        except ValueError:
            source = entry["source"]
        print(f"{source}\t{entry['dest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
