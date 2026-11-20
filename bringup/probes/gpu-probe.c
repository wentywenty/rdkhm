#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <gbm.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Explicit on-board test: render offscreen without changing display modes.
 * `--diag` reports every EGL step and the first usable config so a failure is
 * not reduced to the last eglGetError() value. */

static const char *egl_error_name(EGLint error)
{
    switch (error) {
        case EGL_SUCCESS: return "EGL_SUCCESS";
        case EGL_NOT_INITIALIZED: return "EGL_NOT_INITIALIZED";
        case EGL_BAD_ACCESS: return "EGL_BAD_ACCESS";
        case EGL_BAD_ALLOC: return "EGL_BAD_ALLOC";
        case EGL_BAD_ATTRIBUTE: return "EGL_BAD_ATTRIBUTE";
        case EGL_BAD_CONFIG: return "EGL_BAD_CONFIG";
        case EGL_BAD_CONTEXT: return "EGL_BAD_CONTEXT";
        case EGL_BAD_CURRENT_SURFACE: return "EGL_BAD_CURRENT_SURFACE";
        case EGL_BAD_DISPLAY: return "EGL_BAD_DISPLAY";
        case EGL_BAD_MATCH: return "EGL_BAD_MATCH";
        case EGL_BAD_NATIVE_PIXMAP: return "EGL_BAD_NATIVE_PIXMAP";
        case EGL_BAD_NATIVE_WINDOW: return "EGL_BAD_NATIVE_WINDOW";
        case EGL_BAD_PARAMETER: return "EGL_BAD_PARAMETER";
        case EGL_BAD_SURFACE: return "EGL_BAD_SURFACE";
        case EGL_CONTEXT_LOST: return "EGL_CONTEXT_LOST";
        default: return "EGL_UNKNOWN";
    }
}

static void print_egl_error(const char *step, EGLint error)
{
    printf("  %-26s egl=0x%04x %s\n", step, error, egl_error_name(error));
}

static int diag(const char *node)
{
    int fd = open(node, O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror(node); return 1; }
    struct gbm_device *gbm = gbm_create_device(fd);
    printf("node=%s gbm=%p\n", node, (void *)gbm);
    if (gbm == NULL) { close(fd); return 1; }

    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gbm, NULL);
    printf("display=%p\n", (void *)display);
    print_egl_error("eglGetPlatformDisplay", eglGetError());
    if (display == EGL_NO_DISPLAY) goto done;

    EGLint major = -1, minor = -1;
    EGLBoolean ok = eglInitialize(display, &major, &minor);
    print_egl_error("eglInitialize", eglGetError());
    printf("eglInitialize=%d version=%d.%d\n", ok, major, minor);
    if (!ok) goto done;
    printf("vendor=%s version=%s client_apis=%s\n",
           eglQueryString(display, EGL_VENDOR), eglQueryString(display, EGL_VERSION),
           eglQueryString(display, EGL_CLIENT_APIS));

    ok = eglBindAPI(EGL_OPENGL_ES_API);
    print_egl_error("eglBindAPI(ES)", eglGetError());
    printf("eglBindAPI=%d\n", ok);
    if (!ok) goto done;

    EGLint total = 0;
    eglGetConfigs(display, NULL, 0, &total);
    print_egl_error("eglGetConfigs(count)", eglGetError());
    printf("configs=%d\n", total);

    EGLConfig configs[64];
    EGLint got = 0;
    eglGetConfigs(display, configs, 64, &got);
    print_egl_error("eglGetConfigs(list)", eglGetError());
    EGLint ctx_attr[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    int usable = -1;
    for (EGLint i = 0; i < got && i < 64; i++) {
        EGLint red = -1, green = -1, blue = -1, alpha = -1, surface = -1, renderable = -1;
        eglGetConfigAttrib(display, configs[i], EGL_RED_SIZE, &red);
        eglGetConfigAttrib(display, configs[i], EGL_GREEN_SIZE, &green);
        eglGetConfigAttrib(display, configs[i], EGL_BLUE_SIZE, &blue);
        eglGetConfigAttrib(display, configs[i], EGL_ALPHA_SIZE, &alpha);
        eglGetConfigAttrib(display, configs[i], EGL_SURFACE_TYPE, &surface);
        eglGetConfigAttrib(display, configs[i], EGL_RENDERABLE_TYPE, &renderable);
        EGLContext context = eglCreateContext(display, configs[i], EGL_NO_CONTEXT, ctx_attr);
        EGLint error = eglGetError();
        printf("cfg[%d]=%p rgba=%d,%d,%d,%d surface=0x%x renderable=0x%x ctx=%p err=0x%04x %s\n",
               i, (void *)configs[i], red, green, blue, alpha, surface, renderable,
               (void *)context, error, egl_error_name(error));
        if (context != EGL_NO_CONTEXT) {
            usable = i;
            eglDestroyContext(display, context);
            break;
        }
    }
    printf("first usable config index=%d\n", usable);
    eglTerminate(display);

done:
    gbm_device_destroy(gbm);
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc > 1 && strcmp(argv[1], "--diag") == 0) {
        return diag(argc > 2 ? argv[2] : "/dev/dri/card0");
    }
    if (argc > 2) return 2;
    const char *node = argc == 2 ? argv[1] : "/dev/dri/card0";
    int fd = open(node, O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror(node); return 1; }
    struct gbm_device *gbm = gbm_create_device(fd);
    if (gbm == NULL) { fprintf(stderr, "GBM device creation failed\n"); close(fd); return 1; }

    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gbm, NULL);
    EGLContext context = EGL_NO_CONTEXT;
    EGLSurface surface = EGL_NO_SURFACE;
    int initialized = 0, result = 1;
    EGLint error = EGL_SUCCESS;
    const char *failed_step = NULL;
    EGLint major, minor, count = 0;
    EGLConfig config;
    EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                           EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8,
                           EGL_NONE};
    EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLint surface_attributes[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};

    error = eglGetError();
    if (display == EGL_NO_DISPLAY) { failed_step = "eglGetPlatformDisplay"; goto done; }
    if (!eglInitialize(display, &major, &minor)) {
        failed_step = "eglInitialize";
        error = eglGetError();
        goto done;
    }
    initialized = 1;
    if (!eglBindAPI(EGL_OPENGL_ES_API)) {
        failed_step = "eglBindAPI";
        error = eglGetError();
        goto done;
    }
    if (!eglChooseConfig(display, attributes, &config, 1, &count) || count < 1) {
        failed_step = "eglChooseConfig";
        error = eglGetError();
        goto done;
    }
    context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
    if (context == EGL_NO_CONTEXT) {
        failed_step = "eglCreateContext";
        error = eglGetError();
        goto done;
    }
    surface = eglCreatePbufferSurface(display, config, surface_attributes);
    if (surface == EGL_NO_SURFACE) {
        failed_step = "eglCreatePbufferSurface";
        error = eglGetError();
        goto done;
    }
    if (!eglMakeCurrent(display, surface, surface, context)) {
        failed_step = "eglMakeCurrent";
        error = eglGetError();
        goto done;
    }
    printf("EGL %d.%d vendor=%s\n", major, minor, eglQueryString(display, EGL_VENDOR));
    printf("GL_RENDERER %s\n", glGetString(GL_RENDERER));
    printf("GL_VERSION %s\n", glGetString(GL_VERSION));
    glClearColor(0.25f, 0.5f, 0.75f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glFinish();
    unsigned char pixel[4] = {0};
    glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    if (glGetError() != GL_NO_ERROR || pixel[0] < 62 || pixel[0] > 66 ||
        pixel[1] < 126 || pixel[1] > 130 || pixel[2] < 189 || pixel[2] > 193 || pixel[3] != 255) {
        fprintf(stderr, "Pixel check failed: %u,%u,%u,%u\n", pixel[0], pixel[1], pixel[2], pixel[3]);
        goto done;
    }
    puts("GPU_OFFSCREEN_PASS");
    result = 0;

done:
    if (result) {
        fprintf(stderr, "GPU probe failed at %s, EGL error=0x%x %s\n",
                failed_step ? failed_step : "unknown", error, egl_error_name(error));
    }
    if (initialized) {
        eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
        if (context != EGL_NO_CONTEXT) eglDestroyContext(display, context);
        eglTerminate(display);
    }
    gbm_device_destroy(gbm);
    close(fd);
    return result;
}
