#!/usr/bin/env python3
"""Compile the real encoder selector against a small DRM resource fixture."""
from pathlib import Path
import subprocess
import tempfile

workspace = Path(__file__).resolve().parents[1]
vdi = workspace / "sources/openharmony-full/drivers/peripheral/display/composer/vdi_base"
with tempfile.TemporaryDirectory(prefix="rdkhm-encoder-") as directory:
    temp = Path(directory)
    (temp / "xf86drm.h").write_text("#pragma once\n")
    (temp / "xf86drmMode.h").write_text("""
#pragma once
#include <cstdint>
struct drmModeEncoder { uint32_t encoder_id, crtc_id, possible_crtcs; };
""")
    (temp / "drm_crtc.h").write_text("""
#pragma once
#include <cstdint>
#include <map>
#include <memory>
#define DISPLAY_LOGD(...) ((void)0)
#define DISPLAY_LOGW(...) ((void)0)
#define DISPLAY_LOGE(...) ((void)0)
#define DISPLAY_CHK_RETURN(condition, result, log) do { if (condition) { return result; } } while (0)
namespace OHOS::HDI::DISPLAY {
constexpr int DISPLAY_SUCCESS = 0, DISPLAY_FAILURE = -1;
template<class T> using IdMapPtr = std::map<uint32_t, std::shared_ptr<T>>;
class DrmCrtc {
public:
    DrmCrtc(uint32_t id, uint32_t pipe, bool idle) : id_(id), pipe_(pipe), idle_(idle) {}
    uint32_t GetId() const { return id_; }
    uint32_t GetPipe() const { return pipe_; }
    bool CanBind() const { return idle_; }
private:
    uint32_t id_, pipe_;
    bool idle_;
};
}
""")
    (temp / "test.cpp").write_text("""
#include "drm_encoder.h"
#include <cassert>
using namespace OHOS::HDI::DISPLAY;
int main() {
    auto check = [](uint32_t mask, uint32_t current, bool idle0, bool idle1, int expected) {
        IdMapPtr<DrmCrtc> crtcs;
        crtcs.emplace(71, std::make_shared<DrmCrtc>(71, 0, idle0));
        crtcs.emplace(74, std::make_shared<DrmCrtc>(74, 1, idle1));
        DrmEncoder encoder({80, current, mask});
        uint32_t selected = 999;
        int ret = encoder.PickIdleCrtcId(crtcs, selected);
        if (expected < 0) {
            assert(ret == DISPLAY_FAILURE);
            assert(selected == 999);
        } else {
            assert(ret == DISPLAY_SUCCESS);
            assert(selected == static_cast<uint32_t>(expected));
        }
    };
    check(3, 0, true, true, 71); // Cold boot: both pipes are allowed, no active CRTC.
    check(1, 0, true, true, 71);
    check(2, 0, true, true, 74);
    check(3, 0, false, true, 74);
    check(3, 74, true, true, 74);
    check(0, 0, true, true, -1);
    check(4, 0, true, true, -1);
    check(3, 0, false, false, -1);
}
""")
    subprocess.run([
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-I" + str(temp), "-I" + str(vdi / "include"),
        str(vdi / "src/drm_encoder.cpp"), str(temp / "test.cpp"),
        "-o", str(temp / "test"),
    ], check=True)
    subprocess.run([str(temp / "test")], check=True)
print("PASS: 8 CRTC selection scenarios using the production encoder source")
