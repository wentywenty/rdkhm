#include "hdi_drm_composition.h"
using namespace OHOS::HDI::DISPLAY;
int main()
{
    auto crtc = std::make_shared<DrmCrtc>();
    HdiDrmComposition composition(std::make_shared<DrmConnector>(), crtc, std::make_shared<DrmDevice>());
    assert(composition.Init() == 0);
    HdiDrmLayer client;
    std::vector<HdiLayer*> layers;
    assert(composition.SetLayers(layers, client) == 0);
    assert(composition.Apply(true) == 0);
    assert(commits == 1 && lastRequest.mode && lastRequest.framebuffer);
    assert(!lastRequest.hasZpos);
    assert(!crtc->needsMode && requests == 0);
    assert(lastFlags == DRM_MODE_ATOMIC_ALLOW_MODESET);
    assert(composition.Apply(false) == 0);
    assert(!lastRequest.mode && lastRequest.framebuffer);
    assert(lastFlags & DRM_MODE_ATOMIC_NONBLOCK);
    crtc->needsMode = true;
    failCommit = true;
    assert(composition.Apply(true) != 0 && crtc->needsMode && requests == 0);
    failCommit = false;
    assert(composition.Apply(true) == 0 && !crtc->needsMode && requests == 0);
    crtc->needsMode = true;
    int previousCommits = commits;
    invalidMode = true;
    assert(composition.Apply(true) != 0 && crtc->needsMode && commits == previousCommits && requests == 0);
    invalidMode = false;
    failAlloc = true;
    assert(composition.Apply(true) != 0 && crtc->needsMode && commits == previousCommits && requests == 0);
}
