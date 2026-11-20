#include <list>
#include <memory>
#include <new>
#include <vector>
#include "i_dp_sync_adapter.h"

namespace OHOS {
namespace DistributedDeviceProfile {
class RdkhmDpSyncAdapterStub : public IDPSyncAdapter {
public:
    int32_t Initialize() override { return -1; }
    int32_t Release() override { return 0; }
    int32_t DetectRemoteDPVersion(const std::string&) override { return -1; }
    int32_t SyncProfile(const std::list<std::string>&, const sptr<IRemoteObject>) override { return -1; }
    int32_t NotOHBaseDeviceOnline(const std::string&, const std::string&, bool) override { return -1; }
    int32_t SyncProfile(const std::string&, const std::string&,
        const sptr<IRemoteObject>, bool) override { return -1; }
    int32_t FixDiffProfiles(const std::vector<std::string>&) override { return -1; }
};
} // namespace DistributedDeviceProfile
} // namespace OHOS

extern "C" OHOS::DistributedDeviceProfile::IDPSyncAdapter *CreateDPSyncAdaptertObject()
{
    return new (std::nothrow) OHOS::DistributedDeviceProfile::RdkhmDpSyncAdapterStub();
}
