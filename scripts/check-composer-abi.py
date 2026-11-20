#!/usr/bin/env python3
"""Check required dlsym entry points against the packaged default composer VDI."""
from pathlib import Path
import re
import subprocess
import sys

from workspace import environment


def check(library):
    oh = Path(environment()["RDKHM_OH_TREE"])
    source = (oh / "drivers/peripheral/display/composer/"
              "hdi_service/src/display_composer_service.cpp").read_text()
    start = source.index("int32_t DisplayComposerService::LoadVdiAdapter()")
    end = source.index("void DisplayComposerService::LoadVdiFuncPart1()", start)
    required = set(re.findall(r"CHECK_NULLPOINTER_RETURN_VALUE\(vdiAdapter_->(\w+),", source[start:end]))
    # Refresh registration is a v1.1 entry point but is mandatory for the
    # current service path; the rest of v1.1/v1.2 remains optional.
    required.update(("RegRefreshCallback", "GetDisplaySupportedColorGamuts"))
    if len(required) <= 1:
        raise RuntimeError("No mandatory composer VDI entry points found")
    all_entries = set(re.findall(r'dlsym\(libHandle_,\s*"(\w+)"\)', source))
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
    optional_missing = sorted((all_entries - required) - exported)
    print(f"PASS: {len(required)} mandatory composer VDI C exports (including refresh and color-gamut)")
    if optional_missing:
        print(f"WARN: {len(optional_missing)} later optional composer entry points are not exported: "
              + ", ".join(optional_missing))


if __name__ == "__main__":
    check(Path(sys.argv[1]))
