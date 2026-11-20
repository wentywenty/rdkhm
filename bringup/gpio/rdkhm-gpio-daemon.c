#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

#define DEFAULT_SOCKET "/dev/rdkhm-gpio.sock"
#define DEFAULT_TOOL "/rdkhm/gpio"
#define DEFAULT_TCP_PORT 9800
#define MAX_TOKENS 8
#define MAX_LINE 512
#define MAX_OUTPUT 8192

static const char *socket_path(void)
{
    const char *override = getenv("RDKHM_GPIO_SOCKET");

    return (override != NULL && override[0] != '\0') ? override : DEFAULT_SOCKET;
}

static unsigned short tcp_port(void)
{
    const char *override = getenv("RDKHM_GPIO_TCP_PORT");

    if (override != NULL && override[0] != '\0') {
        long value = strtol(override, NULL, 10);
        if (value > 0 && value < 65536) {
            return (unsigned short)value;
        }
    }
    return DEFAULT_TCP_PORT;
}

static const char *tool_path(void)
{
    const char *override = getenv("RDKHM_GPIO_TOOL");

    return (override != NULL && override[0] != '\0') ? override : DEFAULT_TOOL;
}

static void send_text(int fd, const char *text)
{
    size_t left = strlen(text);

    while (left > 0) {
        ssize_t written = write(fd, text, left);

        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            return;
        }
        if (written == 0) {
            return;
        }
        text += written;
        left -= (size_t)written;
    }
}

static int run_tool(char *const argv[], char *output, size_t capacity)
{
    int pipefd[2];
    pid_t child;
    ssize_t count;
    size_t used = 0;
    int status;

    if (pipe(pipefd) != 0) {
        snprintf(output, capacity, "pipe: %s\n", strerror(errno));
        return 1;
    }
    child = fork();
    if (child < 0) {
        snprintf(output, capacity, "fork: %s\n", strerror(errno));
        close(pipefd[0]);
        close(pipefd[1]);
        return 1;
    }
    if (child == 0) {
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[0]);
        close(pipefd[1]);
        execv(argv[0], argv);
        _exit(127);
    }
    close(pipefd[1]);
    while (used + 1 < capacity) {
        count = read(pipefd[0], output + used, capacity - used - 1);
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        if (count == 0) {
            break;
        }
        used += (size_t)count;
    }
    output[used] = '\0';
    close(pipefd[0]);
    if (waitpid(child, &status, 0) < 0) {
        return 1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

static int allowed_command(const char *command)
{
    static const char *const allowed[] = {
        "list", "show", "export", "unexport", "get", "set", "dir",
    };
    size_t index;

    for (index = 0; index < sizeof(allowed) / sizeof(allowed[0]); index++) {
        if (strcmp(command, allowed[index]) == 0) {
            return 1;
        }
    }
    return 0;
}

static int validate_pin(const char *text)
{
    char *end = NULL;
    long value = strtol(text, &end, 10);

    return end != NULL && *end == '\0' && value >= 1 && value <= 40;
}

static int handle_request(int client)
{
    char line[MAX_LINE];
    char output[MAX_OUTPUT];
    char *tokens[MAX_TOKENS];
    char *arguments[MAX_TOKENS + 2];
    char *save = NULL;
    char *token;
    size_t count = 0;
    ssize_t length;
    size_t index;
    int exit_code;

    length = read(client, line, sizeof(line) - 1);
    if (length <= 0) {
        return 0;
    }
    line[length] = '\0';
    while (length > 0 && (line[length - 1] == '\n' || line[length - 1] == '\r')) {
        line[--length] = '\0';
    }
    if (strcmp(line, "ping") == 0) {
        snprintf(output, sizeof(output), "OK\nPONG\n.\n");
        send_text(client, output);
        return 1;
    }
    if (strcmp(line, "quit") == 0) {
        return 0;
    }
    token = strtok_r(line, " \t", &save);
    while (token != NULL && count < MAX_TOKENS) {
        if (token[0] == '-') {
            snprintf(output, sizeof(output), "ERR 2\ninvalid token\n.\n");
            send_text(client, output);
            return 1;
        }
        tokens[count++] = token;
        token = strtok_r(NULL, " \t", &save);
    }
    if (count == 0 || !allowed_command(tokens[0])) {
        snprintf(output, sizeof(output), "ERR 2\nunknown command\n.\n");
        send_text(client, output);
        return 1;
    }
    if (strcmp(tokens[0], "list") == 0) {
        if (count != 1) {
            snprintf(output, sizeof(output), "ERR 2\nlist takes no arguments\n.\n");
            send_text(client, output);
            return 1;
        }
    } else {
        if (count < 2 || !validate_pin(tokens[1])) {
            snprintf(output, sizeof(output), "ERR 2\npin must be 1..40\n.\n");
            send_text(client, output);
            return 1;
        }
    }
    arguments[0] = (char *)tool_path();
    for (index = 0; index < count; index++) {
        arguments[index + 1] = tokens[index];
    }
    arguments[count + 1] = NULL;

    output[0] = '\0';
    exit_code = run_tool(arguments, output, sizeof(output));
    if (exit_code == 0) {
        snprintf(line, sizeof(line), "OK\n");
    } else {
        snprintf(line, sizeof(line), "ERR %d\n", exit_code);
    }
    send_text(client, line);
    if (output[0] != '\0') {
        send_text(client, output);
        if (output[strlen(output) - 1] != '\n') {
            send_text(client, "\n");
        }
    }
    send_text(client, ".\n");
    return 1;
}

static int peer_allowed(int client)
{
    struct ucred cred;
    socklen_t length = sizeof(cred);
    const char *allowed_uid = getenv("RDKHM_GPIO_ALLOWED_UID");
    const char *allowed_gid = getenv("RDKHM_GPIO_ALLOWED_GID");

    if (getsockopt(client, SOL_SOCKET, SO_PEERCRED, &cred, &length) != 0) {
        fprintf(stderr, "SO_PEERCRED failed: %s\n", strerror(errno));
        return 0;
    }
    if (cred.uid == 0 || cred.gid == 0) {
        return 1;
    }
    if (allowed_uid != NULL && allowed_uid[0] != '\0' &&
        cred.uid == (uid_t)strtoul(allowed_uid, NULL, 10)) {
        return 1;
    }
    if (allowed_gid != NULL && allowed_gid[0] != '\0' &&
        cred.gid == (gid_t)strtoul(allowed_gid, NULL, 10)) {
        return 1;
    }
    return 0;
}

static int accept_client(int server, int is_tcp)
{
    int client = accept(server, NULL, NULL);
    pid_t child;

    if (client < 0) {
        return -1;
    }
    if (!is_tcp && !peer_allowed(client)) {
        send_text(client, "ERR 13\npermission denied\n.\n");
        close(client);
        return 0;
    }
    child = fork();
    if (child < 0) {
        close(client);
        return -1;
    }
    if (child == 0) {
        signal(SIGCHLD, SIG_DFL);
        while (handle_request(client)) {
        }
        close(client);
        _exit(0);
    }
    close(client);
    return 0;
}

static int serve(int unix_server, int tcp_server)
{
    struct pollfd fds[2];
    nfds_t count = 0;

    signal(SIGCHLD, SIG_IGN);
    if (unix_server >= 0) {
        fds[count].fd = unix_server;
        fds[count].events = POLLIN;
        count++;
    }
    if (tcp_server >= 0) {
        fds[count].fd = tcp_server;
        fds[count].events = POLLIN;
        count++;
    }
    for (;;) {
        int ready = poll(fds, count, -1);
        nfds_t index;

        if (ready < 0) {
            if (errno == EINTR) {
                continue;
            }
            return 1;
        }
        for (index = 0; index < count; index++) {
            if ((fds[index].revents & POLLIN) != 0) {
                accept_client(fds[index].fd, fds[index].fd == tcp_server);
            }
        }
    }
}

static int listen_on(const char *path, mode_t mode)
{
    struct sockaddr_un address;
    int server;

    if (strlen(path) >= sizeof(address.sun_path)) {
        fprintf(stderr, "socket path too long: %s\n", path);
        return -1;
    }
    server = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server < 0) {
        fprintf(stderr, "socket: %s\n", strerror(errno));
        return -1;
    }
    unlink(path);
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    snprintf(address.sun_path, sizeof(address.sun_path), "%s", path);
    if (bind(server, (struct sockaddr *)&address, sizeof(address)) != 0) {
        fprintf(stderr, "bind %s: %s\n", path, strerror(errno));
        close(server);
        return -1;
    }
    chmod(path, mode);
    if (listen(server, 8) != 0) {
        fprintf(stderr, "listen %s: %s\n", path, strerror(errno));
        close(server);
        return -1;
    }
    return server;
}

static int listen_tcp(unsigned short port)
{
    struct sockaddr_in address;
    int option = 1;
    int server = socket(AF_INET, SOCK_STREAM, 0);

    if (server < 0) {
        return -1;
    }
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &option, sizeof(option));
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(server, (struct sockaddr *)&address, sizeof(address)) != 0) {
        close(server);
        return -1;
    }
    if (listen(server, 8) != 0) {
        close(server);
        return -1;
    }
    return server;
}

int main(int argc, char **argv)
{
    int foreground = 0;
    int tcp_enabled = 0;
    int unix_server;
    int tcp_server;
    int index;
    mode_t socket_mode = 0660;
    const char *tcp_env = getenv("RDKHM_GPIO_TCP_ENABLE");

    if (tcp_env != NULL && strcmp(tcp_env, "1") == 0) {
        tcp_enabled = 1;
    }
    for (index = 1; index < argc; index++) {
        if (strcmp(argv[index], "-f") == 0) {
            foreground = 1;
        } else if (strcmp(argv[index], "-t") == 0) {
            tcp_enabled = 1;
        } else if (strcmp(argv[index], "-m") == 0 && index + 1 < argc) {
            socket_mode = (mode_t)strtol(argv[++index], NULL, 8);
        }
    }
    signal(SIGPIPE, SIG_IGN);
    if (!foreground) {
        pid_t child = fork();

        if (child < 0) {
            fprintf(stderr, "fork: %s\n", strerror(errno));
            return 1;
        }
        if (child > 0) {
            return 0;
        }
        setsid();
        umask(0077);
    }
    unix_server = listen_on(socket_path(), socket_mode);
    tcp_server = tcp_enabled ? listen_tcp(tcp_port()) : -1;
    if (unix_server < 0 && tcp_server < 0) {
        return 1;
    }
    return serve(unix_server, tcp_server);
}
