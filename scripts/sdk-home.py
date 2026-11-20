#!/usr/bin/env python3
"""Print the hvigor-compatible SDK root, creating the symlink layout if needed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from hvigor_sdk import ensure_sdk_home
from workspace import environment

print(ensure_sdk_home(ROOT, environment()["RDKHM_OH_SDK"]))
