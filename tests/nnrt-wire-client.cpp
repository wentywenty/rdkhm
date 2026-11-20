#include <cassert>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

#include "rdkhm_accel_client.h"

int main(int argc, char **argv)
{
    assert(argc == 2);
    rdkhm::AccelClient client(argv[1]);
    assert(client.Hello() == RDKHM_STATUS_OK);

    uint32_t session = 0;
    assert(client.Load(nullptr, 0, session) == RDKHM_STATUS_INVALID_PARAMETER);
    assert(client.LoadFd(-1, session) == RDKHM_STATUS_INVALID_PARAMETER);

    int empty = memfd_create("empty-model", 0);
    assert(empty >= 0);
    assert(client.LoadFd(empty, session) == RDKHM_STATUS_INVALID_MODEL);
    close(empty);

    std::vector<rdkhm::IoDesc> inputs;
    std::vector<rdkhm::IoDesc> outputs;
    assert(client.Info(999, inputs, outputs) == RDKHM_STATUS_INVALID_MODEL);
    assert(client.Release(999) == RDKHM_STATUS_INVALID_MODEL);

    std::vector<rdkhm::Buffer> no_inputs;
    std::vector<rdkhm::Buffer> no_outputs;
    std::vector<std::vector<uint32_t>> dims;
    assert(client.Run(999, no_inputs, no_outputs, dims) == RDKHM_STATUS_INVALID_MODEL);

    std::puts("PASS: accelerator client");
    return 0;
}
