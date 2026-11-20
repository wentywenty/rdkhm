#!/usr/bin/env python3
"""Enforce the patch file contract: LF, mail header, sign-off and diff style."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = re.compile(
    r"^(new file mode|deleted file mode|old mode|new mode|rename from|rename to|"
    r"similarity index|copy from|copy to|Binary files|GIT binary patch)")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def hunk_problems(lines):
    problems = []
    index = 0
    while index < len(lines):
        match = HUNK.match(lines[index])
        if not match:
            index += 1
            continue
        old = int(match.group(2) or 1)
        new = int(match.group(4) or 1)
        start = index
        index += 1
        while index < len(lines) and (old > 0 or new > 0):
            line = lines[index]
            if line.startswith("\\"):
                index += 1
                continue
            if line.startswith(" "):
                old -= 1
                new -= 1
            elif line.startswith("-"):
                old -= 1
            elif line.startswith("+"):
                new -= 1
            else:
                break
            index += 1
        if old != 0 or new != 0:
            problems.append(f"hunk at line {start + 1} has mismatched line counts")
    return problems


def check(path):
    relative = path.relative_to(ROOT / "patches").as_posix()
    data = path.read_bytes()
    problems = []
    if b"\r" in data:
        problems.append("contains CRLF")
    if not data.endswith(b"\n"):
        problems.append("missing trailing newline")
    text = data.decode("utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("From: "):
        problems.append("missing From header")
    if not any(line.startswith("Subject:") for line in lines[:5]):
        problems.append("missing Subject header")
    if "---" not in lines[:12]:
        problems.append("missing header separator")
    if "Signed-off-by:" not in text:
        problems.append("missing Signed-off-by")
    metadata = any(META.match(line) for line in lines)
    has_git = any(line.startswith("diff --git ") for line in lines)
    has_index = any(line.startswith("index ") for line in lines)
    if metadata and not has_git:
        problems.append("metadata requires git diff --git format")
    if not metadata and has_git:
        problems.append("plain patch must not contain diff --git")
    if not metadata and has_index:
        problems.append("plain patch must not contain index lines")
    problems.extend(hunk_problems(lines))
    return relative, problems


def main():
    paths = sorted((ROOT / "patches").rglob("*.patch"))
    failures = [(relative, problems) for relative, problems in map(check, paths) if problems]
    for relative, problems in failures:
        print(f"FAIL {relative}: {', '.join(problems)}")
    print(f"Checked {len(paths)} patches: {len(failures)} format failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
