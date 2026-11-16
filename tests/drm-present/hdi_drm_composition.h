#pragma once
#include <cassert>
#include <cstdint>
#include <memory>
#include <vector>
#define DISPLAY_LOGD(...) ((void)0)
#define DISPLAY_LOGE(...) ((void)0)
#define DISPLAY_CHK_RETURN(c, r, log) do { if (c) return r; } while (0)
constexpr int DISPLAY_SUCCESS = 0, DISPLAY_FAILURE = -1, DISPLAY_NULL_PTR = -2;
constexpr int DRM_INVALID_ID = 0, DRM_PLANE_TYPE_PRIMARY = 1, DRM_PLANE_TYPE_OVERLAY = 2;
constexpr uint32_t DRM_MODE_ATOMIC_ALLOW_MODESET = 1, DRM_MODE_ATOMIC_NONBLOCK = 2;
struct Request { bool mode = false, framebuffer = false, invalidZpos = false, hasZpos = false; };
using drmModeAtomicReqPtr = Request*;
inline bool failCommit = false, invalidMode = false, failAlloc = false;
inline int commits = 0, requests = 0;
inline uint32_t lastFlags = 0;
inline Request lastRequest;
inline Request* drmModeAtomicAlloc() { if (failAlloc) return nullptr; ++requests; return new Request; }
inline void drmModeAtomicFree(Request* p) { --requests; delete p; }
inline int drmModeAtomicAddProperty(Request* p, uint32_t, uint32_t prop, uint64_t value) {
    p->mode |= prop == 100;
    p->framebuffer |= prop == 101;
    p->hasZpos |= prop == 9;
    p->invalidZpos |= prop == 9 && value > 2;
    return 0;
}
inline int drmModeAtomicCommit(int, Request* p, uint32_t flags, void*) {
    ++commits; lastFlags = flags; lastRequest = *p;
    // Reject split mode-only requests, like a backend requiring a primary plane.
    return failCommit || p->invalidZpos || (p->mode && !p->framebuffer) ? -22 : 0;
}
namespace OHOS::HDI::DISPLAY {
class AtomicReqPtr {
public:
    explicit AtomicReqPtr(Request* p) : p_(p) {}
    ~AtomicReqPtr() { drmModeAtomicFree(p_); }
    Request* Get() const { return p_; }
private: Request* p_;
};
class HdiLayerBuffer {
public: int GetWight() { return 1920; } int GetHeight() { return 1080; }
};
class HdiLayer {
public:
    HdiLayerBuffer* GetCurrentBuffer() { return &buffer_; }
    void SetReleaseFence(int fence) { releaseFence = fence; }
    int releaseFence = -1;
private: HdiLayerBuffer buffer_;
};
class DrmGemBuffer {
public: bool IsValid() { return true; } uint32_t GetFbId() { return 200; }
};
class HdiDrmLayer : public HdiLayer {
public:
    int GetAcquireFenceFd() { return -1; }
    uint32_t GetZorder() { return UINT32_MAX; }
    DrmGemBuffer* GetGemBuffer() { return &gem_; }
private: DrmGemBuffer gem_;
};
class DrmPlane {
public:
    uint32_t GetId() { return 33; }
    int GetPropFenceInId() { return 0; }
    int GetPropCrtc_xId() { return 1; } int GetPropCrtc_yId() { return 2; }
    int GetPropCrtc_wId() { return 3; } int GetPropCrtc_hId() { return 4; }
    int GetPropSrc_xId() { return 5; } int GetPropSrc_yId() { return 6; }
    int GetPropSrc_wId() { return 7; } int GetPropSrc_hId() { return 8; }
    int GetPropZposId() { return 9; } int GetPropFbId() { return 101; }
    int GetPropCrtcId() { return 10; }
    int GetWinType() { return 0; } int GetPipe() { return 0; }
    void UnBindPipe() {}
};
class DrmCrtc {
public:
    uint32_t GetId() { return 71; } int GetPipe() { return 0; }
    bool NeedModeSet() { return needsMode; } void ClearModeSet() { needsMode = false; }
    int GetActiveModeId() { return 0; } int GetActivePropId() { return 11; }
    int GetModePropId() { return 100; } int GetOutFencePropId() { return 12; }
    int GetPlaneMask() { return 0; }
    bool needsMode = true;
};
class DrmModeBlock {
public: int GetBlockId() { return 300; }
};
class DrmConnector {
public:
    uint32_t GetId() { return 80; } int GetPropCrtcId() { return 13; }
    std::unique_ptr<DrmModeBlock> GetModeBlockFromId(int) {
        return invalidMode ? nullptr : std::make_unique<DrmModeBlock>();
    }
};
class DrmDevice {
public:
    int GetDrmFd() { return 3; }
    std::vector<std::shared_ptr<DrmPlane>> GetDrmPlane(int, int type) {
        if (type == DRM_PLANE_TYPE_PRIMARY) return {std::make_shared<DrmPlane>()};
        return {};
    }
};
class HdiDrmComposition {
public:
    HdiDrmComposition(const std::shared_ptr<DrmConnector>&, const std::shared_ptr<DrmCrtc>&,
                     const std::shared_ptr<DrmDevice>&);
    int32_t Init();
    int32_t SetLayers(std::vector<HdiLayer*>&, HdiLayer&);
    int32_t Apply(bool);
    int32_t UpdateMode(Request*, std::unique_ptr<DrmModeBlock>&);
private:
    int32_t SetCrtcProperty(DrmPlane&, Request*, int32_t, int32_t);
    int32_t SetSrcProperty(DrmPlane&, Request*, int32_t, int32_t);
    int32_t ApplyPlane(HdiDrmLayer&, HdiLayer&, DrmPlane&, Request*);
    int32_t RemoveUnusePlane(Request*);
    int32_t FindPlaneAndApply(Request*);
    std::shared_ptr<DrmDevice> mDrmDevice;
    std::shared_ptr<DrmConnector> mConnector;
    std::shared_ptr<DrmCrtc> mCrtc;
    std::vector<std::shared_ptr<DrmPlane>> mPrimPlanes, mOverlayPlanes, mPlanes;
    std::vector<HdiLayer*> mCompLayers;
};
}
