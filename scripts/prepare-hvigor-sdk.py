#!/usr/bin/env python3
"""Prepare the hvigor 6.x SDK layout from the pinned OpenHarmony SDK."""
from pathlib import Path

from hvigor_sdk import ensure_sdk_home
from workspace import ROOT, environment


def main():
    env = environment()
    home = ensure_sdk_home(ROOT, Path(env["RDKHM_OH_SDK"]))
    expected = Path(env["RDKHM_HVIGOR_SDK"])
    if home != expected:
        print(f"hvigor SDK prepared at {home} (RDKHM_HVIGOR_SDK={expected})")
    else:
        print(f"hvigor SDK prepared at {home}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
