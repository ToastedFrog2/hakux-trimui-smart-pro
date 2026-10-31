/* memset, memcmp and bcmp a word at a time.
 *
 * Zig's compiler_rt links byte-at-a-time versions of these into the
 * executable, and its definitions win over glibc's. The render thread
 * compares a ~450-byte pipeline key and other state on every draw: in
 * Terminator: Dawn of Fate (~10k draws a frame) bcmp alone was 29% of the
 * thread. Definitions here take their place. no_builtin keeps the compiler
 * from turning the loops back into calls to themselves.
 */
#include <stddef.h>
#include <stdint.h>

typedef uint64_t __attribute__((may_alias, aligned(1))) u64u;

__attribute__((no_builtin)) int bcmp(const void *a, const void *b, size_t n)
{
    const unsigned char *p = a, *q = b;
    while (n >= 32) {
        uint64_t d = (*(const u64u *)p ^ *(const u64u *)q) | (((const u64u *)p)[1] ^ ((const u64u *)q)[1]) |
                     (((const u64u *)p)[2] ^ ((const u64u *)q)[2]) | (((const u64u *)p)[3] ^ ((const u64u *)q)[3]);
        if (d) {
            return 1;
        }
        p += 32;
        q += 32;
        n -= 32;
    }
    while (n >= 8) {
        if (*(const u64u *)p != *(const u64u *)q) {
            return 1;
        }
        p += 8;
        q += 8;
        n -= 8;
    }
    while (n--) {
        if (*p++ != *q++) {
            return 1;
        }
    }
    return 0;
}

__attribute__((no_builtin)) int memcmp(const void *a, const void *b, size_t n)
{
    const unsigned char *p = a, *q = b;
    while (n >= 8) {
        uint64_t x = *(const u64u *)p, y = *(const u64u *)q;
        if (x != y) {
            /* the first differing byte decides: big-endian order compares it first */
            return __builtin_bswap64(x) < __builtin_bswap64(y) ? -1 : 1;
        }
        p += 8;
        q += 8;
        n -= 8;
    }
    while (n--) {
        int d = *p++ - *q++;
        if (d) {
            return d;
        }
    }
    return 0;
}

__attribute__((no_builtin)) void *memset(void *dst, int c, size_t n)
{
    unsigned char *p = dst;
    if (n < 16) {
        while (n--) {
            *p++ = (unsigned char)c;
        }
        return dst;
    }
    uint64_t w = 0x0101010101010101ull * (unsigned char)c;
    /* first and last 16 bytes unaligned, the rest 16 at a time, aligned */
    ((u64u *)p)[0] = w;
    ((u64u *)p)[1] = w;
    ((u64u *)(p + n - 16))[0] = w;
    ((u64u *)(p + n - 16))[1] = w;
    unsigned char *end = p + n - 16;
    p = (unsigned char *)(((uintptr_t)p + 16) & ~(uintptr_t)15);
    for (; p < end; p += 16) {
        ((uint64_t *)p)[0] = w;
        ((uint64_t *)p)[1] = w;
    }
    return dst;
}
