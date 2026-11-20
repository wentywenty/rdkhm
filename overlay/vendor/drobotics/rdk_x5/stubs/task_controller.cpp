#include <cstdint>
#include <string>
#include <unordered_map>

#include "concurrent_task_type.h"

namespace OHOS {
namespace ConcurrentTask {
using Payload = std::unordered_map<std::string, std::string>;

extern "C" void ReportData(uint32_t, int64_t, const Payload&) {}
extern "C" void ReportSceneInfo(uint32_t, const Payload&) {}

extern "C" void QueryInterval(int, IntervalReply& reply)
{
    reply.rtgId = -1;
    reply.tid = -1;
    reply.paramA = 0;
    reply.paramB = 0;
    reply.bundleName.clear();
}

extern "C" void QueryDeadline(int, DeadlineReply& reply, const Payload&)
{
    reply.setStatus = false;
}

extern "C" void SetAudioDeadline(int, int, int, IntervalReply& reply)
{
    reply.rtgId = -1;
    reply.tid = -1;
    reply.paramA = 0;
    reply.paramB = 0;
    reply.bundleName.clear();
}

extern "C" void RequestAuth(const Payload&) {}
extern "C" void Init() {}
extern "C" void Release() {}
} // namespace ConcurrentTask
} // namespace OHOS
