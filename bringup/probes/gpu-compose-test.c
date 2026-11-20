#define GL_GLEXT_PROTOTYPES 1
#define EGL_EGLEXT_PROTOTYPES 1
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <gbm.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

struct buffer {
    struct gbm_bo *bo;
    int fd;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t format;
    uint64_t modifier;
};

static double ms_since(const struct timespec *start)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - start->tv_sec) * 1000.0 + (now.tv_nsec - start->tv_nsec) / 1e6;
}

static int buffer_create(struct gbm_device *gbm, struct buffer *buffer, uint32_t width,
                         uint32_t height)
{
    memset(buffer, 0, sizeof(*buffer));
    buffer->bo = gbm_bo_create(gbm, width, height, GBM_FORMAT_ARGB8888,
                               GBM_BO_USE_RENDERING | GBM_BO_USE_LINEAR);
    if (buffer->bo == NULL) {
        fprintf(stderr, "gbm_bo_create(%ux%u) failed\n", width, height);
        return -1;
    }
    buffer->fd = gbm_bo_get_fd(buffer->bo);
    buffer->width = width;
    buffer->height = height;
    buffer->stride = gbm_bo_get_stride(buffer->bo);
    buffer->format = gbm_bo_get_format(buffer->bo);
    buffer->modifier = gbm_bo_get_modifier(buffer->bo);
    if (buffer->fd < 0) {
        fprintf(stderr, "gbm_bo_get_fd failed\n");
        return -1;
    }
    printf("buffer %ux%u fd=%d stride=%u format=0x%x modifier=0x%llx\n", width, height,
           buffer->fd, buffer->stride, buffer->format, (unsigned long long)buffer->modifier);
    return 0;
}

static void buffer_destroy(struct buffer *buffer)
{
    if (buffer->fd >= 0) close(buffer->fd);
    if (buffer->bo != NULL) gbm_bo_destroy(buffer->bo);
}

static int buffer_fill(struct buffer *buffer, int foreground)
{
    uint32_t stride = 0;
    void *map_data = NULL;
    uint8_t *map = gbm_bo_map(buffer->bo, 0, 0, buffer->width, buffer->height,
                              GBM_BO_TRANSFER_WRITE, &stride, &map_data);
    if (map == NULL) {
        fprintf(stderr, "gbm_bo_map(write) failed\n");
        return -1;
    }
    for (uint32_t y = 0; y < buffer->height; y++) {
        uint32_t *row = (uint32_t *)(map + y * stride);
        for (uint32_t x = 0; x < buffer->width; x++) {
            if (foreground) {
                row[x] = 0x80ff0000u;
            } else {
                row[x] = x < buffer->width / 2 ? 0xff00ff00u : 0xff0000ffu;
            }
        }
    }
    gbm_bo_unmap(buffer->bo, map_data);
    return 0;
}

static EGLImageKHR image_import(EGLDisplay display, PFNEGLCREATEIMAGEKHRPROC create_image,
                                int modifiers, const struct buffer *buffer)
{
    EGLint attrs[24];
    int n = 0;
    attrs[n++] = EGL_WIDTH;
    attrs[n++] = (EGLint)buffer->width;
    attrs[n++] = EGL_HEIGHT;
    attrs[n++] = (EGLint)buffer->height;
    attrs[n++] = EGL_LINUX_DRM_FOURCC_EXT;
    attrs[n++] = (EGLint)buffer->format;
    attrs[n++] = EGL_DMA_BUF_PLANE0_FD_EXT;
    attrs[n++] = buffer->fd;
    attrs[n++] = EGL_DMA_BUF_PLANE0_OFFSET_EXT;
    attrs[n++] = 0;
    attrs[n++] = EGL_DMA_BUF_PLANE0_PITCH_EXT;
    attrs[n++] = (EGLint)buffer->stride;
    if (buffer->modifier != 0) {
        if (!modifiers) {
            fprintf(stderr, "non-linear buffer without dma-buf modifier support\n");
            return EGL_NO_IMAGE_KHR;
        }
        attrs[n++] = EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT;
        attrs[n++] = (EGLint)(buffer->modifier & 0xffffffffu);
        attrs[n++] = EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT;
        attrs[n++] = (EGLint)(buffer->modifier >> 32);
    }
    attrs[n++] = EGL_NONE;
    return create_image(display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, attrs);
}

static GLuint image_texture(EGLImageKHR image)
{
    GLuint texture = 0;
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glEGLImageTargetTexture2DOES(GL_TEXTURE_2D, (GLeglImageOES)image);
    return texture;
}

static GLuint compile_shader(GLenum type, const char *source)
{
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint ok = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512] = {0};
        glGetShaderInfoLog(shader, sizeof(log), NULL, log);
        fprintf(stderr, "shader 0x%x failed: %s\n", type, log);
        return 0;
    }
    return shader;
}

static int pixel_close(const unsigned char *pixel, uint32_t expected, int tolerance)
{
    int r = (expected >> 16) & 0xff;
    int g = (expected >> 8) & 0xff;
    int b = expected & 0xff;
    int a = (expected >> 24) & 0xff;
    return abs(pixel[0] - r) <= tolerance && abs(pixel[1] - g) <= tolerance &&
           abs(pixel[2] - b) <= tolerance && abs(pixel[3] - a) <= tolerance;
}

int main(int argc, char **argv)
{
    const char *allow = getenv("RDKHM_GPU_COMPOSE_TEST");

    /* This probe imports dma-bufs directly, bypassing the daemon's COMPOSE
     * switch. Refuse by default so a stale/broken kernel cannot be crashed by
     * an accidental invocation. */
    if (allow == NULL || strcmp(allow, "1") != 0) {
        fprintf(stderr,
                "gpu-compose-test: refusing direct dma-buf import.\n"
                "This bypasses the accelerator daemon and requires a kernel with "
                "the dmabuf sg_table fix.\n"
                "Set RDKHM_GPU_COMPOSE_TEST=1 to acknowledge and run.\n");
        return 2;
    }

    const char *node = argc > 1 ? argv[1] : "/dev/dri/card0";
    int fd = open(node, O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror(node); return 1; }
    struct gbm_device *gbm = gbm_create_device(fd);
    if (gbm == NULL) { fprintf(stderr, "gbm_create_device failed\n"); return 1; }

    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gbm, NULL);
    EGLint major = 0, minor = 0;
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor)) {
        fprintf(stderr, "eglInitialize failed 0x%x\n", eglGetError());
        return 1;
    }
    if (!eglBindAPI(EGL_OPENGL_ES_API)) { fprintf(stderr, "eglBindAPI failed\n"); return 1; }
    const char *extensions = eglQueryString(display, EGL_EXTENSIONS);
    int has_dma_buf = strstr(extensions, "EGL_EXT_image_dma_buf_import") != NULL;
    int has_modifiers = strstr(extensions, "EGL_EXT_image_dma_buf_import_modifiers") != NULL;
    int has_fence = strstr(extensions, "EGL_KHR_fence_sync") != NULL;
    int has_native_fence = strstr(extensions, "EGL_ANDROID_native_fence_sync") != NULL;
    printf("EGL %d.%d dma_buf=%d modifiers=%d fence=%d native_fence=%d\n", major, minor,
           has_dma_buf, has_modifiers, has_fence, has_native_fence);
    if (!has_dma_buf) { fprintf(stderr, "dma-buf import not supported\n"); return 1; }

    PFNEGLCREATEIMAGEKHRPROC create_image =
        (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
    PFNEGLDESTROYIMAGEKHRPROC destroy_image =
        (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
    PFNEGLCREATESYNCKHRPROC create_sync =
        (PFNEGLCREATESYNCKHRPROC)eglGetProcAddress("eglCreateSyncKHR");
    PFNEGLDESTROYSYNCKHRPROC destroy_sync =
        (PFNEGLDESTROYSYNCKHRPROC)eglGetProcAddress("eglDestroySyncKHR");
    PFNEGLCLIENTWAITSYNCKHRPROC client_wait_sync =
        (PFNEGLCLIENTWAITSYNCKHRPROC)eglGetProcAddress("eglClientWaitSyncKHR");
    if (!create_image || !destroy_image) {
        fprintf(stderr, "EGL image entry points unavailable\n");
        return 1;
    }

    EGLint config_attrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE,
                             EGL_OPENGL_ES2_BIT, EGL_NONE};
    EGLConfig config = NULL;
    EGLint count = 0;
    if (!eglChooseConfig(display, config_attrs, &config, 1, &count) || count < 1) {
        fprintf(stderr, "eglChooseConfig failed 0x%x\n", eglGetError());
        return 1;
    }
    EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
    EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attrs);
    if (context == EGL_NO_CONTEXT || surface == EGL_NO_SURFACE ||
        !eglMakeCurrent(display, surface, surface, context)) {
        fprintf(stderr, "context/surface failed 0x%x\n", eglGetError());
        return 1;
    }

    struct buffer background, foreground, target;
    if (buffer_create(gbm, &background, 64, 64) || buffer_create(gbm, &foreground, 32, 32) ||
        buffer_create(gbm, &target, 64, 64)) {
        return 1;
    }
    if (buffer_fill(&background, 0) || buffer_fill(&foreground, 1)) return 1;

    EGLImageKHR bg_image = image_import(display, create_image, has_modifiers, &background);
    EGLImageKHR fg_image = image_import(display, create_image, has_modifiers, &foreground);
    EGLImageKHR target_image = image_import(display, create_image, has_modifiers, &target);
    if (bg_image == EGL_NO_IMAGE_KHR || fg_image == EGL_NO_IMAGE_KHR ||
        target_image == EGL_NO_IMAGE_KHR) {
        fprintf(stderr, "dma-buf import failed 0x%x\n", eglGetError());
        return 1;
    }
    GLuint bg_texture = image_texture(bg_image);
    GLuint fg_texture = image_texture(fg_image);
    GLuint target_texture = image_texture(target_image);

    GLuint framebuffer = 0;
    glGenFramebuffers(1, &framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, target_texture, 0);
    GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    printf("fbo status=0x%x\n", status);
    if (status != GL_FRAMEBUFFER_COMPLETE) { fprintf(stderr, "fbo incomplete\n"); return 1; }

    const char *vs =
        "attribute vec2 pos;\n"
        "attribute vec2 tex;\n"
        "varying vec2 v_tex;\n"
        "void main() { v_tex = tex; gl_Position = vec4(pos, 0.0, 1.0); }\n";
    const char *fs =
        "precision mediump float;\n"
        "varying vec2 v_tex;\n"
        "uniform sampler2D tex;\n"
        "void main() { gl_FragColor = texture2D(tex, v_tex); }\n";
    GLuint vertex = compile_shader(GL_VERTEX_SHADER, vs);
    GLuint fragment = compile_shader(GL_FRAGMENT_SHADER, fs);
    if (!vertex || !fragment) return 1;
    GLuint program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glBindAttribLocation(program, 0, "pos");
    glBindAttribLocation(program, 1, "tex");
    glLinkProgram(program);
    GLint linked = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    printf("program link=%d\n", linked);
    if (!linked) return 1;
    glUseProgram(program);
    glUniform1i(glGetUniformLocation(program, "tex"), 0);

    static const GLfloat bg_quad[] = {-1, -1, 0, 0, 1, -1, 1, 0, -1, 1, 0, 1, 1, 1, 1, 1};
    static const GLfloat fg_quad[] = {-0.5f, -0.5f, 0, 0, 0.5f, -0.5f, 1, 0,
                                      -0.5f, 0.5f, 0, 1, 0.5f, 0.5f, 1, 1};
    struct timespec compose_start;
    clock_gettime(CLOCK_MONOTONIC, &compose_start);
    glViewport(0, 0, 64, 64);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);
    glDisable(GL_BLEND);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, bg_texture);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), bg_quad);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), bg_quad + 2);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glEnable(GL_BLEND);
    glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    glBindTexture(GL_TEXTURE_2D, fg_texture);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), fg_quad);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(GLfloat), fg_quad + 2);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glFinish();
    printf("compose_ms=%.3f\n", ms_since(&compose_start));

    int fence_ok = 0;
    if (has_fence && create_sync && client_wait_sync && destroy_sync) {
        EGLSyncKHR sync = create_sync(display, EGL_SYNC_FENCE_KHR, NULL);
        if (sync != EGL_NO_SYNC_KHR) {
            EGLint result = client_wait_sync(display, sync, 0, 1000000000ull);
            fence_ok = result == EGL_CONDITION_SATISFIED_KHR;
            destroy_sync(display, sync);
        }
        printf("fence wait=%d\n", fence_ok);
    }
    int native_fd = -1;
    if (has_native_fence && create_sync) {
        EGLint native_attrs[] = {EGL_SYNC_NATIVE_FENCE_FD_ANDROID, EGL_NO_NATIVE_FENCE_FD_ANDROID,
                                 EGL_NONE};
        EGLSyncKHR sync = create_sync(display, EGL_SYNC_NATIVE_FENCE_ANDROID, native_attrs);
        if (sync != EGL_NO_SYNC_KHR) {
            native_fd = eglDupNativeFenceFDANDROID(display, sync);
            if (destroy_sync) destroy_sync(display, sync);
        }
        printf("native_fence_fd=%d\n", native_fd);
        if (native_fd >= 0) close(native_fd);
    }

    unsigned char samples[3][4];
    glReadPixels(8, 32, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, samples[0]);
    glReadPixels(24, 32, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, samples[1]);
    glReadPixels(56, 32, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, samples[2]);
    printf("gpu left=%u,%u,%u,%u blend=%u,%u,%u,%u right=%u,%u,%u,%u glerr=0x%x\n",
           samples[0][0], samples[0][1], samples[0][2], samples[0][3],
           samples[1][0], samples[1][1], samples[1][2], samples[1][3],
           samples[2][0], samples[2][1], samples[2][2], samples[2][3], glGetError());

    int cpu_ok = -1;
    if (target.modifier == 0) {
        uint32_t stride = 0;
        void *map_data = NULL;
        uint8_t *map = gbm_bo_map(target.bo, 0, 0, 64, 64, GBM_BO_TRANSFER_READ, &stride, &map_data);
        if (map != NULL) {
            uint32_t *left = (uint32_t *)(map + 32 * stride) + 8;
            uint32_t *blend = (uint32_t *)(map + 32 * stride) + 24;
            uint32_t *right = (uint32_t *)(map + 32 * stride) + 56;
            printf("cpu left=0x%08x blend=0x%08x right=0x%08x\n", *left, *blend, *right);
            cpu_ok = (*left == 0xff00ff00u) &&
                     (((*right & 0x00ffffffu) == 0x000000ffu)) &&
                     (abs((int)((*blend >> 16) & 0xff) - 128) <= 8) &&
                     (abs((int)((*blend >> 8) & 0xff) - 128) <= 8) &&
                     (((*blend >> 0) & 0xff) <= 8);
            gbm_bo_unmap(target.bo, map_data);
        }
    } else {
        printf("cpu read skipped for modifier=0x%llx\n", (unsigned long long)target.modifier);
    }

    int pass = pixel_close(samples[0], 0xff00ff00u, 8) &&
               pixel_close(samples[1], 0xff808000u, 16) &&
               pixel_close(samples[2], 0xff0000ffu, 8) &&
               cpu_ok != 0;
    printf("fence_ok=%d cpu_ok=%d\n", fence_ok, cpu_ok);
    puts(pass ? "GPU_COMPOSE_PASS" : "GPU_COMPOSE_FAIL");

    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(display, surface);
    eglDestroyContext(display, context);
    eglTerminate(display);
    buffer_destroy(&background);
    buffer_destroy(&foreground);
    buffer_destroy(&target);
    gbm_device_destroy(gbm);
    close(fd);
    return pass ? 0 : 1;
}
