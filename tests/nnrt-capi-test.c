#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "neural_network_core.h"
#include "neural_network_runtime.h"

static int fail(const char *what, int code)
{
    fprintf(stderr, "FAIL %s: %d\n", what, code);
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <offline-model.bin>\n", argv[0]);
        return 2;
    }

    const size_t *ids = NULL;
    uint32_t count = 0;
    int ret = OH_NNDevice_GetAllDevicesID(&ids, &count);
    if (ret != OH_NN_SUCCESS || ids == NULL || count == 0) return fail("device list", ret);

    size_t device = ids[0];
    const char *name = NULL;
    for (uint32_t i = 0; i < count; i++) {
        if (OH_NNDevice_GetName(ids[i], &name) == OH_NN_SUCCESS && name != NULL &&
            strstr(name, "X5") != NULL) {
            device = ids[i];
            break;
        }
    }
    printf("device=%zu name=%s count=%u\n", device, name ? name : "?", count);

    OH_NNCompilation *compilation = OH_NNCompilation_ConstructWithOfflineModelFile(argv[1]);
    if (compilation == NULL) return fail("construct offline model", -1);
    ret = OH_NNCompilation_SetDevice(compilation, device);
    if (ret == OH_NN_SUCCESS) ret = OH_NNCompilation_Build(compilation);
    if (ret != OH_NN_SUCCESS) {
        OH_NNCompilation_Destroy(&compilation);
        return fail("build", ret);
    }

    OH_NNExecutor *executor = OH_NNExecutor_Construct(compilation);
    OH_NNCompilation_Destroy(&compilation);
    if (executor == NULL) return fail("executor", -1);

    size_t input_count = 0;
    size_t output_count = 0;
    ret = OH_NNExecutor_GetInputCount(executor, &input_count);
    if (ret == OH_NN_SUCCESS) ret = OH_NNExecutor_GetOutputCount(executor, &output_count);
    if (ret != OH_NN_SUCCESS || input_count == 0 || output_count == 0) {
        OH_NNExecutor_Destroy(&executor);
        return fail("io count", ret);
    }
    printf("inputs=%zu outputs=%zu\n", input_count, output_count);

    NN_Tensor *inputs[4] = {0};
    NN_Tensor *outputs[4] = {0};
    size_t output_bytes[4] = {0};
    if (input_count > 4 || output_count > 4) return fail("too many tensors", -1);

    for (size_t i = 0; i < input_count; i++) {
        NN_TensorDesc *desc = OH_NNExecutor_CreateInputTensorDesc(executor, i);
        size_t bytes = 0;
        if (desc == NULL || OH_NNTensorDesc_GetByteSize(desc, &bytes) != OH_NN_SUCCESS) {
            return fail("input desc", i);
        }
        inputs[i] = OH_NNTensor_Create(device, desc);
        OH_NNTensorDesc_Destroy(&desc);
        if (inputs[i] == NULL) return fail("input tensor", i);
        void *data = OH_NNTensor_GetDataBuffer(inputs[i]);
        size_t size = 0;
        if (data == NULL || OH_NNTensor_GetSize(inputs[i], &size) != OH_NN_SUCCESS) {
            return fail("input buffer", i);
        }
        memset(data, 0x80, size);
        printf("input %zu bytes=%zu\n", i, size);
    }
    for (size_t i = 0; i < output_count; i++) {
        NN_TensorDesc *desc = OH_NNExecutor_CreateOutputTensorDesc(executor, i);
        size_t bytes = 0;
        if (desc == NULL || OH_NNTensorDesc_GetByteSize(desc, &bytes) != OH_NN_SUCCESS) {
            return fail("output desc", i);
        }
        output_bytes[i] = bytes;
        outputs[i] = OH_NNTensor_Create(device, desc);
        OH_NNTensorDesc_Destroy(&desc);
        if (outputs[i] == NULL) return fail("output tensor", i);
        printf("output %zu bytes=%zu\n", i, bytes);
    }

    ret = OH_NNExecutor_RunSync(executor, inputs, input_count, outputs, output_count);
    if (ret != OH_NN_SUCCESS) return fail("run", ret);

    for (size_t i = 0; i < output_count; i++) {
        const float *values = (const float *)OH_NNTensor_GetDataBuffer(outputs[i]);
        size_t size = 0;
        OH_NNTensor_GetSize(outputs[i], &size);
        size_t elements = size / sizeof(float);
        double sum = 0.0;
        size_t top = 0;
        for (size_t j = 0; j < elements; j++) {
            sum += values[j];
            if (values[j] > values[top]) top = j;
        }
        printf("output %zu elements=%zu sum=%.6f top=%zu value=%.6f\n",
               i, elements, sum, top, elements ? values[top] : 0.0f);
    }

    for (size_t i = 0; i < input_count; i++) OH_NNTensor_Destroy(&inputs[i]);
    for (size_t i = 0; i < output_count; i++) OH_NNTensor_Destroy(&outputs[i]);
    OH_NNExecutor_Destroy(&executor);
    printf("PASS: OH NNRT offline model inference\n");
    return 0;
}
