#!/usr/bin/env python3
"""Exercise the production classifier with evdev capability fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace / "scripts"))
from workspace import environment

source = (Path(environment(workspace)["RDKHM_OH_TREE"]) /
          "drivers/peripheral/input/udriver/src/input_device_manager.cpp").read_text()
classifier = source[source.index("uint32_t GetInputDeviceTypeInfo("):source.index("int32_t InputDeviceManager::GetCurDevIndex()")]
fixture = r'''
#include <cstdint>
#include <string>
#include <linux/input.h>
#include <cassert>
using std::string;
enum { INDEV_TYPE_UNKNOWN, INDEV_TYPE_TOUCH, INDEV_TYPE_KEYBOARD,
       INDEV_TYPE_MOUSE, INDEV_TYPE_KEY, INDEV_TYPE_TOUCHPAD };
struct InputDeviceInfo {
    struct { uint64_t absCode[(ABS_CNT + 63) / 64]{};
             uint64_t devProp[(INPUT_PROP_CNT + 63) / 64]{}; } abilitySet;
};
'''
cases = r'''
int main() {
    InputDeviceInfo info{};
    assert(GetInputDeviceTypeInfo("QDtech MPI5001", info) == INDEV_TYPE_UNKNOWN);
    info.abilitySet.absCode[0] = (uint64_t{1} << ABS_MT_POSITION_X) |
        (uint64_t{1} << ABS_MT_POSITION_Y);
    assert(GetInputDeviceTypeInfo("QDtech MPI5001", info) == INDEV_TYPE_UNKNOWN);
    info.abilitySet.devProp[0] = uint64_t{1} << INPUT_PROP_DIRECT;
    assert(GetInputDeviceTypeInfo("QDtech MPI5001", info) == INDEV_TYPE_TOUCH);
    info.abilitySet.absCode[0] = uint64_t{1} << ABS_MT_POSITION_X;
    assert(GetInputDeviceTypeInfo("QDtech MPI5001", info) == INDEV_TYPE_UNKNOWN);
    info.abilitySet.absCode[0] = (uint64_t{1} << ABS_X) | (uint64_t{1} << ABS_Y);
    assert(GetInputDeviceTypeInfo("generic USB display", info) == INDEV_TYPE_TOUCH);
    info = {};
    assert(GetInputDeviceTypeInfo("USB Keyboard", info) == INDEV_TYPE_KEYBOARD);
    assert(GetInputDeviceTypeInfo("USB Mouse", info) == INDEV_TYPE_MOUSE);
    assert(GetInputDeviceTypeInfo("Touchpad", info) == INDEV_TYPE_TOUCHPAD);
    assert(GetInputDeviceTypeInfo("input_mt_wrapper", info) == INDEV_TYPE_TOUCH);
}
'''
with tempfile.TemporaryDirectory(prefix="rdkhm-touch-") as directory:
    test = Path(directory) / "test.cpp"
    test.write_text(fixture + classifier + cases)
    binary = Path(directory) / "test"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(test), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: 9 production touch classifier cases; no physical events simulated")
