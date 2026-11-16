#include <assert.h>
#include <stdio.h>
#include "x5_audio.h"

static int opened, closed, writes, fail_open, fail_info, fail_read, fail_write;
static unsigned int channels = 2;
static long saved[2] = {10, 20};
static int fake_handle;
static snd_pcm_state_t pcm_state = SND_PCM_STATE_SETUP;
static int fail_pcm, prepares, drops, pauses;

int snd_ctl_open(snd_ctl_t **handle, const char *name, int mode)
{
    (void)name;
    (void)mode;
    if (fail_open) return -1;
    *handle = (snd_ctl_t *)&fake_handle;
    opened++;
    return 0;
}

int snd_ctl_close(snd_ctl_t *handle)
{
    assert(handle == (snd_ctl_t *)&fake_handle);
    closed++;
    return 0;
}

int snd_ctl_elem_info(snd_ctl_t *handle, snd_ctl_elem_info_t *info)
{
    (void)handle;
    (void)info;
    return fail_info ? -1 : 0;
}

snd_ctl_elem_type_t snd_ctl_elem_info_get_type(const snd_ctl_elem_info_t *info)
{
    (void)info;
    return SND_CTL_ELEM_TYPE_INTEGER;
}

unsigned int snd_ctl_elem_info_get_count(const snd_ctl_elem_info_t *info)
{
    (void)info;
    return channels;
}

long snd_ctl_elem_info_get_min(const snd_ctl_elem_info_t *info)
{
    (void)info;
    return 0;
}

long snd_ctl_elem_info_get_max(const snd_ctl_elem_info_t *info)
{
    (void)info;
    return 191;
}

int snd_ctl_elem_read(snd_ctl_t *handle, snd_ctl_elem_value_t *value)
{
    (void)handle;
    if (fail_read) return -1;
    for (unsigned int i = 0; i < 2; i++) snd_ctl_elem_value_set_integer(value, i, saved[i]);
    return 0;
}

int snd_ctl_elem_write(snd_ctl_t *handle, snd_ctl_elem_value_t *value)
{
    (void)handle;
    if (fail_write) return -1;
    for (unsigned int i = 0; i < 2; i++) saved[i] = snd_ctl_elem_value_get_integer(value, i);
    writes++;
    return 1;
}

snd_pcm_state_t snd_pcm_state(snd_pcm_t *handle)
{
    (void)handle;
    return pcm_state;
}

int snd_pcm_prepare(snd_pcm_t *handle)
{
    (void)handle;
    prepares++;
    if (fail_pcm) return -1;
    pcm_state = SND_PCM_STATE_PREPARED;
    return 0;
}

int snd_pcm_drop(snd_pcm_t *handle)
{
    (void)handle;
    drops++;
    if (fail_pcm) return -1;
    pcm_state = SND_PCM_STATE_SETUP;
    return 0;
}

int snd_pcm_pause(snd_pcm_t *handle, int pause)
{
    (void)handle;
    pauses++;
    if (fail_pcm) return -1;
    pcm_state = pause ? SND_PCM_STATE_PAUSED : SND_PCM_STATE_RUNNING;
    return 0;
}

int main(void)
{
    struct AlsaSoundCard card = {.ctrlName = "hw:7", .pcmHandle = (snd_pcm_t *)&fake_handle};
    long value = -1, maximum = -1;
    assert(X5Control(NULL, "volume", X5_READ, &value, NULL) == HDF_ERR_INVALID_PARAM);
    assert(X5Control(&card, "volume", X5_RANGE, &value, &maximum) == 0);
    assert(value == 0 && maximum == 191);
    assert(X5Control(&card, "volume", X5_READ, &value, NULL) == 0 && value == 10);
    value = 42;
    assert(X5Control(&card, "volume", X5_WRITE, &value, NULL) == 0);
    assert(saved[0] == 42 && saved[1] == 42 && writes == 1);
    value = 192;
    assert(X5Control(&card, "volume", X5_WRITE, &value, NULL) == HDF_ERR_INVALID_PARAM);
    assert(writes == 1);
    int *failures[] = {&fail_open, &fail_info, &fail_read, &fail_write};
    value = 5;
    for (unsigned int i = 0; i < sizeof(failures) / sizeof(failures[0]); i++) {
        *failures[i] = 1;
        assert(X5Control(&card, "volume", X5_WRITE, &value, NULL) == HDF_FAILURE);
        assert(opened == closed);
        *failures[i] = 0;
    }
    channels = 129;
    assert(X5Control(&card, "volume", X5_WRITE, &value, NULL) == HDF_FAILURE);
    assert(opened == closed);
    assert(X5Prepare(&card) == 0 && prepares == 1);
    assert(X5Prepare(&card) == 0 && prepares == 1);
    assert(X5Pause(&card, true) == HDF_ERR_NOT_SUPPORT && pauses == 0);
    card.canPause = true;
    assert(X5Pause(&card, true) == 0 && card.pauseState);
    assert(X5Pause(&card, true) == 0 && pauses == 1);
    fail_pcm = 1;
    assert(X5Pause(&card, false) == HDF_FAILURE && card.pauseState);
    assert(X5Stop(&card) == HDF_FAILURE && card.pauseState);
    fail_pcm = 0;
    assert(X5Stop(&card) == 0 && !card.pauseState && drops == 2);
    assert(X5Prepare(&card) == 0 && prepares == 2);
    assert(X5Pause(&card, true) == 0 && card.pauseState && pauses == 3);
    assert(X5Pause(&card, false) == 0 && !card.pauseState);
    card.pcmHandle = NULL;
    assert(X5Prepare(&card) == HDF_ERR_INVALID_PARAM);
    assert(X5Stop(&card) == HDF_ERR_INVALID_PARAM);
    puts("PASS: X5 control ranges, both channels, failure cleanup and PCM restart/pause");
    return 0;
}
