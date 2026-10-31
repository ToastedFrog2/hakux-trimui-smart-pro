#ifndef HAKUX_LINUX_RANDOM_H
#define HAKUX_LINUX_RANDOM_H
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/random.h>
/* arc4random entered glibc after this device's 2.33. Use kernel entropy. */
static inline void nc_linux_random_buf(void *buffer, size_t size) {
    uint8_t *p = buffer;
    while (size) {
        ssize_t n = getrandom(p, size, 0);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) abort();
        p += n; size -= (size_t)n;
    }
}
static inline uint32_t nc_linux_random(void) {
    uint32_t n; nc_linux_random_buf(&n,sizeof(n)); return n;
}
#endif
