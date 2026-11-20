#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <gbm.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include "accel_wire.h"

struct buffer {
    struct gbm_bo *bo;
    int fd;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t format;
    uint64_t modifier;
};

static int buffer_create(struct gbm_device *gbm, struct buffer *buffer, uint32_t width,
                         uint32_t height)
{
    memset(buffer, 0, sizeof(*buffer));
    buffer->bo = gbm_bo_create(gbm, width, height, GBM_FORMAT_ARGB8888,
                               GBM_BO_USE_RENDERING | GBM_BO_USE_LINEAR);
    if (buffer->bo == NULL) return -1;
    buffer->fd = gbm_bo_get_fd(buffer->bo);
    buffer->width = width;
    buffer->height = height;
    buffer->stride = gbm_bo_get_stride(buffer->bo);
    buffer->format = gbm_bo_get_format(buffer->bo);
    buffer->modifier = gbm_bo_get_modifier(buffer->bo);
    return buffer->fd < 0 ? -1 : 0;
}

static int buffer_fill(struct buffer *buffer, int foreground)
{
    uint32_t stride = 0;
    void *map_data = NULL;
    uint8_t *map = gbm_bo_map(buffer->bo, 0, 0, buffer->width, buffer->height,
                              GBM_BO_TRANSFER_WRITE, &stride, &map_data);
    if (map == NULL) return -1;
    for (uint32_t y = 0; y < buffer->height; y++) {
        uint32_t *row = (uint32_t *)(map + y * stride);
        for (uint32_t x = 0; x < buffer->width; x++) {
            row[x] = foreground ? 0xffff0000u :
                     (x < buffer->width / 2 ? 0xff00ff00u : 0xff0000ffu);
        }
    }
    gbm_bo_unmap(buffer->bo, map_data);
    return 0;
}

static int send_compose(int sock, const struct buffer *target, const struct buffer *background,
                        const struct buffer *foreground, int input_fence)
{
    struct {
        struct rdkhm_wire_header header;
        struct rdkhm_compose_request request;
        struct rdkhm_compose_layer layers[2];
    } message;
    memset(&message, 0, sizeof(message));
    message.header.magic = RDKHM_WIRE_MAGIC;
    message.header.version = RDKHM_WIRE_VERSION;
    message.header.command = RDKHM_WIRE_COMPOSE;
    message.header.payload = sizeof(message.request) + sizeof(message.layers);
    message.header.fds = input_fence >= 0 ? 4 : 3;
    message.request.target_fd_index = 0;
    message.request.target_fence_fd_index = UINT32_MAX;
    message.request.target_format = target->format;
    message.request.target_width = target->width;
    message.request.target_height = target->height;
    message.request.target_stride = target->stride;
    message.request.target_modifier = target->modifier;
    message.request.layer_count = 2;
    message.layers[0].fd_index = 1;
    message.layers[0].fence_fd_index = UINT32_MAX;
    message.layers[0].format = background->format;
    message.layers[0].width = background->width;
    message.layers[0].height = background->height;
    message.layers[0].stride = background->stride;
    message.layers[0].modifier = background->modifier;
    message.layers[0].crop_w = background->width;
    message.layers[0].crop_h = background->height;
    message.layers[0].dst_w = background->width;
    message.layers[0].dst_h = background->height;
    message.layers[0].alpha = 255;
    message.layers[1].fd_index = 2;
    message.layers[1].fence_fd_index = UINT32_MAX;
    message.layers[1].format = foreground->format;
    message.layers[1].width = foreground->width;
    message.layers[1].height = foreground->height;
    message.layers[1].stride = foreground->stride;
    message.layers[1].modifier = foreground->modifier;
    message.layers[1].crop_w = foreground->width;
    message.layers[1].crop_h = foreground->height;
    message.layers[1].dst_x = 16;
    message.layers[1].dst_y = 16;
    message.layers[1].dst_w = foreground->width;
    message.layers[1].dst_h = foreground->height;
    message.layers[1].alpha = 128;
    message.layers[1].blend = 1;

    int fds[4] = {target->fd, background->fd, foreground->fd, input_fence};
    int fd_count = input_fence >= 0 ? 4 : 3;
    if (input_fence >= 0) {
        message.layers[0].fence_fd_index = 3;
        message.layers[0].fd_index = 1;
    }
    struct iovec iov = {.iov_base = &message.header, .iov_len = sizeof(message.header)};
    char control[CMSG_SPACE(sizeof(int) * 4)];
    struct msghdr msg = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control,
        .msg_controllen = sizeof(control),
    };
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(int) * (size_t)fd_count);
    memcpy(CMSG_DATA(cmsg), fds, sizeof(int) * (size_t)fd_count);
    if (sendmsg(sock, &msg, MSG_NOSIGNAL) < 0) return -1;
    const unsigned char *payload = (const unsigned char *)&message.request;
    size_t length = sizeof(message.request) + sizeof(message.layers);
    if (send(sock, payload, length, MSG_NOSIGNAL) != (ssize_t)length) return -1;
    return 0;
}

static int receive_compose(int sock, struct rdkhm_compose_response *response, int *fence_fd)
{
    struct rdkhm_wire_header header;
    struct iovec iov = {.iov_base = &header, .iov_len = sizeof(header)};
    char control[CMSG_SPACE(sizeof(int))];
    struct msghdr msg = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control,
        .msg_controllen = sizeof(control),
    };
    ssize_t got = recvmsg(sock, &msg, 0);
    if (got != (ssize_t)sizeof(header)) return -1;
    *fence_fd = -1;
    for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg); cmsg != NULL;
         cmsg = CMSG_NXTHDR(&msg, cmsg)) {
        if (cmsg->cmsg_level == SOL_SOCKET && cmsg->cmsg_type == SCM_RIGHTS) {
            memcpy(fence_fd, CMSG_DATA(cmsg), sizeof(int));
        }
    }
    if (header.magic != RDKHM_WIRE_MAGIC || header.command != RDKHM_WIRE_COMPOSE) return -1;
    memset(response, 0, sizeof(*response));
    size_t copy = header.payload < sizeof(*response) ? header.payload : sizeof(*response);
    if (copy > 0 && recv(sock, response, copy, MSG_WAITALL) != (ssize_t)copy) return -1;
    if (header.payload > copy) {
        unsigned char discard[64];
        size_t left = header.payload - copy;
        while (left > 0) {
            size_t chunk = left < sizeof(discard) ? left : sizeof(discard);
            if (recv(sock, discard, chunk, MSG_WAITALL) != (ssize_t)chunk) return -1;
            left -= chunk;
        }
    }
    return 0;
}

static int connect_socket(const char *path)
{
    int sock = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (sock < 0) return -1;
    struct sockaddr_un address = {0};
    address.sun_family = AF_UNIX;
    snprintf(address.sun_path, sizeof(address.sun_path), "%s", path);
    if (connect(sock, (struct sockaddr *)&address, sizeof(address)) < 0) {
        close(sock);
        return -1;
    }
    return sock;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <socket>\n", argv[0]);
        return 2;
    }
    int card = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (card < 0) { perror("open card0"); return 1; }
    struct gbm_device *gbm = gbm_create_device(card);
    if (gbm == NULL) return 1;
    struct buffer target, background, foreground;
    if (buffer_create(gbm, &target, 64, 64) || buffer_create(gbm, &background, 64, 64) ||
        buffer_create(gbm, &foreground, 32, 32) || buffer_fill(&background, 0) ||
        buffer_fill(&foreground, 1)) {
        return 1;
    }
    int sock = connect_socket(argv[1]);
    if (sock < 0) {
        perror("connect");
        return 1;
    }
    if (send_compose(sock, &target, &background, &foreground, -1) < 0) {
        perror("send");
        return 1;
    }
    struct rdkhm_compose_response response;
    int fence_fd = -1;
    if (receive_compose(sock, &response, &fence_fd) < 0) {
        fprintf(stderr, "receive failed\n");
        return 1;
    }
    printf("status=%u layers=%u elapsed=%ums fence_fd=%d\n", response.status,
           response.layers, response.elapsed_ms, fence_fd);
    int fence_ok = 1;
    if (fence_fd >= 0) {
        struct pollfd ready = {.fd = fence_fd, .events = POLLIN};
        fence_ok = poll(&ready, 1, 3000) > 0;
    }
    int input_fence_ok = 0;
    int first_fence = fence_fd;
    fence_fd = -1;
    close(sock);
    sock = connect_socket(argv[1]);
    if (first_fence >= 0 && sock >= 0 &&
        send_compose(sock, &target, &background, &foreground, first_fence) == 0) {
        struct rdkhm_compose_response second;
        if (receive_compose(sock, &second, &fence_fd) == 0) {
            printf("input_fence status=%u layers=%u elapsed=%ums fence_fd=%d\n",
                   second.status, second.layers, second.elapsed_ms, fence_fd);
            if (second.status == RDKHM_STATUS_OK && fence_fd >= 0) {
                struct pollfd ready = {.fd = fence_fd, .events = POLLIN};
                input_fence_ok = poll(&ready, 1, 3000) > 0;
            }
        }
    }
    if (fence_fd >= 0) close(fence_fd);
    if (first_fence >= 0) close(first_fence);
    int pixels_ok = 0;
    uint32_t stride = 0;
    void *map_data = NULL;
    uint8_t *map = gbm_bo_map(target.bo, 0, 0, 64, 64, GBM_BO_TRANSFER_READ, &stride, &map_data);
    if (map != NULL) {
        uint32_t left = *(uint32_t *)(map + 32 * stride + 8 * 4);
        uint32_t blend = *(uint32_t *)(map + 32 * stride + 24 * 4);
        uint32_t right = *(uint32_t *)(map + 32 * stride + 56 * 4);
        printf("cpu left=0x%08x blend=0x%08x right=0x%08x\n", left, blend, right);
        pixels_ok = left == 0xff00ff00u && right == 0xff0000ffu &&
                    abs((int)((blend >> 16) & 0xff) - 128) <= 8 &&
                    abs((int)((blend >> 8) & 0xff) - 128) <= 8 &&
                    ((blend & 0xff) <= 8);
        gbm_bo_unmap(target.bo, map_data);
    } else {
        fprintf(stderr, "target mmap failed\n");
    }
    int pass = response.status == RDKHM_STATUS_OK && response.layers == 2 && fence_ok &&
               input_fence_ok && pixels_ok;
    printf("fence_ok=%d input_fence_ok=%d pixels_ok=%d\n", fence_ok, input_fence_ok, pixels_ok);
    puts(pass ? "GPU_COMPOSE_WIRE_PASS" : "GPU_COMPOSE_WIRE_FAIL");
    close(sock);
    gbm_device_destroy(gbm);
    close(card);
    return pass ? 0 : 1;
}
