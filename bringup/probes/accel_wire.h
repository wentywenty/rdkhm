#ifndef RDKHM_ACCEL_WIRE_H
#define RDKHM_ACCEL_WIRE_H

#include <stdint.h>

/* Binary accelerator protocol carried over the same AF_UNIX stream as the
 * newline text probes. A binary frame always starts with RDKHM_WIRE_MAGIC.
 * All integers are little-endian; file descriptors travel as SCM_RIGHTS. */
#define RDKHM_WIRE_MAGIC 0x314B4452u /* "RDK1" */
#define RDKHM_WIRE_VERSION 1u
#define RDKHM_WIRE_MAX_DIMS 8u
#define RDKHM_WIRE_MAX_TENSORS 16u
#define RDKHM_WIRE_MAX_FDS 16u
#define RDKHM_WIRE_MAX_LAYERS 8u
#define RDKHM_WIRE_MAX_PAYLOAD (64u * 1024u * 1024u)

enum rdkhm_wire_command {
    RDKHM_WIRE_HELLO = 1,
    RDKHM_WIRE_LOAD = 2,
    RDKHM_WIRE_INFO = 3,
    RDKHM_WIRE_RUN = 4,
    RDKHM_WIRE_RELEASE = 5,
    RDKHM_WIRE_COMPOSE = 6,
};

/* Values intentionally match OHOS::HDI::Nnrt NNRT_ReturnCode. */
enum rdkhm_wire_status {
    RDKHM_STATUS_OK = 0,
    RDKHM_STATUS_FAILED = 1,
    RDKHM_STATUS_NULL_PTR = 2,
    RDKHM_STATUS_INVALID_PARAMETER = 3,
    RDKHM_STATUS_MEMORY_ERROR = 4,
    RDKHM_STATUS_OUT_OF_MEMORY = 5,
    RDKHM_STATUS_NOT_SUPPORT = 11,
    RDKHM_STATUS_SERVICE_ERROR = 12,
    RDKHM_STATUS_DEVICE_ERROR = 13,
    RDKHM_STATUS_DEVICE_BUSY = 14,
    RDKHM_STATUS_TIME_OUT = 17,
    RDKHM_STATUS_INVALID_INPUT = 20,
    RDKHM_STATUS_INVALID_OUTPUT = 21,
    RDKHM_STATUS_INVALID_BUFFER = 27,
    RDKHM_STATUS_INVALID_BUFFER_SIZE = 28,
    RDKHM_STATUS_INVALID_MODEL = 31,
};

struct rdkhm_wire_header {
    uint32_t magic;
    uint16_t version;
    uint16_t command;
    uint32_t session;
    uint32_t payload;
    uint16_t fds;
    uint16_t flags;
    uint32_t reserved;
} __attribute__((packed));

struct rdkhm_io_desc {
    uint32_t type;
    uint32_t format;
    uint32_t rank;
    uint32_t dims[RDKHM_WIRE_MAX_DIMS];
    uint32_t bytes;
    uint32_t reserved;
} __attribute__((packed));

struct rdkhm_io_response {
    uint32_t status;
    uint32_t input_count;
    uint32_t output_count;
} __attribute__((packed));

struct rdkhm_buffer_desc {
    uint32_t fd_index;
    uint32_t reserved;
    uint64_t offset;
    uint64_t bytes;
} __attribute__((packed));

struct rdkhm_run_request {
    uint32_t input_count;
    uint32_t output_count;
} __attribute__((packed));

struct rdkhm_run_output {
    uint32_t rank;
    uint32_t dims[RDKHM_WIRE_MAX_DIMS];
    uint32_t bytes;
    uint32_t reserved;
} __attribute__((packed));

struct rdkhm_load_request {
    uint32_t model_bytes;
    uint32_t reserved;
} __attribute__((packed));

struct rdkhm_compose_layer {
    uint32_t fd_index;
    uint32_t fence_fd_index;
    uint32_t format;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint64_t modifier;
    uint32_t crop_x;
    uint32_t crop_y;
    uint32_t crop_w;
    uint32_t crop_h;
    int32_t dst_x;
    int32_t dst_y;
    uint32_t dst_w;
    uint32_t dst_h;
    uint32_t alpha;
    uint32_t transform;
    uint32_t blend;
    uint32_t reserved;
} __attribute__((packed));

struct rdkhm_compose_request {
    uint32_t target_fd_index;
    uint32_t target_fence_fd_index;
    uint32_t target_format;
    uint32_t target_width;
    uint32_t target_height;
    uint32_t target_stride;
    uint64_t target_modifier;
    uint32_t layer_count;
    uint32_t flags;
} __attribute__((packed));

struct rdkhm_compose_response {
    uint32_t status;
    uint32_t elapsed_ms;
    uint32_t layers;
    uint32_t reserved;
} __attribute__((packed));

#endif /* RDKHM_ACCEL_WIRE_H */
