#include "i_dm_service_impl_ext_resident.h"

namespace OHOS {
namespace DistributedHardware {
class RdkhmDmResidentStub : public IDMServiceImplExtResident {
public:
    int32_t Initialize(const std::shared_ptr<IDeviceManagerServiceListener> &) override { return -1; }
    int32_t Release() override { return 0; }
    bool IsDMServiceAdapterLoad() override { return false; }
    bool IsDMServiceAdapterSoLoaded() override { return false; }
    int32_t BindTargetExt(const std::string &, const PeerTargetId &,
        const std::map<std::string, std::string> &) override { return -1; }
    int32_t UnbindTargetExt(const std::string &, const PeerTargetId &,
        const std::map<std::string, std::string> &) override { return -1; }
    int32_t HandleDeviceStatusChange(DmDeviceState, const DmDeviceInfo &) override { return -1; }
    int32_t ReplyUiAction(const std::string &, int32_t, const std::string &) override { return -1; }
    int32_t AccountIdLogout(int32_t, const std::string &, const std::vector<std::string> &) override { return -1; }
    void HandleDeviceNotTrust(const std::string &) override {}
    int32_t SetDnPolicy(int32_t, int32_t) override { return -1; }
    int32_t AccountUserSwitched(int32_t, const std::string &) override { return -1; }
    int32_t GetDeviceProfileInfoList(const std::string &, const DmDeviceProfileInfoFilterOptions &) override { return -1; }
    int32_t GetDeviceIconInfo(const std::string &, const DmDeviceIconInfoFilterOptions &) override { return -1; }
    int32_t PutDeviceProfileInfoList(const std::string &,
        const std::vector<OHOS::DistributedHardware::DmDeviceProfileInfo> &) override { return -1; }
    std::vector<std::string> GetDeviceNamePrefixs() override { return {}; }
    void HandleNetworkConnected(int32_t) override {}
    int32_t SetLocalDeviceName(const std::string &, const std::string &) override { return -1; }
    int32_t SetRemoteDeviceName(const std::string &, const std::string &, const std::string &) override { return -1; }
    int32_t GetDeviceProfileInfosFromLocalCache(const NetworkIdQueryFilter &,
        std::vector<DmDeviceProfileInfo> &) override { return -1; }
    int32_t RestoreLocalDeviceName() override { return -1; }
    void ClearCacheWhenLogout(int32_t, const std::string &) override {}
    void HandleScreenLockEvent(bool) override {}
    int32_t OpenAuthSessionWithPara(const std::string &, int32_t, bool) override { return -1; }
    void HandleUserSwitchEvent(int32_t, int32_t) override {}
};
} // namespace DistributedHardware
} // namespace OHOS

extern "C" OHOS::DistributedHardware::IDMServiceImplExtResident *CreateDMServiceExtResidentObject()
{
    return new (std::nothrow) OHOS::DistributedHardware::RdkhmDmResidentStub();
}
