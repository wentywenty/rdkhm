#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <gbm.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

/* Explicit on-board test: render offscreen without changing display modes. */
int main(int argc, char **argv)
{
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
    EGLint major, minor, count = 0;
    EGLConfig config;
    EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                           EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLint surface_attributes[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor)) goto done;
    initialized = 1;
    if (!eglBindAPI(EGL_OPENGL_ES_API) ||
        !eglChooseConfig(display, attributes, &config, 1, &count) || count != 1) goto done;
    context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
    surface = eglCreatePbufferSurface(display, config, surface_attributes);
    if (context == EGL_NO_CONTEXT || surface == EGL_NO_SURFACE ||
        !eglMakeCurrent(display, surface, surface, context)) goto done;
    printf("EGL %d.%d vendor=%s\n", major, minor, eglQueryString(display, EGL_VENDOR));
    printf("GL_RENDERER %s\n", glGetString(GL_RENDERER));
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
    if (result) fprintf(stderr, "GPU probe failed, EGL error=0x%x\n", eglGetError());
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
