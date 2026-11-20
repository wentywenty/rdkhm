#!/usr/bin/env python3
"""Exercise production atomic composition with mocked DRM objects/ioctls."""
from pathlib import Path
import subprocess
import sys
import tempfile

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace / "scripts"))
from workspace import environment

fixture = workspace / "tests/drm-present"
source = (Path(environment(workspace)["RDKHM_OH_TREE"]) /
          "drivers/peripheral/display/composer/vdi_base/src")
with tempfile.TemporaryDirectory(prefix="rdkhm-present-") as directory:
    executable = Path(directory) / "test"
    subprocess.run([
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        "-Wno-unused-but-set-variable",
        "-DRDK_X5_SOFTWARE_COMPOSITION", "-I" + str(fixture),
        str(source / "hdi_drm_composition.cpp"), str(fixture / "test.cpp"),
        "-o", str(executable),
    ], check=True)
    subprocess.run([str(executable)], check=True)
print("PASS: first frame, flip, failed commit, retry, invalid mode and allocation failure")
