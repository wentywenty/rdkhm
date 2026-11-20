// Minimal SLE advertising probe for /dev/hwsle.
// Protocol derived from the WS73 reference scripts:
//   frame: 0xA1 | opcode u16 LE | payload_len u16 LE | payload
//   RX:    0xA2 EVENT, 0xA3 ACB, 0xA4 ICB
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <time.h>
#include <unistd.h>

#define DEV "/dev/hwsle"
#define DT_CMD 0xA1
#define OP_ADV_PARAMS 0x0C02
#define OP_ADV_DATA 0x0C03
#define OP_ADV_ENABLE 0x0C05

static long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static void dump(const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; i++)
        printf("%02x%s", data[i], i + 1 == len ? "" : " ");
    putchar('\n');
}

static long g_start_ms;

static void drain(int fd, int milliseconds)
{
    long end = now_ms() + milliseconds;
    while (now_ms() < end) {
        fd_set set;
        FD_ZERO(&set);
        FD_SET(fd, &set);
        struct timeval tv = {0, 50000};
        int ready = select(fd + 1, &set, NULL, NULL, &tv);
        if (ready <= 0)
            continue;
        uint8_t buf[4096];
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n > 0) {
            printf("RX @%ldms %zd: ", now_ms() - g_start_ms, n);
            dump(buf, (size_t)n);
            if (buf[0] == 0xA2 && n >= 8) {
                uint16_t opcode = (uint16_t)(buf[5] | (buf[6] << 8));
                printf("   EVENT op=0x%04x status=0x%02x data_len=%zd\n",
                       opcode, buf[7], n - 8);
            } else if (buf[0] == 0xA3) {
                printf("   ACB advertising report (%zd bytes)\n", n);
            } else if (buf[0] == 0xA4) {
                printf("   ICB connection info (%zd bytes)\n", n);
            }
        }
    }
}

static int send_frame(int fd, uint16_t opcode, const uint8_t *payload, size_t len)
{
    uint8_t frame[320];
    if (len > sizeof(frame) - 5)
        return -1;
    frame[0] = DT_CMD;
    frame[1] = (uint8_t)(opcode & 0xff);
    frame[2] = (uint8_t)(opcode >> 8);
    frame[3] = (uint8_t)(len & 0xff);
    frame[4] = (uint8_t)(len >> 8);
    memcpy(frame + 5, payload, len);
    printf("TX op=0x%04x len=%zu: ", opcode, len);
    dump(frame, len + 5);
    fflush(stdout);
    return write(fd, frame, len + 5) == (ssize_t)(len + 5) ? 0 : -1;
}

static void adv_params(uint8_t p[49])
{
    memset(p, 0, 49);
    p[0] = 0;           /* advHandle */
    p[1] = 1;           /* advMode: connectable undirected */
    uint32_t interval = 800; /* 100 ms in 125 us units */
    p[3] = interval & 0xff;
    p[4] = (interval >> 8) & 0xff;
    p[5] = (interval >> 16) & 0xff;
    p[6] = interval & 0xff;
    p[7] = (interval >> 8) & 0xff;
    p[8] = (interval >> 16) & 0xff;
    p[9] = 0x07;        /* channels 76/77/78 */
    p[10] = 0;          /* own address type public */
    p[11] = 0;          /* peer address type */
    p[24] = 0;          /* filter policy */
    p[25] = 127;        /* TX power: no preference */
    p[26] = 0;          /* primary frame format */
}

int main(int argc, char **argv)
{
    int hold_ms = 30000;
    if (argc > 1) {
        int seconds = atoi(argv[1]);
        if (seconds > 0)
            hold_ms = seconds * 1000;
    }

    int fd = open(DEV, O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        perror("open " DEV);
        return 1;
    }
    g_start_ms = now_ms();
    printf("opened " DEV "\n");
    drain(fd, 1000);

    uint8_t params[49];
    adv_params(params);
    printf("== SET_ADV_PARAMS ==\n");
    if (send_frame(fd, OP_ADV_PARAMS, params, sizeof(params)) < 0)
        perror("write params");
    usleep(300000);
    drain(fd, 2500);

    const uint8_t adv[] = {0x02, 0x01, 0x06, 0x03, 0x03, 0x41, 0x42, 0x43};
    uint8_t data[4 + sizeof(adv)] = {0, 3, 0, (uint8_t)sizeof(adv)};
    memcpy(data + 4, adv, sizeof(adv));
    printf("== SET_ADV_DATA ==\n");
    if (send_frame(fd, OP_ADV_DATA, data, sizeof(data)) < 0)
        perror("write data");
    usleep(300000);
    drain(fd, 2500);

    const uint8_t enable[] = {1, 0, 0, 0, 0};
    printf("== SET_ADV_ENABLE ==\n");
    if (send_frame(fd, OP_ADV_ENABLE, enable, sizeof(enable)) < 0)
        perror("write enable");
    usleep(300000);
    drain(fd, 2500);

    printf("== holding fd %d ms; advertising stays enabled ==\n", hold_ms);
    drain(fd, hold_ms);

    close(fd);
    printf("closed; done\n");
    return 0;
}
