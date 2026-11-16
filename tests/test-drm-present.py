#!/usr/bin/env python3
"""Exercise production atomic composition with mocked DRM objects/ioctls."""
from pathlib import Path
import subprocess
import tempfile

workspace = Path(__file__).resolve().parents[1]
fixture = workspace / "tests/drm-present"
source = workspace / "sources/openharmony-full/drivers/peripheral/display/composer/vdi_base/src"
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
