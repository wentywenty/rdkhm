#include "sec_comp_enhance_adapter.h"

namespace OHOS {
namespace Security {
namespace SecurityComponent {
class RdkhmSecCompClientEnhanceStub : public SecCompClientEnhanceInterface {
public:
    bool EnhanceDataPreprocess(const uintptr_t, std::string&) override { return false; }
    bool EnhanceDataPreprocess(const uintptr_t, int32_t, std::string&) override { return false; }
    bool EnhanceClientSerialize(const uintptr_t, MessageParcel&, SecCompRawdata&) override { return false; }
    bool EnhanceClientDeserialize(const uintptr_t, SecCompRawdata&, MessageParcel&) override { return false; }
    void RegisterScIdEnhance(const uintptr_t, int32_t) override {}
    void UnregisterScIdEnhance(const uintptr_t, int32_t) override {}
};
} // namespace SecurityComponent
} // namespace Security
} // namespace OHOS

extern "C" OHOS::Security::SecurityComponent::SecCompClientEnhanceInterface *GetClientInstance()
{
    return nullptr;
}
