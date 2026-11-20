#include <napi/native_api.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/time.h>
#include <unistd.h>

#include <cstring>
#include <string>

namespace {
constexpr const char *DAEMON_HOST = "127.0.0.1";
constexpr int DAEMON_PORT = 9800;

int send_all(int fd, const std::string &data)
{
    size_t sent = 0;
    while (sent < data.size()) {
        ssize_t count = send(fd, data.data() + sent, data.size() - sent, 0);
        if (count <= 0) {
            return -1;
        }
        sent += static_cast<size_t>(count);
    }
    return 0;
}

std::string request_daemon(const std::string &command)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        return "ERR socket";
    }
    struct timeval timeout = {2, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(DAEMON_PORT);
    inet_pton(AF_INET, DAEMON_HOST, &address.sin_addr);
    if (connect(fd, reinterpret_cast<struct sockaddr *>(&address), sizeof(address)) != 0) {
        close(fd);
        return "ERR connect";
    }
    if (send_all(fd, command + "\n") != 0) {
        close(fd);
        return "ERR send";
    }
    std::string reply;
    char buffer[512];
    while (reply.find(".\n") == std::string::npos) {
        ssize_t count = recv(fd, buffer, sizeof(buffer), 0);
        if (count <= 0) {
            break;
        }
        reply.append(buffer, static_cast<size_t>(count));
    }
    close(fd);
    return reply;
}

napi_value Request(napi_env env, napi_callback_info info)
{
    size_t argc = 1;
    napi_value argv[1] = {nullptr};
    napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr);
    if (argc < 1) {
        napi_value error;
        napi_create_string_utf8(env, "ERR usage", NAPI_AUTO_LENGTH, &error);
        return error;
    }
    size_t length = 0;
    napi_get_value_string_utf8(env, argv[0], nullptr, 0, &length);
    std::string command(length, '\0');
    napi_get_value_string_utf8(env, argv[0], command.data(), length + 1, &length);
    std::string reply = request_daemon(command);
    napi_value result;
    napi_create_string_utf8(env, reply.c_str(), reply.size(), &result);
    return result;
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor properties[] = {
        {"request", nullptr, Request, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    napi_define_properties(env, exports, 1, properties);
    return exports;
}

napi_module module = {
    1,
    0,
    nullptr,
    Init,
    "pintool",
    nullptr,
    {0},
};
}

extern "C" __attribute__((constructor)) void RegisterPintoolModule()
{
    napi_module_register(&module);
}
