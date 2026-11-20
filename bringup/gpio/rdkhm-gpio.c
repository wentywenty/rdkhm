#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAP_PATH "/rdkhm/rdk_x5_40pin.tsv"
#define GPIO_ROOT "/sys/class/gpio"

struct pin_info {
    int pin;
    int gpio;
    int line;
    int base;
    int usable;
    char controller[32];
    char owner[64];
    char soc[64];
};

static int write_file(const char *path, const char *value)
{
    int fd = open(path, O_WRONLY);
    ssize_t written;

    if (fd < 0) {
        fprintf(stderr, "open %s: %s\n", path, strerror(errno));
        return -1;
    }
    written = write(fd, value, strlen(value));
    if (written != (ssize_t)strlen(value)) {
        fprintf(stderr, "write %s: %s\n", path, strerror(errno));
        close(fd);
        return -1;
    }
    close(fd);
    return 0;
}

static int read_file(const char *path, char *buffer, size_t size)
{
    int fd = open(path, O_RDONLY);
    ssize_t length;

    if (fd < 0) {
        return -1;
    }
    length = read(fd, buffer, size - 1);
    close(fd);
    if (length < 0) {
        return -1;
    }
    buffer[length] = '\0';
    while (length > 0 && (buffer[length - 1] == '\n' || buffer[length - 1] == '\r')) {
        buffer[--length] = '\0';
    }
    return 0;
}

static const char *map_path(void)
{
    const char *override = getenv("RDKHM_GPIO_MAP");

    return (override != NULL && override[0] != '\0') ? override : MAP_PATH;
}

static int pin_dir(int gpio, char *path, size_t size)
{
    return snprintf(path, size, GPIO_ROOT "/gpio%d", gpio);
}

static int pin_exists(int gpio)
{
    char path[128];

    pin_dir(gpio, path, sizeof(path));
    return access(path, F_OK) == 0;
}

static int load_pin(int pin, struct pin_info *info)
{
    FILE *stream = fopen(map_path(), "r");
    char line[256];

    if (stream == NULL) {
        fprintf(stderr, "open %s: %s\n", map_path(), strerror(errno));
        return -1;
    }
    while (fgets(line, sizeof(line), stream) != NULL) {
        struct pin_info entry;
        char controller[32];
        char owner[64];
        char soc[64];
        int fields;

        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        fields = sscanf(line, "%d\t%d\t%31s\t%d\t%d\t%d\t%63s\t%63[^\n]",
                        &entry.pin, &entry.gpio, controller, &entry.line,
                        &entry.base, &entry.usable, owner, soc);
        if (fields < 8) {
            continue;
        }
        if (entry.pin != pin) {
            continue;
        }
        snprintf(entry.controller, sizeof(entry.controller), "%s", controller);
        snprintf(entry.owner, sizeof(entry.owner), "%s", owner);
        snprintf(entry.soc, sizeof(entry.soc), "%s", soc);
        *info = entry;
        fclose(stream);
        return 0;
    }
    fclose(stream);
    fprintf(stderr, "pin %d is not in %s\n", pin, map_path());
    return -1;
}

static int pin_allowed(const struct pin_info *info)
{
    const char *force = getenv("RDKHM_GPIO_ALLOW_CLAIMED");

    if (info->usable) {
        return 1;
    }
    if (force != NULL && strcmp(force, "1") == 0) {
        fprintf(stderr, "warning: pin %d is not usable as GPIO (owner %s), forced by RDKHM_GPIO_ALLOW_CLAIMED\n",
                info->pin, info->owner);
        return 1;
    }
    fprintf(stderr, "pin %d is not usable as GPIO (mux_owner %s); refusing unless RDKHM_GPIO_ALLOW_CLAIMED=1\n",
            info->pin, info->owner);
    return 0;
}

static int export_pin(const struct pin_info *info, int direction, int value)
{
    char number[16];
    char path[128];
    char leaf[192];
    int tries;

    if (pin_exists(info->gpio)) {
        fprintf(stderr, "pin %d (gpio %d) is already exported\n", info->pin, info->gpio);
    } else {
        snprintf(number, sizeof(number), "%d", info->gpio);
        if (write_file(GPIO_ROOT "/export", number) != 0) {
            return -1;
        }
        for (tries = 0; tries < 100 && !pin_exists(info->gpio); tries++) {
            struct timespec delay = { 0, 10000000L };
            nanosleep(&delay, NULL);
        }
        if (!pin_exists(info->gpio)) {
            fprintf(stderr, "gpio %d did not appear after export\n", info->gpio);
            return -1;
        }
    }
    if (direction < 0) {
        return 0;
    }
    pin_dir(info->gpio, path, sizeof(path));
    snprintf(leaf, sizeof(leaf), "%s/direction", path);
    if (write_file(leaf, direction ? "out" : "in") != 0) {
        return -1;
    }
    if (direction && value >= 0) {
        snprintf(leaf, sizeof(leaf), "%s/value", path);
        return write_file(leaf, value ? "1" : "0");
    }
    return 0;
}

static int show_pin(const struct pin_info *info)
{
    char path[128];
    char leaf[192];
    char value[32];

    printf("pin:        %d\n", info->pin);
    printf("gpio:       %d\n", info->gpio);
    printf("controller: %s line %d (base %d)\n", info->controller, info->line, info->base);
    printf("soc_name:   %s\n", info->soc);
    printf("mux_owner:  %s\n", info->owner);
    printf("usable:     %s\n", info->usable ? "yes" : "no");
    if (!pin_exists(info->gpio)) {
        printf("exported:   no\n");
        return 0;
    }
    printf("exported:   yes\n");
    pin_dir(info->gpio, path, sizeof(path));
    snprintf(leaf, sizeof(leaf), "%s/direction", path);
    if (read_file(leaf, value, sizeof(value)) == 0) {
        printf("direction:  %s\n", value);
    }
    snprintf(leaf, sizeof(leaf), "%s/value", path);
    if (read_file(leaf, value, sizeof(value)) == 0) {
        printf("value:      %s\n", value);
    }
    return 0;
}

static int read_pin_value(const struct pin_info *info)
{
    char path[128];
    char leaf[192];
    char value[32];

    if (!pin_exists(info->gpio)) {
        fprintf(stderr, "pin %d (gpio %d) is not exported\n", info->pin, info->gpio);
        return -1;
    }
    pin_dir(info->gpio, path, sizeof(path));
    snprintf(leaf, sizeof(leaf), "%s/value", path);
    if (read_file(leaf, value, sizeof(value)) != 0) {
        fprintf(stderr, "read %s: %s\n", leaf, strerror(errno));
        return -1;
    }
    printf("%s\n", value);
    return 0;
}

static int list_pins(void)
{
    FILE *stream = fopen(map_path(), "r");
    char line[256];

    if (stream == NULL) {
        fprintf(stderr, "open %s: %s\n", map_path(), strerror(errno));
        return -1;
    }
    printf("PIN GPIO CTRL      LINE BASE USABLE OWNER               SOC\n");
    while (fgets(line, sizeof(line), stream) != NULL) {
        struct pin_info entry;
        char controller[32];
        char owner[64];
        char soc[64];
        int fields;

        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        fields = sscanf(line, "%d\t%d\t%31s\t%d\t%d\t%d\t%63s\t%63[^\n]",
                        &entry.pin, &entry.gpio, controller, &entry.line,
                        &entry.base, &entry.usable, owner, soc);
        if (fields < 8) {
            continue;
        }
        printf("%3d %4d %-9s %4d %4d %-6s %-20s %s\n", entry.pin, entry.gpio,
               controller, entry.line, entry.base, entry.usable ? "yes" : "no",
               owner, soc);
    }
    fclose(stream);
    return 0;
}

static void usage(void)
{
    fprintf(stderr,
            "usage: rdkhm-gpio <command> [args]\n"
            "  list\n"
            "  show <pin>\n"
            "  export <pin> [in|out] [0|1]\n"
            "  unexport <pin>\n"
            "  get <pin>\n"
            "  set <pin> <0|1>\n"
            "  dir <pin> <in|out>\n");
}

int main(int argc, char **argv)
{
    struct pin_info info;
    const char *command;

    if (argc < 2) {
        usage();
        return 2;
    }
    command = argv[1];
    if (strcmp(command, "list") == 0) {
        return list_pins() == 0 ? 0 : 1;
    }
    if (argc < 3) {
        usage();
        return 2;
    }
    if (load_pin(atoi(argv[2]), &info) != 0) {
        return 1;
    }
    if (strcmp(command, "show") == 0) {
        return show_pin(&info) == 0 ? 0 : 1;
    }
    if (strcmp(command, "export") == 0) {
        int direction = -1;
        int value = -1;

        if (argc >= 4) {
            if (strcmp(argv[3], "in") == 0) {
                direction = 0;
            } else if (strcmp(argv[3], "out") == 0) {
                direction = 1;
            } else {
                usage();
                return 2;
            }
        }
        if (argc >= 5) {
            if (strcmp(argv[4], "0") != 0 && strcmp(argv[4], "1") != 0) {
                usage();
                return 2;
            }
            value = argv[4][0] - '0';
        }
        if (!pin_allowed(&info)) {
            return 1;
        }
        return export_pin(&info, direction, value) == 0 ? 0 : 1;
    }
    if (strcmp(command, "unexport") == 0) {
        char number[16];

        if (!pin_exists(info.gpio)) {
            return 0;
        }
        snprintf(number, sizeof(number), "%d", info.gpio);
        return write_file(GPIO_ROOT "/unexport", number) == 0 ? 0 : 1;
    }
    if (strcmp(command, "get") == 0) {
        return read_pin_value(&info) == 0 ? 0 : 1;
    }
    if (strcmp(command, "set") == 0) {
        char leaf[192];
        char path[128];

        if (argc != 4 || (strcmp(argv[3], "0") != 0 && strcmp(argv[3], "1") != 0)) {
            usage();
            return 2;
        }
        if (!pin_exists(info.gpio)) {
            fprintf(stderr, "pin %d is not exported; run export first\n", info.pin);
            return 1;
        }
        if (!pin_allowed(&info)) {
            return 1;
        }
        pin_dir(info.gpio, path, sizeof(path));
        snprintf(leaf, sizeof(leaf), "%s/value", path);
        return write_file(leaf, argv[3]) == 0 ? 0 : 1;
    }
    if (strcmp(command, "dir") == 0) {
        char leaf[192];
        char path[128];

        if (argc != 4 || (strcmp(argv[3], "in") != 0 && strcmp(argv[3], "out") != 0)) {
            usage();
            return 2;
        }
        if (!pin_allowed(&info)) {
            return 1;
        }
        pin_dir(info.gpio, path, sizeof(path));
        snprintf(leaf, sizeof(leaf), "%s/direction", path);
        return write_file(leaf, argv[3]) == 0 ? 0 : 1;
    }
    usage();
    return 2;
}
