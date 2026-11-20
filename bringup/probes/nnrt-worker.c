#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "dnn/hb_dnn.h"

typedef int32_t (*initialize_fn)(hbPackedDNNHandle_t *, const char **, int32_t);
typedef int32_t (*release_fn)(hbPackedDNNHandle_t);
typedef int32_t (*names_fn)(const char ***, int32_t *, hbPackedDNNHandle_t);
typedef int32_t (*model_fn)(hbDNNHandle_t *, hbPackedDNNHandle_t, const char *);
typedef int32_t (*count_fn)(int32_t *, hbDNNHandle_t);
typedef int32_t (*name_fn)(const char **, hbDNNHandle_t, int32_t);
typedef int32_t (*props_fn)(hbDNNTensorProperties *, hbDNNHandle_t, int32_t);

static void shape(const hbDNNTensorShape *value)
{
    putchar('[');
    for (int32_t i = 0; i < value->numDimensions; ++i) {
        if (i) putchar(',');
        printf("%d", value->dimensionSize[i]);
    }
    putchar(']');
}

static int describe(void *library, const char *path)
{
    initialize_fn initialize = (initialize_fn)dlsym(library, "hbDNNInitializeFromFiles");
    release_fn release = (release_fn)dlsym(library, "hbDNNRelease");
    names_fn names = (names_fn)dlsym(library, "hbDNNGetModelNameList");
    model_fn model = (model_fn)dlsym(library, "hbDNNGetModelHandle");
    count_fn input_count = (count_fn)dlsym(library, "hbDNNGetInputCount");
    count_fn output_count = (count_fn)dlsym(library, "hbDNNGetOutputCount");
    name_fn input_name = (name_fn)dlsym(library, "hbDNNGetInputName");
    name_fn output_name = (name_fn)dlsym(library, "hbDNNGetOutputName");
    props_fn input_props = (props_fn)dlsym(library, "hbDNNGetInputTensorProperties");
    props_fn output_props = (props_fn)dlsym(library, "hbDNNGetOutputTensorProperties");
    if (!initialize || !release || !names || !model || !input_count || !output_count ||
        !input_name || !output_name || !input_props || !output_props) {
        fprintf(stderr, "DNN descriptor API is incomplete\n");
        return 1;
    }
    hbPackedDNNHandle_t packed = NULL;
    int32_t result = initialize(&packed, &path, 1);
    if (result != 0) {
        fprintf(stderr, "MODEL LOAD FAILED: %d\n", result);
        return 1;
    }
    const char **model_names = NULL;
    int32_t model_count = 0;
    result = names(&model_names, &model_count, packed);
    if (result != 0 || model_count < 1 || !model_names) {
        fprintf(stderr, "MODEL ENUMERATION FAILED: %d count=%d\n", result, model_count);
        release(packed);
        return 1;
    }
    for (int32_t m = 0; m < model_count; ++m) {
        hbDNNHandle_t handle = NULL;
        result = model(&handle, packed, model_names[m]);
        if (result != 0 || !handle) {
            fprintf(stderr, "MODEL HANDLE FAILED: %s (%d)\n", model_names[m], result);
            release(packed);
            return 1;
        }
        int32_t count = 0;
        if (input_count(&count, handle) != 0) return 1;
        printf("MODEL_INPUTS %s %d\n", model_names[m], count);
        for (int32_t i = 0; i < count; ++i) {
            const char *name = NULL;
            hbDNNTensorProperties properties;
            memset(&properties, 0, sizeof(properties));
            if (input_name(&name, handle, i) != 0 || input_props(&properties, handle, i) != 0) return 1;
            printf("INPUT %d %s shape=", i, name ? name : "?");
            shape(&properties.validShape);
            printf(" type=%d layout=%d bytes=%d\n", properties.tensorType,
                   properties.tensorLayout, properties.alignedByteSize);
        }
        if (output_count(&count, handle) != 0) return 1;
        printf("MODEL_OUTPUTS %s %d\n", model_names[m], count);
        for (int32_t i = 0; i < count; ++i) {
            const char *name = NULL;
            hbDNNTensorProperties properties;
            memset(&properties, 0, sizeof(properties));
            if (output_name(&name, handle, i) != 0 || output_props(&properties, handle, i) != 0) return 1;
            printf("OUTPUT %d %s shape=", i, name ? name : "?");
            shape(&properties.validShape);
            printf(" type=%d layout=%d bytes=%d\n", properties.tensorType,
                   properties.tensorLayout, properties.alignedByteSize);
        }
    }
    result = release(packed);
    return result == 0 ? 0 : 1;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "Usage: rdkhm-nnrt-worker --describe model.bin\n");
        return 2;
    }
    if (strcmp(argv[1], "--describe") != 0) return 2;
    void *library = dlopen("libdnn.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        fprintf(stderr, "LOAD FAILED libdnn.so: %s\n", dlerror());
        return 1;
    }
    int result = describe(library, argv[2]);
    dlclose(library);
    return result;
}
