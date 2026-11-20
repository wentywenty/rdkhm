#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "dnn/hb_dnn.h"

static void *load(const char *name)
{
    void *handle = dlopen(name, RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) fprintf(stderr, "LOAD FAILED %s: %s\n", name, dlerror());
    else printf("LOADED %s\n", name);
    return handle;
}

static int models(void *dnn, const char *path)
{
    int32_t (*initialize)(hbPackedDNNHandle_t *, const char **, int32_t) = dlsym(dnn, "hbDNNInitializeFromFiles");
    int32_t (*names)(const char ***, int32_t *, hbPackedDNNHandle_t) = dlsym(dnn, "hbDNNGetModelNameList");
    int32_t (*release)(hbPackedDNNHandle_t) = dlsym(dnn, "hbDNNRelease");
    if (initialize == NULL || names == NULL || release == NULL) return 1;
    hbPackedDNNHandle_t packed = NULL;
    int32_t result = initialize(&packed, &path, 1);
    if (result != 0) {
        fprintf(stderr, "MODEL LOAD FAILED: %d\n", result);
        return 1;
    }
    const char **list = NULL;
    int32_t count = 0;
    result = names(&list, &count, packed);
    if (result == 0 && count > 0 && list != NULL) {
        for (int32_t i = 0; i < count; ++i) printf("MODEL %s\n", list[i]);
    } else {
        fprintf(stderr, "MODEL ENUMERATION FAILED: %d count=%d\n", result, count);
        result = -1;
    }
    int32_t cleanup = release(packed);
    return result != 0 || cleanup != 0;
}

int main(int argc, char **argv)
{
    if (argc != 2 && argc != 3) {
        fprintf(stderr, "Usage: rdkhm-accelerator --check | --models model.bin\n");
        return 2;
    }
    int check = argc == 2 && strcmp(argv[1], "--check") == 0;
    int inspect = argc == 3 && strcmp(argv[1], "--models") == 0;
    if (!check && !inspect) return 2;
    void *dnn = load("libdnn.so");
    if (dnn == NULL) return 1;
    const char *(*version)(void) = dlsym(dnn, "hbDNNGetVersion");
    const char *value = version == NULL ? NULL : version();
    if (value == NULL) { dlclose(dnn); return 1; }
    printf("DNN_VERSION %s\n", value);
    int result = 0;
    if (inspect) {
        result = models(dnn, argv[2]);
    } else {
        void *egl = load("libEGL.so.1");
        void *gles = load("libGLESv2.so.2");
        if (egl == NULL || gles == NULL) result = 1;
        if (gles != NULL) dlclose(gles);
        if (egl != NULL) dlclose(egl);
        if (!result) puts("LIBRARY_CHECK_PASS: no rendering or inference was performed");
    }
    dlclose(dnn);
    return result;
}
