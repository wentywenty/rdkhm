#include "alsa_snd_capture.h"
#include "x5_audio.h"

static int32_t GetRange(struct AlsaCapture *capture, long *minimum, long *maximum)
{
    return capture == NULL ? HDF_ERR_INVALID_PARAM :
        X5Control(&capture->soundCard, "ADC Capture Volume", X5_RANGE, minimum, maximum);
}

static int32_t GetVolume(struct AlsaCapture *capture, long *volume)
{
    return capture == NULL ? HDF_ERR_INVALID_PARAM :
        X5Control(&capture->soundCard, "ADC Capture Volume", X5_READ, volume, NULL);
}

static int32_t SetVolume(struct AlsaCapture *capture, long volume)
{
    return capture == NULL ? HDF_ERR_INVALID_PARAM :
        X5Control(&capture->soundCard, "ADC Capture Volume", X5_WRITE, &volume, NULL);
}

static int32_t Init(struct AlsaCapture *capture)
{
    long minimum, maximum;
    return GetRange(capture, &minimum, &maximum);
}

static int32_t SelectScene(struct AlsaCapture *capture, enum AudioPortPin pins, const struct PathDeviceInfo *device)
{
    (void)device;
    if (capture == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    if (pins != PIN_IN_MIC && pins != PIN_IN_HS_MIC) {
        return HDF_ERR_NOT_SUPPORT;
    }
    capture->descPins = pins;
    return HDF_SUCCESS;
}

static int32_t Start(struct AlsaCapture *capture)
{
    if (capture == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    int32_t result = X5Prepare(&capture->soundCard);
    if (result != HDF_SUCCESS) {
        return result;
    }
    if (snd_pcm_state(capture->soundCard.pcmHandle) == SND_PCM_STATE_RUNNING) {
        return HDF_SUCCESS;
    }
    return snd_pcm_start(capture->soundCard.pcmHandle) < 0 ? HDF_FAILURE : HDF_SUCCESS;
}

static int32_t Stop(struct AlsaCapture *capture)
{
    return capture == NULL ? HDF_ERR_INVALID_PARAM : X5Stop(&capture->soundCard);
}

static int32_t Pause(struct AlsaCapture *capture, bool pause)
{
    return capture == NULL ? HDF_ERR_INVALID_PARAM : X5Pause(&capture->soundCard, pause);
}

static bool GetMute(struct AlsaCapture *capture)
{
    (void)capture;
    return false;
}

static int32_t SetMute(struct AlsaCapture *capture, bool mute)
{
    (void)capture;
    (void)mute;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t GetGainRange(struct AlsaCapture *capture, float *minimum, float *maximum)
{
    (void)capture;
    (void)minimum;
    (void)maximum;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t GetGain(struct AlsaCapture *capture, float *gain)
{
    (void)capture;
    (void)gain;
    return HDF_ERR_NOT_SUPPORT;
}

static int32_t SetGain(struct AlsaCapture *capture, float gain)
{
    (void)capture;
    (void)gain;
    return HDF_ERR_NOT_SUPPORT;
}

int32_t CaptureOverrideFunc(struct AlsaCapture *capture)
{
    if (capture == NULL || capture->soundCard.cardType != SND_CARD_PRIMARY) {
        return HDF_ERR_NOT_SUPPORT;
    }
    capture->Init = Init;
    capture->SelectScene = SelectScene;
    capture->Start = Start;
    capture->Stop = Stop;
    capture->SetPauseState = Pause;
    capture->GetVolThreshold = GetRange;
    capture->GetVolume = GetVolume;
    capture->SetVolume = SetVolume;
    capture->GetMute = GetMute;
    capture->SetMute = SetMute;
    capture->GetGainThreshold = GetGainRange;
    capture->GetGain = GetGain;
    capture->SetGain = SetGain;
    return HDF_SUCCESS;
}
