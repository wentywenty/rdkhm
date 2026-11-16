#!/usr/bin/env python3
"""Check required dlsym entry points against the packaged default composer VDI."""
from pathlib import Path
import re
import subprocess
import sys


def check(library):
    workspace = Path(__file__).resolve().parents[1]
    source = (workspace / "sources/openharmony-full/drivers/peripheral/display/composer/"
              "hdi_service/src/display_composer_service.cpp").read_text()
    start = source.index("int32_t DisplayComposerService::LoadVdiAdapter()")
    end = source.index("void DisplayComposerService::LoadVdiFuncPart1()", start)
    required = set(re.findall(r"CHECK_NULLPOINTER_RETURN_VALUE\(vdiAdapter_->(\w+),", source[start:end]))
    if not required:
        raise RuntimeError("No mandatory composer VDI entry points found")
    output = subprocess.check_output(["readelf", "--dyn-syms", "--wide", str(library)], text=True)
    exported = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 8 and fields[3] == "FUNC" and fields[4] in ("GLOBAL", "WEAK"):
            if fields[5] == "DEFAULT" and fields[6] != "UND":
                exported.add(fields[7])
    missing = required - exported
    if missing:
        raise RuntimeError("Missing composer VDI exports: " + ", ".join(sorted(missing)))
    print(f"PASS: {len(required)} mandatory composer VDI C exports")


if __name__ == "__main__":
    check(Path(sys.argv[1]))
