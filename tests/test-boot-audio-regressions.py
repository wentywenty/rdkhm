#!/usr/bin/env python3
"""Run production initialization functions with controlled service dependencies."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
from workspace import environment

tree = Path(environment(root)['RDKHM_OH_TREE'])
audio = (tree / 'foundation/multimedia/audio_framework/frameworks/native/pulseaudio/modules/hdi/hdi_adapter_intf/sink/sink_adapter.cpp').read_text()
audio = audio[audio.index('int32_t SinkAdapterInit('):audio.index('void SinkAdapterDeInit(')]
account = (tree / 'base/account/os_account/services/accountmgr/src/osaccount/os_account_control_file_manager.cpp').read_text()
account = account[account.index('ErrCode OsAccountControlFileManager::GetAccountIndexInfo('):account.index('ErrCode OsAccountControlFileManager::GetBaseOAConstraintsFromFile(')]
fixture = r'''
#include <cassert>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>
#include "cJSON.h"
#define AUDIO_INFO_LOG(...)
#define CHECK_AND_RETURN_RET_LOG(condition, error, ...) if (!(condition)) return error
constexpr int ERR_INVALID_HANDLE=-1, ERR_INVALID_PARAM=-2, SUCCESS=0, HDI_INVALID_ID=-1;
using AudioSampleFormat=int;
struct SinkAdapter { int renderId=1; };
struct SinkAdapterAttr {
    const char *adapterName="primary", *deviceNetworkId="local", *aux=nullptr;
    int openMicSpeaker=0, format=0, sampleRate=48000, channel=2, deviceType=0, channelLayout=0;
    float volume=1;
};
struct IAudioSinkAttr {
    std::string adapterName, deviceNetworkId, aux;
    int openMicSpeaker, format, sampleRate, channel, deviceType, channelLayout;
    float volume;
};
struct IAudioRenderSink {
    IAudioSinkAttr last{};
    bool inited=false;
    bool IsInited() { return inited; }
    int Init(const IAudioSinkAttr &attr) { last=attr; return 0; }
};
auto renderSink=std::make_shared<IAudioRenderSink>();
std::shared_ptr<IAudioRenderSink> GetRenderSink(int) { return renderSink; }
using ErrCode=int;
constexpr int ERR_OK=0;
enum class OsAccountType { ADMIN, PRIVATE };
struct OsAccountInfo {
    int id; OsAccountType type; std::string name, shortName;
    int GetLocalId() const { return id; }
    OsAccountType GetType() const { return type; }
    std::string GetLocalName() const { return name; }
    std::string GetShortName() const { return shortName; }
};
namespace Constants { const char *LOCAL_NAME="localName", *SHORT_NAME="shortName"; }
using Json=std::unique_ptr<cJSON, decltype(&cJSON_Delete)>;
Json CreateJson() { return Json(cJSON_CreateObject(), cJSON_Delete); }
Json CreateJsonNull() { return Json(cJSON_CreateNull(), cJSON_Delete); }
void AddStringToJson(Json &j, const char *k, const std::string &v) { cJSON_AddStringToObject(j.get(), k, v.c_str()); }
void AddObjToJson(Json &j, const std::string &k, Json &v) { cJSON_AddItemToObject(j.get(), k.c_str(), v.release()); }
std::string PackJsonToString(const Json &j) {
    char *s=cJSON_PrintUnformatted(j.get()); std::string out(s); cJSON_free(s); return out;
}
struct OsAccountControlFileManager {
    std::vector<OsAccountInfo> accounts;
    int error=0;
    int GetOsAccountList(std::vector<OsAccountInfo> &out) { out=accounts; return error; }
    int GetAccountIndexInfo(std::string &out);
};
'''
cases = r'''
int main() {
    SinkAdapter adapter;
    SinkAdapterAttr attr;
    assert(SinkAdapterInit(&adapter, &attr)==0);
    assert(renderSink->last.aux.empty());
    assert(renderSink->last.sampleRate==48000);
    attr.aux="split-mode";
    assert(SinkAdapterInit(&adapter, &attr)==0);
    assert(renderSink->last.aux=="split-mode");
    assert(SinkAdapterInit(nullptr, &attr)==ERR_INVALID_HANDLE);
    assert(SinkAdapterInit(&adapter, nullptr)==ERR_INVALID_PARAM);
    adapter.renderId=HDI_INVALID_ID;
    assert(SinkAdapterInit(&adapter, &attr)==ERR_INVALID_HANDLE);
    OsAccountControlFileManager manager;
    std::string index;
    assert(manager.GetAccountIndexInfo(index)==0);
    assert(index=="{}");
    manager.accounts={{100, OsAccountType::ADMIN, "user", ""}, {101, OsAccountType::PRIVATE, "private", ""}};
    assert(manager.GetAccountIndexInfo(index)==0);
    Json parsed(cJSON_Parse(index.c_str()), cJSON_Delete);
    assert(cJSON_IsObject(parsed.get()));
    assert(cJSON_GetObjectItemCaseSensitive(parsed.get(), "100")!=nullptr);
    assert(cJSON_GetObjectItemCaseSensitive(parsed.get(), "101")==nullptr);
    manager.error=-42;
    assert(manager.GetAccountIndexInfo(index)==-42);
}
'''
with tempfile.TemporaryDirectory(prefix='rdkhm-boot-regression-') as directory:
    work = Path(directory)
    source = work / 'test.cpp'
    source.write_text(fixture + audio + account + cases)
    cjson = tree / 'third_party/cJSON'
    subprocess.run(['gcc', '-c', str(cjson / 'cJSON.c'), '-I', str(cjson), '-o', str(work / 'cjson.o')], check=True)
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', str(source), str(work / 'cjson.o'), '-I', str(cjson), '-o', str(work / 'test')], check=True)
    subprocess.run([str(work / 'test')], check=True)
print('PASS: production sink optional aux, invalid handles, empty/populated/private account index, storage error propagation')
