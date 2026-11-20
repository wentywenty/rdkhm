#!/usr/bin/env python3
"""Summarize an RDK X5 serial or hilog capture by failure domain."""
import argparse
import collections
import re
from pathlib import Path

CATEGORIES = [
    ("critical", re.compile(
        r"\bpanic\b|\bOops\b|\bBUG:|\bwatchdog\b|\bwdt\b|pretimeout|"
        r"PM: suspend|PM: resume|BootROM|thermal|undervolt|"
        r"reset reason|hardware reset|Kernel panic", re.I)),
    ("init", re.compile(
        r"\[Init\]|ServiceStart|ServiceExec|init_service|init_common|"
        r"init_config|init_cmds|init_trace|init.rdk_x5", re.I)),
    ("hdf", re.compile(
        r"\bhdf\b|\bHDI\b|LoadHdi|devhost|devmgr|devsvc|"
        r"hdf_device|hdi_servmgr|passthrough", re.I)),
    ("display", re.compile(
        r"display|DISP|composer|RSScreen|render_service|BootAnimation|"
        r"drm|plane|crtc", re.I)),
    ("input", re.compile(
        r"input|InputWindows|Multimodal|MMI|touch|QDtech|libinput|evdev", re.I)),
    ("security", re.compile(
        r"teecd|\bTEE\b|access_token|SELINUX|avc:|security|huks", re.I)),
    ("network", re.compile(
        r"softbus|DHDM|wifi|netmanager|hdc|Bluetooth|bt_", re.I)),
    ("audio", re.compile(
        r"audio|PulseAudio|AudioXml|effect_model", re.I)),
    ("noise", re.compile(
        r"MUSL-SIGCHAIN|signal: 4|le_epoll|HISYSEVENT_TRANSPORT|"
        r"LoopEvent|ffrt|SA_LOAD_DURATION", re.I)),
]
ANSI = re.compile(r"\x1b\[[0-9;]*m")
STAMP = re.compile(
    r"^(?:\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[A-Z]\s+\S+\s*)?"
    r"(?:\[\s*\d+\.\d+\]\s*)?")
NORMALIZE = [
    (re.compile(r"\b[0-9a-f]{8,}\b"), "<hex>"),
    (re.compile(r"\b\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\b"), "<time>"),
    (re.compile(r"\[\s*\d+\.\d+\]"), "<ktime>"),
    (re.compile(r"\bpid[= ]\d+\b", re.I), "pid=<n>"),
    (re.compile(r"\b\d+\b"), "<n>"),
]


def classify(line):
    for name, pattern in CATEGORIES:
        if pattern.search(line):
            return name
    return "other"


def normalize(line):
    line = STAMP.sub("", line)
    for pattern, replacement in NORMALIZE:
        line = pattern.sub(replacement, line)
    return line.strip()[:500]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="+", type=Path)
    parser.add_argument("--examples", type=int, default=3)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--category")
    args = parser.parse_args()

    counts = collections.Counter()
    unique = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)

    for path in args.log:
        text = path.read_bytes().decode("utf-8", "replace")
        for raw in text.splitlines():
            line = ANSI.sub("", raw).rstrip()
            if not line.strip():
                continue
            category = classify(line)
            counts[category] += 1
            unique[category][normalize(line)] += 1
            if len(examples[category]) < args.examples and line not in examples[category]:
                examples[category].append(line[:400])

    print(f"files: {len(args.log)}")
    print(f"lines: {sum(counts.values())}")
    print("\ncounts:")
    for category, count in counts.most_common():
        if args.category and category != args.category:
            continue
        print(f"  {category:10s} {count:8d}")
        for message, occurrences in unique[category].most_common(args.top):
            print(f"    {occurrences:6d}  {message}")
        for example in examples[category]:
            print(f"      e.g. {example}")


if __name__ == "__main__":
    main()
