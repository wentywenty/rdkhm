#!/usr/bin/env python3
"""Index a local board capture without treating duplicate dumps as new crashes."""
import collections
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
crashes = {}
for path in sorted(root.rglob("cppcrash*")):
    if not path.is_file():
        continue
    header = path.read_text(errors="replace").splitlines()[:24]
    fields = dict(line.split(":", 1) for line in header if ":" in line)
    if not all(key in fields for key in ("Pid", "Timestamp", "Process name")):
        continue
    key = (fields["Pid"], fields["Timestamp"], fields["Process name"])
    entry = crashes.setdefault(key, {
        "pid": key[0], "timestamp": key[1], "process": key[2],
        "reason": fields.get("Reason"),
        "fault_frames": [line for line in header if line.startswith("#")][:5],
        "copies": [],
    })
    entry["copies"].append(str(path.relative_to(root)))

files = [p for p in root.rglob("*") if p.is_file()
         and p.name not in ("capture-index.json", "SHA256SUMS")]
result = {
    "file_count_excluding_index_and_checksums": len(files),
    "bytes_excluding_index_and_checksums": sum(p.stat().st_size for p in files),
    "unique_crashes": len(crashes),
    "crashes_by_process": dict(collections.Counter(c["process"] for c in crashes.values())),
    "crashes": list(crashes.values()),
    "error_tags_by_capture": {},
}
for name in ("hilog-start.txt", "hilog-end.txt", "hilog-stream-15s.txt"):
    path = root / name
    if path.exists():
        tags = re.findall(r"\sE\s+[A-Za-z0-9]+/([^:]+):", path.read_text(errors="replace"))
        result["error_tags_by_capture"][name] = dict(collections.Counter(tags).most_common(20))
(root / "capture-index.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "crashes"}, indent=2))
