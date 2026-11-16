#ifndef RDKHM_X5_AUDIO_H
#define RDKHM_X5_AUDIO_H

#include "alsa_soundcard.h"

enum X5ControlOperation { X5_RANGE, X5_READ, X5_WRITE };

/* ES8326 exposes integer controls; update every channel and always close the fd. */
static inline int32_t X5Control(struct AlsaSoundCard *card, const char *name,
    enum X5ControlOperation operation, long *value, long *maximum)
{
    if (card == NULL || name == NULL || value == NULL || (operation == X5_RANGE && maximum == NULL)) {
        return HDF_ERR_INVALID_PARAM;
    }
    snd_ctl_t *ctl = NULL;
    snd_ctl_elem_info_t *info;
    snd_ctl_elem_value_t *data;
    snd_ctl_elem_info_alloca(&info);
    snd_ctl_elem_value_alloca(&data);
    if (snd_ctl_open(&ctl, card->ctrlName, 0) < 0) {
        return HDF_FAILURE;
    }
    int32_t result = HDF_FAILURE;
    snd_ctl_elem_info_set_interface(info, SND_CTL_ELEM_IFACE_MIXER);
    snd_ctl_elem_info_set_name(info, name);
    if (snd_ctl_elem_info(ctl, info) < 0 || snd_ctl_elem_info_get_type(info) != SND_CTL_ELEM_TYPE_INTEGER) {
        goto done;
    }
    long minimum = snd_ctl_elem_info_get_min(info);
    long upper = snd_ctl_elem_info_get_max(info);
    unsigned int count = snd_ctl_elem_info_get_count(info);
    if (count == 0 || count > 128 || minimum > upper) {
        goto done;
    }
    if (operation == X5_RANGE) {
        *value = minimum;
        *maximum = upper;
        result = HDF_SUCCESS;
        goto done;
    }
    snd_ctl_elem_value_set_interface(data, SND_CTL_ELEM_IFACE_MIXER);
    snd_ctl_elem_value_set_name(data, name);
    if (snd_ctl_elem_read(ctl, data) < 0) {
        goto done;
    }
    if (operation == X5_READ) {
        *value = snd_ctl_elem_value_get_integer(data, 0);
        result = HDF_SUCCESS;
    } else if (operation == X5_WRITE) {
        if (*value < minimum || *value > upper) {
            result = HDF_ERR_INVALID_PARAM;
            goto done;
        }
        for (unsigned int i = 0; i < count; ++i) {
            snd_ctl_elem_value_set_integer(data, i, *value);
        }
        result = snd_ctl_elem_write(ctl, data) < 0 ? HDF_FAILURE : HDF_SUCCESS;
    }
done:
    snd_ctl_close(ctl);
    return result;
}

static inline int32_t X5Prepare(struct AlsaSoundCard *card)
{
    if (card == NULL || card->pcmHandle == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    snd_pcm_state_t state = snd_pcm_state(card->pcmHandle);
    if (state == SND_PCM_STATE_PREPARED || state == SND_PCM_STATE_RUNNING) {
        return HDF_SUCCESS;
    }
    if (snd_pcm_prepare(card->pcmHandle) < 0) {
        return HDF_FAILURE;
    }
    card->pauseState = false;
    return HDF_SUCCESS;
}

static inline int32_t X5Stop(struct AlsaSoundCard *card)
{
    if (card == NULL || card->pcmHandle == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    if (snd_pcm_drop(card->pcmHandle) < 0) {
        return HDF_FAILURE;
    }
    card->pauseState = false;
    return HDF_SUCCESS;
}

static inline int32_t X5Pause(struct AlsaSoundCard *card, bool pause)
{
    if (card == NULL || card->pcmHandle == NULL) {
        return HDF_ERR_INVALID_PARAM;
    }
    if (!card->canPause) {
        return HDF_ERR_NOT_SUPPORT;
    }
    if (card->pauseState == pause) {
        return HDF_SUCCESS;
    }
    if (snd_pcm_pause(card->pcmHandle, pause) < 0) {
        return HDF_FAILURE;
    }
    card->pauseState = pause;
    return HDF_SUCCESS;
}

#endif
