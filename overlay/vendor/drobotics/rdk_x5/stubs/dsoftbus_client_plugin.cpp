#include "g_enhance_sdk_func.h"

extern "C" void BusCenterExProxyDeInit(void) {}
extern "C" int32_t DiscRecoveryPolicy(void) { return -1; }
extern "C" int32_t CheckFileSchema(int32_t, FileSchemaListener *) { return -1; }
extern "C" int32_t SetSchemaCallback(FileSchema, const char *[], uint32_t) { return -1; }
extern "C" int32_t SetExtSocketOpt(int32_t, OptLevel, OptType, void *, uint32_t) { return -1; }
extern "C" int32_t GetExtSocketOpt(int32_t, OptLevel, OptType, void *, int32_t *) { return -1; }
extern "C" int32_t TransFileSchemaInit(void) { return -1; }
extern "C" void TransFileSchemaDeinit(void) {}
extern "C" int32_t VtpSetSocketMultiLayer(int, OnFrameEvt *, const void *) { return -1; }
extern "C" bool IsVtpFrameSentEvt(const FtEventCbkInfo *) { return false; }
extern "C" int HandleVtpFrameEvt(int, OnFrameEvt, const FtEventCbkInfo *) { return -1; }
extern "C" int32_t TransOnPagingConnect(const int32_t, const ChannelInfo *) { return -1; }
