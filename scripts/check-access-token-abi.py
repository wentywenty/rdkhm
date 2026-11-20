#!/usr/bin/env python3
"""Keep the X5 kernel access-token device ABI aligned with OH userspace."""
from pathlib import Path
import re
import sys

from workspace import ROOT, environment

OH = Path(environment()["RDKHM_OH_TREE"])
KERNEL = ROOT / "patches/kernel/0001-openharmony-core.patch"
USER = OH / "base/security/access_token/interfaces/innerkits/token_setproc/include/setproc_common.h"
IPC = OH / "foundation/communication/ipc/ipc/native/c/adapter/access_token/src/access_token_adapter.c"

def value(path, text):
    match = re.search(r"ACCESS_TOKEN_ID_IOCTL_BASE\s+'([^'])'", text)
    if not match:
        raise RuntimeError(f"missing ioctl base in {path}")
    return match.group(1)

def commands(text):
    names = ("GET_TOKEN_ID", "SET_TOKEN_ID", "GET_FTOKEN_ID", "SET_FTOKEN_ID",
             "ADD_PERMISSIONS", "REMOVE_PERMISSIONS", "GET_PERMISSION", "SET_PERMISSION")
    return [name for name in names if re.search(r"\b" + name + r"\b", text)]

kernel = KERNEL.read_text()
user = USER.read_text()
ipc = IPC.read_text()
bases = {str(KERNEL): value(KERNEL, kernel), str(USER): value(USER, user), str(IPC): value(IPC, ipc)}
if len(set(bases.values())) != 1:
    raise RuntimeError(f"ioctl magic mismatch: {bases}")
expected = ["GET_TOKEN_ID", "SET_TOKEN_ID", "GET_FTOKEN_ID", "SET_FTOKEN_ID",
            "ADD_PERMISSIONS", "REMOVE_PERMISSIONS", "GET_PERMISSION", "SET_PERMISSION"]
if commands(kernel)[:len(expected)] != expected or commands(user)[:len(expected)] != expected:
    raise RuntimeError("access-token ioctl command ordering mismatch")
print(f"PASS: access-token ioctl magic={next(iter(bases.values()))} command ordering aligned")
