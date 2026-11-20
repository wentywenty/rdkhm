#define _GNU_SOURCE
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

#include "rdkhm_accel_client.h"

static void PrintShape(const rdkhm::IoDesc &desc)
{
    std::printf("[");
    for (uint32_t i = 0; i < desc.rank; i++) {
        std::printf("%s%u", i ? "," : "", desc.dims[i]);
    }
    std::printf("] type=%u format=%u bytes=%u", desc.type, desc.format, desc.bytes);
}

int main(int argc, char **argv)
{
    if (argc != 3) { std::fprintf(stderr, "usage: %s <socket> <model>\n", argv[0]); return 2; }
    int model = open(argv[2], O_RDONLY | O_CLOEXEC);
    if (model < 0) { std::perror(argv[2]); return 1; }
    rdkhm::AccelClient client(argv[1]);

    uint32_t session = 0;
    int32_t status = client.LoadFd(model, session);
    std::printf("load status=%d session=%u\n", status, session);
    if (status != RDKHM_STATUS_OK) return 1;

    std::vector<rdkhm::IoDesc> inputs;
    std::vector<rdkhm::IoDesc> outputs;
    status = client.Info(session, inputs, outputs);
    std::printf("info status=%d inputs=%zu outputs=%zu\n", status, inputs.size(), outputs.size());
    if (status != RDKHM_STATUS_OK) return 1;
    for (size_t i = 0; i < inputs.size(); i++) {
        std::printf("input %zu ", i); PrintShape(inputs[i]); std::printf("\n");
    }
    for (size_t i = 0; i < outputs.size(); i++) {
        std::printf("output %zu ", i); PrintShape(outputs[i]); std::printf("\n");
    }

    std::vector<int> input_fds;
    std::vector<int> output_fds;
    std::vector<rdkhm::Buffer> input_buffers;
    std::vector<rdkhm::Buffer> output_buffers;
    for (const auto &desc : inputs) {
        int fd = memfd_create("nnrt-input", 0);
        if (fd < 0 || ftruncate(fd, desc.bytes) != 0) { std::perror("input memfd"); return 1; }
        std::vector<uint8_t> data(desc.bytes, 0x80);
        if (pwrite(fd, data.data(), data.size(), 0) != static_cast<ssize_t>(data.size())) return 1;
        input_fds.push_back(fd);
        input_buffers.push_back({fd, 0, desc.bytes});
    }
    for (const auto &desc : outputs) {
        int fd = memfd_create("nnrt-output", 0);
        if (fd < 0 || ftruncate(fd, desc.bytes) != 0) { std::perror("output memfd"); return 1; }
        output_fds.push_back(fd);
        output_buffers.push_back({fd, 0, desc.bytes});
    }

    std::vector<std::vector<uint32_t>> output_dims;
    status = client.Run(session, input_buffers, output_buffers, output_dims);
    std::printf("run status=%d\n", status);
    if (status != RDKHM_STATUS_OK) return 1;

    for (size_t i = 0; i < output_fds.size(); i++) {
        std::vector<float> values(outputs[i].bytes / sizeof(float));
        if (pread(output_fds[i], values.data(), values.size() * sizeof(float), 0) < 0) return 1;
        double sum = 0;
        size_t top = 0;
        for (size_t j = 0; j < values.size(); j++) {
            sum += values[j];
            if (values[j] > values[top]) top = j;
        }
        std::printf("output %zu dims=[", i);
        for (size_t d = 0; d < output_dims[i].size(); d++) {
            std::printf("%s%u", d ? "," : "", output_dims[i][d]);
        }
        std::printf("] sum=%.6f top=%zu value=%.6f\n", sum, top, values[top]);
    }

    for (int fd : input_fds) close(fd);
    for (int fd : output_fds) close(fd);
    close(model);
    std::printf("PASS: inference run\n");
    return 0;
}
