#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <sys/stat.h>
#include <time.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static volatile sig_atomic_t server_fd = -1;

static long long milliseconds(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static int inherited_socket(void)
{
    const char *value = getenv("OHOS_SOCKET_rdkhm_accel");
    if (value == NULL || *value == '\0') {
        return -1;
    }
    char *end = NULL;
    long parsed = strtol(value, &end, 10);
    if (end == value || *end != '\0' || parsed < 3 || parsed > INT_MAX) {
        return -1;
    }
    int fd = (int)parsed;
    int socket_type = 0;
    socklen_t length = sizeof(socket_type);
    if (getsockopt(fd, SOL_SOCKET, SO_TYPE, &socket_type, &length) < 0 ||
        socket_type != SOCK_STREAM) {
        return -1;
    }
    struct sockaddr_un address = {0};
    length = sizeof(address);
    if (getsockname(fd, (struct sockaddr *)&address, &length) < 0 ||
        address.sun_family != AF_UNIX) return -1;
    return fd;
}

static void stop_handler(int signal_number)
{
    (void)signal_number;
    running = 0;
    if (server_fd >= 0) {
        close(server_fd);
        server_fd = -1;
    }
}

static int load_library(const char *name)
{
    void *handle = dlopen(name, RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) {
        return -1;
    }
    dlclose(handle);
    return 0;
}

static void reply(int client, const char *message)
{
    size_t remaining = strlen(message);
    const char *cursor = message;
    while (remaining > 0) {
        ssize_t written = send(client, cursor, remaining, MSG_NOSIGNAL);
        if (written < 0 && errno == EINTR && running) continue;
        if (written <= 0) {
            return;
        }
        cursor += written;
        remaining -= (size_t)written;
    }
}

static void handle_client(int client)
{
    char command[128] = {0};
    size_t used = 0;
    long long deadline = milliseconds() + 2000;
    while (running) {
        int timeout = (int)(deadline - milliseconds());
        struct pollfd ready = {.fd = client, .events = POLLIN};
        if (timeout <= 0) { reply(client, "ERROR timeout\n"); return; }
        int result = poll(&ready, 1, timeout);
        if (result < 0 && errno == EINTR) continue;
        if (result <= 0) { reply(client, "ERROR timeout\n"); return; }
        char byte;
        ssize_t length = recv(client, &byte, 1, 0);
        if (length < 0 && errno == EINTR) continue;
        if (length <= 0) return;
        if (byte == '\n') break;
        if (byte == '\0' || used == sizeof(command) - 1) {
            reply(client, "ERROR invalid-frame\n"); return;
        }
        command[used++] = byte;
    }
    if (!running) return;
    if (used && command[used - 1] == '\r') command[used - 1] = '\0';
    if (strcmp(command, "PING") == 0) {
        reply(client, "PONG\n");
        return;
    }
    if (strcmp(command, "GPU_CHECK") == 0) {
        int egl = load_library("libEGL.so.1");
        int gles = load_library("libGLESv2.so.2");
        reply(client, egl == 0 && gles == 0 ? "GPU_RUNTIME_READY\n" : "GPU_RUNTIME_UNAVAILABLE\n");
        return;
    }
    if (strcmp(command, "NPU_CHECK") == 0) {
        reply(client, load_library("libdnn.so") == 0 ? "NPU_RUNTIME_READY\n" : "NPU_RUNTIME_UNAVAILABLE\n");
        return;
    }
    if (strcmp(command, "NNRT_BACKEND") == 0) {
        reply(client, "NNRT_BACKEND_UNAVAILABLE\n");
        return;
    }
    reply(client, "ERROR unsupported-command\n");
}

int main(int argc, char **argv)
{
    const char *socket_path = "/dev/unix/socket/rdkhm_accel";
    if (argc == 3 && strcmp(argv[1], "--socket") == 0) {
        socket_path = argv[2];
    } else if (argc != 1) {
        fprintf(stderr, "usage: accelerator-daemon [--socket path]\n");
        return 2;
    }

    int server = argc == 1 ? inherited_socket() : -1;
    if (argc == 1 && server < 0) {
        fprintf(stderr, "Missing or invalid init socket\n");
        return 1;
    }
    int owns_path = 0;
    if (server < 0) {
        server = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        if (server < 0) {
            perror("socket");
            return 1;
        }
        struct sockaddr_un address = {0};
        address.sun_family = AF_UNIX;
        if (snprintf(address.sun_path, sizeof(address.sun_path), "%s", socket_path) >= (int)sizeof(address.sun_path)) {
            close(server);
            return 2;
        }
        umask(0077);
        if (bind(server, (struct sockaddr *)&address, sizeof(address)) < 0 || listen(server, 4) < 0) {
            perror("bind/listen");
            close(server);
            return 1;
        }
        owns_path = 1;
    }
    if (listen(server, 4) < 0) { close(server); return 1; }
    server_fd = server;
    struct sigaction action = {.sa_handler = stop_handler};
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    while (running) {
        int client = accept4(server, NULL, NULL, SOCK_CLOEXEC);
        if (client < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        struct timeval timeout = {.tv_sec = 2};
        if (setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0) {
            close(client);
            continue;
        }
        handle_client(client);
        close(client);
    }
    if (owns_path) {
        unlink(socket_path);
    }
    if (server_fd >= 0) close(server_fd);
    return 0;
}
