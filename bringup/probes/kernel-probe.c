// SPDX-License-Identifier: Apache-2.0
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <linux/android/binder.h>
#include <ashmem.h>

#define TOKEN_GET _IOR('A', 1, unsigned long long)
#define TOKEN_SET _IOW('A', 2, unsigned long long)
_Static_assert(sizeof(struct binder_feature_set) == 8, "Binder feature ABI");
_Static_assert(sizeof(struct access_token) == 32, "Binder token ABI");

static int failed;

static void check(int ok, const char *name)
{
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        failed++;
}

static void binder_probe(void)
{
    const char *paths[] = {"/dev/binder", "/dev/hwbinder", "/dev/vndbinder"};
    for (unsigned int i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        int fd = open(paths[i], O_RDWR | O_CLOEXEC);
        check(fd >= 0, paths[i]);
        if (fd < 0)
            continue;
        struct binder_version version = {0};
        check(ioctl(fd, BINDER_VERSION, &version) == 0 &&
              version.protocol_version == BINDER_CURRENT_PROTOCOL_VERSION,
              "Binder protocol version");
        struct binder_feature_set feature = {0};
        check(ioctl(fd, BINDER_FEATURE_SET, &feature) == 0 && feature.feature_set == 1,
              "Binder advertises only AccessToken extension");
        struct access_token token;
        memset(&token, 0xff, sizeof(token));
        check(ioctl(fd, BINDER_GET_ACCESS_TOKEN, &token) == 0 &&
              token.sender_tokenid == 0 && token.first_tokenid == 0 &&
              token.reserved[0] == 0 && token.reserved[1] == 0,
              "Fresh Binder thread token and reserved fields are zero");
        errno = 0;
        check(ioctl(fd, BINDER_GET_ACCESS_TOKEN, NULL) == -1 && errno == EFAULT,
              "Binder rejects invalid token output pointer");
        close(fd);
    }
}

static void token_probe(void)
{
    int fd = open("/dev/access_token_id", O_RDWR | O_CLOEXEC);
    check(fd >= 0, "/dev/access_token_id");
    if (fd < 0)
        return;
    unsigned long long original = 0, readback = 0;
    if (ioctl(fd, TOKEN_GET, &original) < 0) {
        check(0, "AccessToken read");
        close(fd);
        return;
    }
    /* This dedicated root test process changes only its own task token. */
    unsigned long long sample = 0x123456789abcdef0ULL;
    check(ioctl(fd, TOKEN_SET, &sample) == 0, "AccessToken write");
    check(ioctl(fd, TOKEN_GET, &readback) == 0 && readback == sample,
          "AccessToken 64-bit roundtrip");
    check(ioctl(fd, TOKEN_SET, &original) == 0, "AccessToken restore");
    close(fd);
}

static void ashmem_probe(void)
{
    int fd = open("/dev/ashmem", O_RDWR | O_CLOEXEC);
    check(fd >= 0, "/dev/ashmem");
    if (fd < 0)
        return;
    size_t size = (size_t)sysconf(_SC_PAGESIZE);
    char name[ASHMEM_NAME_LEN] = "rdkhm-probe";
    check(ioctl(fd, ASHMEM_SET_NAME, name) == 0, "Ashmem set name");
    check(ioctl(fd, ASHMEM_SET_SIZE, size) == 0, "Ashmem set size");
    check(ioctl(fd, ASHMEM_GET_SIZE) == (int)size, "Ashmem get size");
    char *memory = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    check(memory != MAP_FAILED, "Ashmem mmap");
    if (memory != MAP_FAILED) {
        memcpy(memory, name, sizeof(name));
        check(memcmp(memory, name, sizeof(name)) == 0, "Ashmem read/write");
        munmap(memory, size);
    }
    close(fd);
}

int main(void)
{
    puts("RDKHM kernel ABI smoke test; not OpenHarmony system qualification");
    binder_probe();
    token_probe();
    ashmem_probe();
    printf("RESULT failures=%d\n", failed);
    return failed ? 1 : 0;
}
