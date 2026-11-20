#define _GNU_SOURCE
#define GL_GLEXT_PROTOTYPES 1
#define EGL_EGLEXT_PROTOTYPES 1
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <gbm.h>

#include <dnn/hb_dnn.h>
#include <dnn/hb_sys.h>

#include "accel_wire.h"

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

static int gpu_compose_enabled(void)
{
    const char *value = getenv("RDKHM_GPU_COMPOSE");
    if (value != NULL && strcmp(value, "1") == 0) {
        return 1;
    }
    return access("/vendor/etc/rdkhm-gpu-compose.enable", F_OK) == 0;
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

static int wait_readable(int fd, long long deadline)
{
    for (;;) {
        int timeout = (int)(deadline - milliseconds());
        if (timeout <= 0) return -1;
        struct pollfd ready = {.fd = fd, .events = POLLIN};
        int result = poll(&ready, 1, timeout);
        if (result < 0 && errno == EINTR) continue;
        return result > 0 ? 0 : -1;
    }
}

static int recv_exact(int fd, void *buffer, size_t length, long long deadline)
{
    char *cursor = buffer;
    while (length > 0) {
        if (wait_readable(fd, deadline) < 0) return -1;
        ssize_t got = recv(fd, cursor, length, 0);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) return -1;
        cursor += got;
        length -= (size_t)got;
    }
    return 0;
}

static int send_exact(int fd, const void *buffer, size_t length)
{
    const char *cursor = buffer;
    while (length > 0) {
        ssize_t written = send(fd, cursor, length, MSG_NOSIGNAL);
        if (written < 0 && errno == EINTR && running) continue;
        if (written <= 0) return -1;
        cursor += written;
        length -= (size_t)written;
    }
    return 0;
}

static void reply(int client, const char *message)
{
    (void)send_exact(client, message, strlen(message));
}

/* ------------------------------------------------------------------ */
/* libdnn session layer                                               */

struct dnn_symbols {
    void *handle;
    int32_t (*release)(hbPackedDNNHandle_t);
    int32_t (*names)(char const ***, int32_t *, hbPackedDNNHandle_t);
    int32_t (*model)(hbDNNHandle_t *, hbPackedDNNHandle_t, char const *);
    int32_t (*input_count)(int32_t *, hbDNNHandle_t);
    int32_t (*output_count)(int32_t *, hbDNNHandle_t);
    int32_t (*input_props)(hbDNNTensorProperties *, hbDNNHandle_t, int32_t);
    int32_t (*output_props)(hbDNNTensorProperties *, hbDNNHandle_t, int32_t);
    int32_t (*infer)(hbDNNTaskHandle_t *, hbDNNTensor **, hbDNNTensor const *,
                     hbDNNHandle_t, hbDNNInferCtrlParam *);
    int32_t (*wait_task)(hbDNNTaskHandle_t, int32_t);
    int32_t (*release_task)(hbDNNTaskHandle_t);
    int32_t (*allocate)(hbSysMem *, uint32_t);
    int32_t (*free_mem)(hbSysMem *);
    int32_t (*flush_mem)(hbSysMem *, int32_t);
    int32_t (*write_mem)(hbSysMem *, char *, uint32_t);
    int32_t (*read_mem)(char *, hbSysMem *, uint32_t);
};

static struct dnn_symbols dnn;

static int dnn_load(void)
{
    if (dnn.handle != NULL) return 0;
    dnn.handle = dlopen("libdnn.so", RTLD_NOW | RTLD_LOCAL);
    if (dnn.handle == NULL) return -1;
#define LOAD_SYMBOL(field, symbol) do { \
        *(void **)(&dnn.field) = dlsym(dnn.handle, symbol); \
        if (dnn.field == NULL) goto fail; \
    } while (0)
    LOAD_SYMBOL(release, "hbDNNRelease");
    LOAD_SYMBOL(names, "hbDNNGetModelNameList");
    LOAD_SYMBOL(model, "hbDNNGetModelHandle");
    LOAD_SYMBOL(input_count, "hbDNNGetInputCount");
    LOAD_SYMBOL(output_count, "hbDNNGetOutputCount");
    LOAD_SYMBOL(input_props, "hbDNNGetInputTensorProperties");
    LOAD_SYMBOL(output_props, "hbDNNGetOutputTensorProperties");
    LOAD_SYMBOL(infer, "hbDNNInfer");
    LOAD_SYMBOL(wait_task, "hbDNNWaitTaskDone");
    LOAD_SYMBOL(release_task, "hbDNNReleaseTask");
    LOAD_SYMBOL(allocate, "hbSysAllocCachedMem");
    LOAD_SYMBOL(free_mem, "hbSysFreeMem");
    LOAD_SYMBOL(flush_mem, "hbSysFlushMem");
    LOAD_SYMBOL(write_mem, "hbSysWriteMem");
    LOAD_SYMBOL(read_mem, "hbSysReadMem");
#undef LOAD_SYMBOL
    return 0;
fail:
    dlclose(dnn.handle);
    memset(&dnn, 0, sizeof(dnn));
    return -1;
}

struct npu_session {
    int used;
    uint32_t id;
    hbPackedDNNHandle_t packed;
    hbDNNHandle_t model;
    void *model_data;
    int32_t input_count;
    int32_t output_count;
    hbDNNTensorProperties inputs[RDKHM_WIRE_MAX_TENSORS];
    hbDNNTensorProperties outputs[RDKHM_WIRE_MAX_TENSORS];
};

static struct npu_session sessions[4];
static uint32_t next_session = 1;

static struct npu_session *session_find(uint32_t id)
{
    for (size_t i = 0; i < sizeof(sessions) / sizeof(sessions[0]); i++) {
        if (sessions[i].used && sessions[i].id == id) return &sessions[i];
    }
    return NULL;
}

static void session_clear(struct npu_session *session)
{
    if (session->packed != NULL) dnn.release(session->packed);
    free(session->model_data);
    memset(session, 0, sizeof(*session));
}

static struct npu_session *session_alloc(void)
{
    for (size_t i = 0; i < sizeof(sessions) / sizeof(sessions[0]); i++) {
        if (!sessions[i].used) {
            memset(&sessions[i], 0, sizeof(sessions[i]));
            sessions[i].used = 1;
            sessions[i].id = next_session++;
            if (next_session == 0) next_session = 1;
            return &sessions[i];
        }
    }
    return NULL;
}

static void describe(const hbDNNTensorProperties *properties, struct rdkhm_io_desc *out)
{
    memset(out, 0, sizeof(*out));
    out->type = (uint32_t)properties->tensorType;
    out->format = (uint32_t)properties->tensorLayout;
    uint32_t rank = properties->validShape.numDimensions;
    if (rank > RDKHM_WIRE_MAX_DIMS) rank = RDKHM_WIRE_MAX_DIMS;
    out->rank = rank;
    for (uint32_t i = 0; i < rank; i++) {
        out->dims[i] = (uint32_t)properties->validShape.dimensionSize[i];
    }
    out->bytes = (uint32_t)properties->alignedByteSize;
}

static int read_fd(int fd, uint64_t offset, void *buffer, uint64_t length)
{
    char *cursor = buffer;
    while (length > 0) {
        ssize_t got = pread(fd, cursor, length, (off_t)offset);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) return -1;
        cursor += got;
        offset += (uint64_t)got;
        length -= (uint64_t)got;
    }
    return 0;
}

static int write_fd(int fd, uint64_t offset, const void *buffer, uint64_t length)
{
    const char *cursor = buffer;
    while (length > 0) {
        ssize_t written = pwrite(fd, cursor, length, (off_t)offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) return -1;
        cursor += written;
        offset += (uint64_t)written;
        length -= (uint64_t)written;
    }
    return 0;
}

static uint32_t npu_load(const unsigned char *payload, uint32_t length, int model_fd,
                         uint32_t *session_id)
{
    if (dnn_load() != 0) return RDKHM_STATUS_NOT_SUPPORT;
    void *data = NULL;
    if (model_fd >= 0) {
        struct stat info;
        if (fstat(model_fd, &info) < 0 || info.st_size <= 0 ||
            info.st_size > (off_t)RDKHM_WIRE_MAX_PAYLOAD) return RDKHM_STATUS_INVALID_MODEL;
        data = malloc((size_t)info.st_size);
        if (data == NULL) return RDKHM_STATUS_OUT_OF_MEMORY;
        if (read_fd(model_fd, 0, data, (uint64_t)info.st_size) < 0) {
            free(data);
            return RDKHM_STATUS_INVALID_MODEL;
        }
        length = (uint32_t)info.st_size;
    } else {
        if (payload == NULL || length == 0) return RDKHM_STATUS_INVALID_MODEL;
        data = malloc(length);
        if (data == NULL) return RDKHM_STATUS_OUT_OF_MEMORY;
        memcpy(data, payload, length);
    }
    struct npu_session *session = session_alloc();
    if (session == NULL) {
        free(data);
        return RDKHM_STATUS_DEVICE_BUSY;
    }
    session->model_data = data;
    const void *model_data[1] = {data};
    int32_t model_length[1] = {(int32_t)length};
    int32_t result = 0;
    {
        static int32_t (*initialize)(hbPackedDNNHandle_t *, const void **, int32_t *, int32_t);
        *(void **)(&initialize) = dlsym(dnn.handle, "hbDNNInitializeFromDDR");
        if (initialize == NULL) {
            session_clear(session);
            return RDKHM_STATUS_NOT_SUPPORT;
        }
        result = initialize(&session->packed, model_data, model_length, 1);
    }
    if (result != 0 || session->packed == NULL) {
        session_clear(session);
        return RDKHM_STATUS_INVALID_MODEL;
    }
    char const **names = NULL;
    int32_t count = 0;
    if (dnn.names(&names, &count, session->packed) != 0 || count < 1 || names == NULL ||
        dnn.model(&session->model, session->packed, names[0]) != 0 || session->model == NULL) {
        session_clear(session);
        return RDKHM_STATUS_INVALID_MODEL;
    }
    if (dnn.input_count(&session->input_count, session->model) != 0 ||
        dnn.output_count(&session->output_count, session->model) != 0 ||
        session->input_count < 0 || session->output_count < 0 ||
        session->input_count > (int32_t)RDKHM_WIRE_MAX_TENSORS ||
        session->output_count > (int32_t)RDKHM_WIRE_MAX_TENSORS) {
        session_clear(session);
        return RDKHM_STATUS_INVALID_MODEL;
    }
    for (int32_t i = 0; i < session->input_count; i++) {
        if (dnn.input_props(&session->inputs[i], session->model, i) != 0) {
            session_clear(session);
            return RDKHM_STATUS_INVALID_MODEL;
        }
    }
    for (int32_t i = 0; i < session->output_count; i++) {
        if (dnn.output_props(&session->outputs[i], session->model, i) != 0) {
            session_clear(session);
            return RDKHM_STATUS_INVALID_MODEL;
        }
    }
    *session_id = session->id;
    return RDKHM_STATUS_OK;
}

static uint32_t npu_info(uint32_t id, unsigned char **payload, uint32_t *length)
{
    struct npu_session *session = session_find(id);
    if (session == NULL) return RDKHM_STATUS_INVALID_MODEL;
    size_t count = (size_t)session->input_count + (size_t)session->output_count;
    *length = (uint32_t)(sizeof(struct rdkhm_io_response) + count * sizeof(struct rdkhm_io_desc));
    *payload = calloc(1, *length);
    if (*payload == NULL) return RDKHM_STATUS_OUT_OF_MEMORY;
    struct rdkhm_io_response *head = (struct rdkhm_io_response *)*payload;
    head->status = RDKHM_STATUS_OK;
    head->input_count = (uint32_t)session->input_count;
    head->output_count = (uint32_t)session->output_count;
    struct rdkhm_io_desc *desc = (struct rdkhm_io_desc *)(head + 1);
    for (int32_t i = 0; i < session->input_count; i++) describe(&session->inputs[i], &desc[i]);
    desc += session->input_count;
    for (int32_t i = 0; i < session->output_count; i++) describe(&session->outputs[i], &desc[i]);
    return RDKHM_STATUS_OK;
}

static uint32_t copy_in(int fd, uint64_t offset, uint64_t available, hbSysMem *mem, uint32_t size)
{
    void *staging = calloc(1, size);
    if (staging == NULL) return RDKHM_STATUS_OUT_OF_MEMORY;
    uint64_t copy = available < size ? available : size;
    if (copy > 0 && read_fd(fd, offset, staging, copy) < 0) {
        free(staging);
        return RDKHM_STATUS_INVALID_BUFFER;
    }
    int32_t result = dnn.write_mem(mem, (char *)staging, size);
    free(staging);
    if (result != 0) return RDKHM_STATUS_DEVICE_ERROR;
    dnn.flush_mem(mem, HB_SYS_MEM_CACHE_CLEAN);
    return RDKHM_STATUS_OK;
}

static uint32_t npu_run(uint32_t id, const unsigned char *payload, uint32_t length,
                        const int *fds, int fd_count,
                        unsigned char **response, uint32_t *response_length)
{
    struct npu_session *session = session_find(id);
    if (session == NULL) return RDKHM_STATUS_INVALID_MODEL;
    if (length < sizeof(struct rdkhm_run_request)) return RDKHM_STATUS_INVALID_PARAMETER;
    const unsigned char *cursor = payload;
    const struct rdkhm_run_request *request = (const struct rdkhm_run_request *)cursor;
    cursor += sizeof(*request);
    if (request->input_count != (uint32_t)session->input_count ||
        request->output_count != (uint32_t)session->output_count) {
        return RDKHM_STATUS_INVALID_INPUT;
    }
    size_t expected = sizeof(*request) +
        ((size_t)request->input_count + request->output_count) * sizeof(struct rdkhm_buffer_desc);
    if (length != expected) return RDKHM_STATUS_INVALID_PARAMETER;

    hbDNNTensor inputs[RDKHM_WIRE_MAX_TENSORS];
    hbDNNTensor outputs[RDKHM_WIRE_MAX_TENSORS];
    hbDNNTensor *output_ptrs[RDKHM_WIRE_MAX_TENSORS];
    hbSysMem output_mem[RDKHM_WIRE_MAX_TENSORS];
    memset(inputs, 0, sizeof(inputs));
    memset(outputs, 0, sizeof(outputs));
    memset(output_mem, 0, sizeof(output_mem));
    int32_t allocated = 0;
    uint32_t status = RDKHM_STATUS_OK;
    hbDNNTaskHandle_t task = NULL;

    for (uint32_t i = 0; i < request->input_count; i++) {
        const struct rdkhm_buffer_desc *desc = (const struct rdkhm_buffer_desc *)cursor;
        cursor += sizeof(*desc);
        if (desc->fd_index >= (uint32_t)fd_count) { status = RDKHM_STATUS_INVALID_BUFFER; goto done; }
        uint32_t size = (uint32_t)session->inputs[i].alignedByteSize;
        if (dnn.allocate(&inputs[i].sysMem[0], size) != 0) { status = RDKHM_STATUS_OUT_OF_MEMORY; goto done; }
        allocated |= (1u << i);
        inputs[i].properties = session->inputs[i];
        status = copy_in(fds[desc->fd_index], desc->offset, desc->bytes, &inputs[i].sysMem[0], size);
        if (status != RDKHM_STATUS_OK) goto done;
    }
    for (uint32_t i = 0; i < request->output_count; i++) {
        uint32_t size = (uint32_t)session->outputs[i].alignedByteSize;
        if (dnn.allocate(&output_mem[i], size) != 0) { status = RDKHM_STATUS_OUT_OF_MEMORY; goto done; }
        outputs[i].sysMem[0] = output_mem[i];
        outputs[i].properties = session->outputs[i];
        output_ptrs[i] = &outputs[i];
        allocated |= (1u << (request->input_count + i));
    }
    {
        hbDNNInferCtrlParam control;
        memset(&control, 0, sizeof(control));
        control.priority = 0;
        int32_t result = dnn.infer(&task, output_ptrs, inputs, session->model, &control);
        if (result != 0) { status = RDKHM_STATUS_DEVICE_ERROR; goto done; }
        result = dnn.wait_task(task, 10000);
        if (result != 0) { status = RDKHM_STATUS_TIME_OUT; goto done; }
    }
    cursor = payload + sizeof(*request) + (size_t)request->input_count * sizeof(struct rdkhm_buffer_desc);
    *response_length = (uint32_t)(sizeof(uint32_t) + sizeof(uint32_t) +
        (size_t)request->output_count * sizeof(struct rdkhm_run_output));
    *response = calloc(1, *response_length);
    if (*response == NULL) { status = RDKHM_STATUS_OUT_OF_MEMORY; goto done; }
    {
        uint32_t *head = (uint32_t *)*response;
        head[0] = RDKHM_STATUS_OK;
        head[1] = request->output_count;
        struct rdkhm_run_output *out = (struct rdkhm_run_output *)(head + 2);
        for (uint32_t i = 0; i < request->output_count; i++) {
            const struct rdkhm_buffer_desc *desc = (const struct rdkhm_buffer_desc *)cursor;
            cursor += sizeof(*desc);
            if (desc->fd_index >= (uint32_t)fd_count) { status = RDKHM_STATUS_INVALID_BUFFER; goto done; }
            uint32_t size = (uint32_t)session->outputs[i].alignedByteSize;
            dnn.flush_mem(&output_mem[i], HB_SYS_MEM_CACHE_INVALIDATE);
            void *staging = malloc(size);
            if (staging == NULL) { status = RDKHM_STATUS_OUT_OF_MEMORY; goto done; }
            if (dnn.read_mem(staging, &output_mem[i], size) != 0) {
                free(staging);
                status = RDKHM_STATUS_DEVICE_ERROR;
                goto done;
            }
            uint64_t copy = desc->bytes < size ? desc->bytes : size;
            int written = copy == 0 || write_fd(fds[desc->fd_index], desc->offset, staging, copy) == 0;
            free(staging);
            if (!written) { status = RDKHM_STATUS_INVALID_BUFFER; goto done; }
            uint32_t rank = session->outputs[i].validShape.numDimensions;
            if (rank > RDKHM_WIRE_MAX_DIMS) rank = RDKHM_WIRE_MAX_DIMS;
            out[i].rank = rank;
            for (uint32_t d = 0; d < rank; d++) {
                out[i].dims[d] = (uint32_t)session->outputs[i].validShape.dimensionSize[d];
            }
            out[i].bytes = (uint32_t)copy;
        }
    }
done:
    if (task != NULL) dnn.release_task(task);
    for (uint32_t i = 0; i < request->input_count && i < RDKHM_WIRE_MAX_TENSORS; i++) {
        if (allocated & (1u << i)) dnn.free_mem(&inputs[i].sysMem[0]);
    }
    for (uint32_t i = 0; i < request->output_count && i < RDKHM_WIRE_MAX_TENSORS; i++) {
        if (allocated & (1u << (request->input_count + i))) dnn.free_mem(&output_mem[i]);
    }
    return status;
}

/* ------------------------------------------------------------------ */
/* GPU composition                                                    */

struct gpu_state {
    int card_fd;
    struct gbm_device *gbm;
    EGLDisplay display;
    EGLContext context;
    EGLSurface surface;
    EGLConfig config;
    GLuint program;
    GLint uniform_tex;
    GLint uniform_alpha;
    int ready;
    int modifiers;
    int native_fence;
    int wait_sync;
};

static struct gpu_state gpu = {.card_fd = -1};

static GLuint gpu_compile(GLenum type, const char *source)
{
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint ok = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512] = {0};
        glGetShaderInfoLog(shader, sizeof(log), NULL, log);
        fprintf(stderr, "compose shader 0x%x: %s\n", type, log);
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

static int gpu_init(void)
{
    if (gpu.ready) return 0;
    const char *node = getenv("RDKHM_GPU_NODE");
    if (node == NULL || *node == '\0') node = "/dev/dri/card0";
    gpu.card_fd = open(node, O_RDWR | O_CLOEXEC);
    if (gpu.card_fd < 0) return -1;
    gpu.gbm = gbm_create_device(gpu.card_fd);
    if (gpu.gbm == NULL) goto fail;
    gpu.display = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gpu.gbm, NULL);
    if (gpu.display == EGL_NO_DISPLAY) goto fail;
    EGLint major = 0, minor = 0;
    if (!eglInitialize(gpu.display, &major, &minor)) goto fail;
    if (!eglBindAPI(EGL_OPENGL_ES_API)) goto fail;
    const char *extensions = eglQueryString(gpu.display, EGL_EXTENSIONS);
    gpu.modifiers = extensions != NULL &&
        strstr(extensions, "EGL_EXT_image_dma_buf_import_modifiers") != NULL;
    gpu.native_fence = extensions != NULL &&
        strstr(extensions, "EGL_ANDROID_native_fence_sync") != NULL;
    gpu.wait_sync = extensions != NULL && strstr(extensions, "EGL_KHR_wait_sync") != NULL;
    EGLint config_attrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                             EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE};
    EGLint count = 0;
    if (!eglChooseConfig(gpu.display, config_attrs, &gpu.config, 1, &count) || count < 1) goto fail;
    EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    gpu.context = eglCreateContext(gpu.display, gpu.config, EGL_NO_CONTEXT, context_attrs);
    if (gpu.context == EGL_NO_CONTEXT) goto fail;
    if (extensions != NULL && strstr(extensions, "EGL_KHR_surfaceless_context") != NULL) {
        if (!eglMakeCurrent(gpu.display, EGL_NO_SURFACE, EGL_NO_SURFACE, gpu.context)) goto fail;
    } else {
        EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
        gpu.surface = eglCreatePbufferSurface(gpu.display, gpu.config, surface_attrs);
        if (gpu.surface == EGL_NO_SURFACE ||
            !eglMakeCurrent(gpu.display, gpu.surface, gpu.surface, gpu.context)) goto fail;
    }
    const char *vertex_source =
        "attribute vec2 pos;\n"
        "attribute vec2 tex;\n"
        "varying vec2 v_tex;\n"
        "void main() { v_tex = tex; gl_Position = vec4(pos, 0.0, 1.0); }\n";
    const char *fragment_source =
        "precision mediump float;\n"
        "varying vec2 v_tex;\n"
        "uniform sampler2D tex;\n"
        "uniform float alpha;\n"
        "void main() { vec4 c = texture2D(tex, v_tex); gl_FragColor = vec4(c.rgb, c.a * alpha); }\n";
    GLuint vertex = gpu_compile(GL_VERTEX_SHADER, vertex_source);
    GLuint fragment = gpu_compile(GL_FRAGMENT_SHADER, fragment_source);
    if (vertex == 0 || fragment == 0) goto fail;
    gpu.program = glCreateProgram();
    glAttachShader(gpu.program, vertex);
    glAttachShader(gpu.program, fragment);
    glBindAttribLocation(gpu.program, 0, "pos");
    glBindAttribLocation(gpu.program, 1, "tex");
    glLinkProgram(gpu.program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    GLint linked = 0;
    glGetProgramiv(gpu.program, GL_LINK_STATUS, &linked);
    if (!linked) {
        char log[512] = {0};
        glGetProgramInfoLog(gpu.program, sizeof(log), NULL, log);
        fprintf(stderr, "compose program: %s\n", log);
        goto fail;
    }
    gpu.uniform_tex = glGetUniformLocation(gpu.program, "tex");
    gpu.uniform_alpha = glGetUniformLocation(gpu.program, "alpha");
    glUseProgram(gpu.program);
    glUniform1i(gpu.uniform_tex, 0);
    gpu.ready = 1;
    fprintf(stderr, "compose: %s EGL %d.%d modifiers=%d native_fence=%d wait_sync=%d\n",
            node, major, minor, gpu.modifiers, gpu.native_fence, gpu.wait_sync);
    return 0;
fail:
    if (gpu.program) glDeleteProgram(gpu.program);
    gpu.program = 0;
    if (gpu.context != EGL_NO_CONTEXT && gpu.display != EGL_NO_DISPLAY) {
        eglMakeCurrent(gpu.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (gpu.surface != EGL_NO_SURFACE) eglDestroySurface(gpu.display, gpu.surface);
        eglDestroyContext(gpu.display, gpu.context);
    }
    if (gpu.display != EGL_NO_DISPLAY) eglTerminate(gpu.display);
    if (gpu.gbm != NULL) gbm_device_destroy(gpu.gbm);
    if (gpu.card_fd >= 0) close(gpu.card_fd);
    memset(&gpu, 0, sizeof(gpu));
    gpu.card_fd = -1;
    return -1;
}

static int gpu_import(int fd, uint32_t format, uint32_t width, uint32_t height, uint32_t stride,
                      uint64_t modifier, EGLImageKHR *image, GLuint *texture)
{
    EGLint attrs[24];
    int n = 0;
    attrs[n++] = EGL_WIDTH;
    attrs[n++] = (EGLint)width;
    attrs[n++] = EGL_HEIGHT;
    attrs[n++] = (EGLint)height;
    attrs[n++] = EGL_LINUX_DRM_FOURCC_EXT;
    attrs[n++] = (EGLint)format;
    attrs[n++] = EGL_DMA_BUF_PLANE0_FD_EXT;
    attrs[n++] = fd;
    attrs[n++] = EGL_DMA_BUF_PLANE0_OFFSET_EXT;
    attrs[n++] = 0;
    attrs[n++] = EGL_DMA_BUF_PLANE0_PITCH_EXT;
    attrs[n++] = (EGLint)stride;
    if (modifier != 0) {
        if (!gpu.modifiers) return -1;
        attrs[n++] = EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT;
        attrs[n++] = (EGLint)(modifier & 0xffffffffu);
        attrs[n++] = EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT;
        attrs[n++] = (EGLint)(modifier >> 32);
    }
    attrs[n++] = EGL_NONE;
    EGLImageKHR imported = eglCreateImageKHR(gpu.display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT,
                                             NULL, attrs);
    if (imported == EGL_NO_IMAGE_KHR) return -1;
    GLuint tex = 0;
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glEGLImageTargetTexture2DOES(GL_TEXTURE_2D, (GLeglImageOES)imported);
    if (glGetError() != GL_NO_ERROR) {
        glDeleteTextures(1, &tex);
        eglDestroyImageKHR(gpu.display, imported);
        return -1;
    }
    *image = imported;
    *texture = tex;
    return 0;
}

static int gpu_wait_fence(int fd)
{
    if (fd < 0) return 0;
    int owned = dup(fd);
    if (owned < 0) return -1;
    EGLint attrs[] = {EGL_SYNC_NATIVE_FENCE_FD_ANDROID, owned, EGL_NONE};
    EGLSyncKHR sync = eglCreateSyncKHR(gpu.display, EGL_SYNC_NATIVE_FENCE_ANDROID, attrs);
    if (sync == EGL_NO_SYNC_KHR) {
        close(owned);
        return -1;
    }
    EGLint result = 0;
    if (gpu.wait_sync) {
        result = eglWaitSyncKHR(gpu.display, sync, 0) == EGL_TRUE ? 0 : -1;
    }
    if (result != 0) {
        result = eglClientWaitSyncKHR(gpu.display, sync, 0, 1000000000ull) ==
                 EGL_CONDITION_SATISFIED_KHR ? 0 : -1;
    }
    eglDestroySyncKHR(gpu.display, sync);
    if (result != 0) fprintf(stderr, "compose: input fence wait failed\n");
    return result;
}

static uint32_t gpu_compose(const unsigned char *payload, uint32_t length,
                            const int *fds, int fd_count, int *output_fd)
{
    *output_fd = -1;
    if (length < sizeof(struct rdkhm_compose_request)) return RDKHM_STATUS_INVALID_PARAMETER;
    const struct rdkhm_compose_request *request =
        (const struct rdkhm_compose_request *)payload;
    if (request->layer_count > RDKHM_WIRE_MAX_LAYERS ||
        request->target_width == 0 || request->target_height == 0 ||
        request->target_width > 4096 || request->target_height > 4096) {
        return RDKHM_STATUS_INVALID_PARAMETER;
    }
    size_t expected = sizeof(*request) +
        (size_t)request->layer_count * sizeof(struct rdkhm_compose_layer);
    if (length != expected) return RDKHM_STATUS_INVALID_PARAMETER;
    if (request->target_fd_index >= (uint32_t)fd_count) return RDKHM_STATUS_INVALID_BUFFER;
    if (gpu_init() != 0) return RDKHM_STATUS_NOT_SUPPORT;

    long long started = milliseconds();
    EGLImageKHR target_image = EGL_NO_IMAGE_KHR;
    GLuint target_texture = 0;
    GLuint framebuffer = 0;
    EGLImageKHR images[RDKHM_WIRE_MAX_LAYERS] = {0};
    GLuint textures[RDKHM_WIRE_MAX_LAYERS] = {0};
    GLuint image_count = 0;
    uint32_t status = RDKHM_STATUS_OK;
    if (request->target_fence_fd_index < (uint32_t)fd_count &&
        gpu_wait_fence(fds[request->target_fence_fd_index]) != 0) {
        return RDKHM_STATUS_TIME_OUT;
    }
    if (gpu_import(fds[request->target_fd_index], request->target_format,
                   request->target_width, request->target_height, request->target_stride,
                   request->target_modifier, &target_image, &target_texture) != 0) {
        return RDKHM_STATUS_NOT_SUPPORT;
    }
    glGenFramebuffers(1, &framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                           target_texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        status = RDKHM_STATUS_INVALID_BUFFER;
        goto done;
    }
    glViewport(0, 0, (GLsizei)request->target_width, (GLsizei)request->target_height);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(gpu.program);
    const unsigned char *cursor = payload + sizeof(*request);
    for (uint32_t i = 0; i < request->layer_count; i++) {
        const struct rdkhm_compose_layer *layer =
            (const struct rdkhm_compose_layer *)cursor;
        cursor += sizeof(*layer);
        if (layer->fd_index >= (uint32_t)fd_count ||
            layer->transform != 0 || layer->width == 0 || layer->height == 0 ||
            layer->crop_x + layer->crop_w > layer->width ||
            layer->crop_y + layer->crop_h > layer->height ||
            layer->dst_w == 0 || layer->dst_h == 0) {
            status = RDKHM_STATUS_INVALID_PARAMETER;
            goto done;
        }
        if (layer->fence_fd_index < (uint32_t)fd_count &&
            gpu_wait_fence(fds[layer->fence_fd_index]) != 0) {
            status = RDKHM_STATUS_TIME_OUT;
            goto done;
        }
        if (gpu_import(fds[layer->fd_index], layer->format, layer->width, layer->height,
                       layer->stride, layer->modifier, &images[image_count],
                       &textures[image_count]) != 0) {
            status = RDKHM_STATUS_INVALID_BUFFER;
            goto done;
        }
        float left = (float)layer->dst_x / (float)request->target_width * 2.0f - 1.0f;
        float right = (float)(layer->dst_x + (int32_t)layer->dst_w) /
                      (float)request->target_width * 2.0f - 1.0f;
        float top = 1.0f - (float)layer->dst_y / (float)request->target_height * 2.0f;
        float bottom = 1.0f - (float)(layer->dst_y + (int32_t)layer->dst_h) /
                       (float)request->target_height * 2.0f;
        float u0 = (float)layer->crop_x / (float)layer->width;
        float u1 = (float)(layer->crop_x + layer->crop_w) / (float)layer->width;
        float v0 = (float)layer->crop_y / (float)layer->height;
        float v1 = (float)(layer->crop_y + layer->crop_h) / (float)layer->height;
        GLfloat vertices[] = {
            left, bottom, u0, v0,
            right, bottom, u1, v0,
            left, top, u0, v1,
            right, top, u1, v1,
        };
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, textures[image_count]);
        glUniform1f(gpu.uniform_alpha, (float)layer->alpha / 255.0f);
        if (layer->blend != 0 || layer->alpha < 255) {
            glEnable(GL_BLEND);
            glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                                GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
        } else {
            glDisable(GL_BLEND);
        }
        glEnableVertexAttribArray(0);
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), vertices);
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), vertices + 2);
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
        image_count++;
    }
    if (gpu.native_fence) {
        EGLint attrs[] = {EGL_SYNC_NATIVE_FENCE_FD_ANDROID,
                          EGL_NO_NATIVE_FENCE_FD_ANDROID, EGL_NONE};
        EGLSyncKHR sync = eglCreateSyncKHR(gpu.display, EGL_SYNC_NATIVE_FENCE_ANDROID, attrs);
        if (sync == EGL_NO_SYNC_KHR) {
            status = RDKHM_STATUS_DEVICE_ERROR;
            goto done;
        }
        *output_fd = eglDupNativeFenceFDANDROID(gpu.display, sync);
        eglDestroySyncKHR(gpu.display, sync);
        if (*output_fd < 0) status = RDKHM_STATUS_DEVICE_ERROR;
    } else {
        glFinish();
    }
    if (status == RDKHM_STATUS_OK) {
        fprintf(stderr, "compose: %ux%u layers=%u elapsed=%lldms fence_fd=%d\n",
                request->target_width, request->target_height, request->layer_count,
                milliseconds() - started, *output_fd);
    }
done:
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    if (framebuffer) glDeleteFramebuffers(1, &framebuffer);
    for (uint32_t i = 0; i < image_count; i++) {
        glDeleteTextures(1, &textures[i]);
        eglDestroyImageKHR(gpu.display, images[i]);
    }
    if (target_texture) glDeleteTextures(1, &target_texture);
    if (target_image != EGL_NO_IMAGE_KHR) eglDestroyImageKHR(gpu.display, target_image);
    return status;
}

/* ------------------------------------------------------------------ */
/* wire framing                                                       */

static int peek_binary(int client, long long deadline)
{
    unsigned char magic[4];
    size_t got = 0;
    while (got < sizeof(magic)) {
        if (wait_readable(client, deadline) < 0) return -1;
        ssize_t length = recv(client, magic + got, sizeof(magic) - got, MSG_PEEK);
        if (length < 0 && errno == EINTR) continue;
        if (length <= 0) return -1;
        got += (size_t)length;
    }
    return memcmp(magic, "RDK1", 4) == 0 ? 1 : 0;
}

static int recv_frame(int client, struct rdkhm_wire_header *header,
                      unsigned char **payload, int *fds, int *fd_count,
                      long long deadline)
{
    *payload = NULL;
    *fd_count = 0;
    if (wait_readable(client, deadline) < 0) return -1;
    struct iovec iov = {.iov_base = header, .iov_len = sizeof(*header)};
    char control[CMSG_SPACE(sizeof(int) * RDKHM_WIRE_MAX_FDS)];
    struct msghdr message = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control,
        .msg_controllen = sizeof(control),
    };
    ssize_t got = recvmsg(client, &message, MSG_CMSG_CLOEXEC);
    if (got < 0 && errno == EINTR) return recv_frame(client, header, payload, fds, fd_count, deadline);
    if (got <= 0) return -1;
    for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message); cmsg != NULL; cmsg = CMSG_NXTHDR(&message, cmsg)) {
        if (cmsg->cmsg_level != SOL_SOCKET || cmsg->cmsg_type != SCM_RIGHTS) continue;
        size_t count = (cmsg->cmsg_len - CMSG_LEN(0)) / sizeof(int);
        int *received = (int *)CMSG_DATA(cmsg);
        for (size_t i = 0; i < count && *fd_count < (int)RDKHM_WIRE_MAX_FDS; i++) {
            fds[(*fd_count)++] = received[i];
        }
        for (size_t i = RDKHM_WIRE_MAX_FDS; i < count; i++) close(received[i]);
    }
    if ((size_t)got < sizeof(*header) &&
        recv_exact(client, (char *)header + got, sizeof(*header) - (size_t)got, deadline) < 0) {
        return -1;
    }
    if (header->magic != RDKHM_WIRE_MAGIC || header->version != RDKHM_WIRE_VERSION ||
        header->payload > RDKHM_WIRE_MAX_PAYLOAD || header->fds != (uint16_t)*fd_count) {
        return -1;
    }
    if (header->fds > RDKHM_WIRE_MAX_FDS) return -1;
    if (header->payload > 0) {
        *payload = malloc(header->payload);
        if (*payload == NULL) return -1;
        if (recv_exact(client, *payload, header->payload, deadline) < 0) {
            free(*payload);
            *payload = NULL;
            return -1;
        }
    }
    return 0;
}

static int send_frame(int client, uint16_t command, uint32_t session,
                      const void *payload, uint32_t length)
{
    struct rdkhm_wire_header header;
    memset(&header, 0, sizeof(header));
    header.magic = RDKHM_WIRE_MAGIC;
    header.version = RDKHM_WIRE_VERSION;
    header.command = command;
    header.session = session;
    header.payload = length;
    if (send_exact(client, &header, sizeof(header)) < 0) return -1;
    if (length > 0 && send_exact(client, payload, length) < 0) return -1;
    return 0;
}

static int send_status(int client, uint16_t command, uint32_t session, uint32_t status)
{
    return send_frame(client, command, session, &status, sizeof(status));
}

static int send_frame_fds(int client, uint16_t command, uint32_t session,
                          const void *payload, uint32_t length, const int *fds, int fd_count)
{
    struct rdkhm_wire_header header;
    memset(&header, 0, sizeof(header));
    header.magic = RDKHM_WIRE_MAGIC;
    header.version = RDKHM_WIRE_VERSION;
    header.command = command;
    header.session = session;
    header.payload = length;
    header.fds = (uint16_t)fd_count;
    struct iovec iov = {.iov_base = &header, .iov_len = sizeof(header)};
    char control[CMSG_SPACE(sizeof(int) * RDKHM_WIRE_MAX_FDS)];
    struct msghdr message = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control,
        .msg_controllen = CMSG_SPACE(sizeof(int) * (size_t)fd_count),
    };
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(int) * (size_t)fd_count);
    memcpy(CMSG_DATA(cmsg), fds, sizeof(int) * (size_t)fd_count);
    if (sendmsg(client, &message, MSG_NOSIGNAL) < 0) return -1;
    if (length > 0 && send_exact(client, payload, length) < 0) return -1;
    return 0;
}

static void handle_binary(int client)
{
    long long deadline = milliseconds() + 10000;
    struct rdkhm_wire_header header;
    unsigned char *payload = NULL;
    int fds[RDKHM_WIRE_MAX_FDS];
    int fd_count = 0;
    if (recv_frame(client, &header, &payload, fds, &fd_count, deadline) < 0) {
        for (int i = 0; i < fd_count; i++) close(fds[i]);
        free(payload);
        return;
    }
    uint32_t status = RDKHM_STATUS_INVALID_PARAMETER;
    unsigned char *response = NULL;
    uint32_t response_length = 0;
    int response_fd = -1;
    uint32_t session = header.session;
    switch (header.command) {
        case RDKHM_WIRE_HELLO:
            status = dnn_load() ? RDKHM_STATUS_NOT_SUPPORT : RDKHM_STATUS_OK;
            break;
        case RDKHM_WIRE_LOAD: {
            int model_fd = -1;
            const unsigned char *model = payload;
            uint32_t length = header.payload;
            uint32_t new_session = 0;
            if (fd_count == 1) {
                model_fd = fds[0];
                model = NULL;
                length = 0;
            } else if (header.payload >= sizeof(struct rdkhm_load_request)) {
                const struct rdkhm_load_request *request =
                    (const struct rdkhm_load_request *)payload;
                length = request->model_bytes;
                model = payload + sizeof(*request);
                if ((size_t)length + sizeof(*request) != header.payload) {
                    status = RDKHM_STATUS_INVALID_PARAMETER;
                    break;
                }
            }
            status = npu_load(model, length, model_fd, &new_session);
            if (status == RDKHM_STATUS_OK) session = new_session;
            break;
        }
        case RDKHM_WIRE_INFO:
            status = npu_info(session, &response, &response_length);
            break;
        case RDKHM_WIRE_RUN:
            status = npu_run(session, payload, header.payload, fds, fd_count,
                             &response, &response_length);
            break;
        case RDKHM_WIRE_RELEASE: {
            struct npu_session *found = session_find(session);
            if (found == NULL) status = RDKHM_STATUS_INVALID_MODEL;
            else { session_clear(found); status = RDKHM_STATUS_OK; }
            break;
        }
        case RDKHM_WIRE_COMPOSE: {
            if (header.payload < sizeof(struct rdkhm_compose_request)) {
                status = RDKHM_STATUS_INVALID_PARAMETER;
                break;
            }
            if (!gpu_compose_enabled()) {
                status = RDKHM_STATUS_NOT_SUPPORT;
                break;
            }
            const struct rdkhm_compose_request *request =
                (const struct rdkhm_compose_request *)payload;
            long long compose_start = milliseconds();
            status = gpu_compose(payload, header.payload, fds, fd_count, &response_fd);
            if (status == RDKHM_STATUS_OK) {
                response_length = (uint32_t)sizeof(struct rdkhm_compose_response);
                response = calloc(1, response_length);
                if (response == NULL) {
                    status = RDKHM_STATUS_OUT_OF_MEMORY;
                    break;
                }
                struct rdkhm_compose_response *out =
                    (struct rdkhm_compose_response *)response;
                out->status = RDKHM_STATUS_OK;
                out->elapsed_ms = (uint32_t)(milliseconds() - compose_start);
                out->layers = request->layer_count;
            }
            break;
        }
        default:
            status = RDKHM_STATUS_NOT_SUPPORT;
            break;
    }
    for (int i = 0; i < fd_count; i++) close(fds[i]);
    free(payload);
    if (response != NULL && status == RDKHM_STATUS_OK) {
        if (response_fd >= 0) {
            (void)send_frame_fds(client, header.command, session, response, response_length,
                                 &response_fd, 1);
        } else {
            (void)send_frame(client, header.command, session, response, response_length);
        }
    } else {
        (void)send_status(client, header.command, session, status);
    }
    if (response_fd >= 0) close(response_fd);
    free(response);
}

/* ------------------------------------------------------------------ */
/* text probes                                                        */

static void drain_pending_line(int client)
{
    char discard[64];
    for (;;) {
        ssize_t length = recv(client, discard, sizeof(discard), MSG_DONTWAIT);
        if (length <= 0) return;
        if (memchr(discard, '\n', (size_t)length) != NULL) return;
    }
}

static void handle_text(int client)
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
            drain_pending_line(client);
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
    if (strcmp(command, "GPU_COMPOSE_CHECK") == 0) {
        reply(client, gpu_compose_enabled() ? "GPU_COMPOSE_READY\n" : "GPU_COMPOSE_UNAVAILABLE\n");
        return;
    }
    if (strcmp(command, "GPU_CHECK") == 0) {
        int egl = load_library("libEGL.so.1");
        int gles = load_library("libGLESv2.so.2");
        reply(client, egl == 0 && gles == 0 ? "GPU_RUNTIME_READY\n" : "GPU_RUNTIME_UNAVAILABLE\n");
        return;
    }
    if (strcmp(command, "NPU_CHECK") == 0) {
        reply(client, dnn_load() == 0 ? "NPU_RUNTIME_READY\n" : "NPU_RUNTIME_UNAVAILABLE\n");
        return;
    }
    if (strcmp(command, "NNRT_BACKEND") == 0) {
        /* This is a runtime/library capability probe, not a claim of NNRT
         * backend registration or successful hardware inference. */
        reply(client, dnn_load() == 0 ?
            "NNRT_BACKEND_RUNTIME_READY\n" : "NNRT_BACKEND_UNAVAILABLE\n");
        return;
    }
    reply(client, "ERROR unsupported-command\n");
}

static void handle_client(int client)
{
    /* Keep the connection for compositor clients. Text probes and one-shot
     * clients still work because EOF/timeouts terminate the loop. */
    while (running) {
        int binary = peek_binary(client, milliseconds() + 2000);
        if (binary < 0) {
            (void)reply(client, "ERROR timeout\n");
            return;
        }
        if (binary) handle_binary(client);
        else handle_text(client);
    }
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
        struct timeval timeout = {.tv_sec = 10};
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
