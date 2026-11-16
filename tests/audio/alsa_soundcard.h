#ifndef TEST_ALSA_SOUNDCARD_H
#define TEST_ALSA_SOUNDCARD_H
#include <alsa/asoundlib.h>
#include <stdbool.h>
#include <stdint.h>
#define HDF_SUCCESS 0
#define HDF_FAILURE (-1)
#define HDF_ERR_INVALID_PARAM (-2)
#define HDF_ERR_NOT_SUPPORT (-3)
/* Only the fields used by x5_audio.h; the real ABI is checked by the OH build. */
struct AlsaSoundCard {
    char ctrlName[65];
    snd_pcm_t *pcmHandle;
    bool canPause;
    bool pauseState;
};
#endif
