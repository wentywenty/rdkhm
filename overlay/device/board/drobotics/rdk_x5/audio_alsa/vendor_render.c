#include "alsa_snd_render.h"
#include "x5_audio.h"

static int32_t GetRange(struct AlsaRender *render, long *minimum, long *maximum)
{
    if (render == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    return X5Control(&render->soundCard, "HPL Playback Volume", X5_RANGE, minimum, maximum);
}

static int32_t GetVolume(struct AlsaRender *render, long *volume)
{
    if (render == NULL || volume == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    long left, right;
    if (X5Control(&render->soundCard, "HPL Playback Volume", X5_READ, &left, NULL) != HDF_SUCCESS ||
        X5Control(&render->soundCard, "HPR Playback Volume", X5_READ, &right, NULL) != HDF_SUCCESS) {
        return HDF_FAILURE;
    }
    *volume = (left + right) / 2;
    return HDF_SUCCESS;
}

static int32_t SetVolume(struct AlsaRender *render, long volume)
{
    if (render == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    long previous;
    if (X5Control(&render->soundCard, "HPL Playback Volume", X5_READ, &previous, NULL) != HDF_SUCCESS) {
        return HDF_FAILURE;
    }
    int32_t result = X5Control(&render->soundCard, "HPL Playback Volume", X5_WRITE, &volume, NULL);
    if (result != HDF_SUCCESS) {
        return result;
    }
    result = X5Control(&render->soundCard, "HPR Playback Volume", X5_WRITE, &volume, NULL);
    if (result != HDF_SUCCESS) {
        (void)X5Control(&render->soundCard, "HPL Playback Volume", X5_WRITE, &previous, NULL);
    }
    return result;
}

static int32_t Init(struct AlsaRender *render)
{
    long minimum, maximum;
    return GetRange(render, &minimum, &maximum);
}

static int32_t SelectScene(struct AlsaRender *render, enum AudioPortPin pins, const struct PathDeviceInfo *device)
{
    (void)device;
    if (render == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    if (pins != PIN_OUT_SPEAKER && pins != PIN_OUT_HEADSET && pins != PIN_OUT_HEADPHONE) {
        return HDF_ERR_NOT_SUPPORT;
    }
    render->descPins = pins;
    return HDF_SUCCESS;
}

static int32_t Start(struct AlsaRender *render)
{
    return render == NULL ? HDF_ERR_INVALID_PARAM : X5Prepare(&render->soundCard);
}

static int32_t Stop(struct AlsaRender *render)
{
    return render == NULL ? HDF_ERR_INVALID_PARAM : X5Stop(&render->soundCard);
}

static int32_t Pause(struct AlsaRender *render, bool pause)
{
    return render == NULL ? HDF_ERR_INVALID_PARAM : X5Pause(&render->soundCard, pause);
}

static bool GetMute(struct AlsaRender *render)
{
    (void)render;
    return false;
}

static int32_t SetMute(struct AlsaRender *render, bool mute)
{
    (void)render;
    (void)mute;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t GetGainRange(struct AlsaRender *render, float *minimum, float *maximum)
{
    (void)render;
    (void)minimum;
    (void)maximum;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t GetGain(struct AlsaRender *render, float *gain)
{
    (void)render;
    (void)gain;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t SetGain(struct AlsaRender *render, float gain)
{
    (void)render;
    (void)gain;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t GetChannelMode(struct AlsaRender *render, enum AudioChannelMode *mode)
{
    if (render == NULL || mode == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    *mode = AUDIO_CHANNEL_NORMAL;
    return HDF_SUCCESS;
}

static int32_t SetChannelMode(struct AlsaRender *render, enum AudioChannelMode mode)
{
    if (render == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    return mode == AUDIO_CHANNEL_NORMAL ? HDF_SUCCESS : HDF_ERR_NOT_SUPPORT;
}

int32_t RenderOverrideFunc(struct AlsaRender *render)
{
    if (render == NULL || render->soundCard.cardType != SND_CARD_PRIMARY) {
        return HDF_ERR_NOT_SUPPORT;
    }
    render->Init = Init;
    render->SelectScene = SelectScene;
    render->Start = Start;
    render->Stop = Stop;
    render->SetPauseState = Pause;
    render->GetVolThreshold = GetRange;
    render->GetVolume = GetVolume;
    render->SetVolume = SetVolume;
    render->GetMute = GetMute;
    render->SetMute = SetMute;
    render->GetGainThreshold = GetGainRange;
    render->GetGain = GetGain;
    render->SetGain = SetGain;
    render->GetChannelMode = GetChannelMode;
    render->SetChannelMode = SetChannelMode;
    return HDF_SUCCESS;
}
