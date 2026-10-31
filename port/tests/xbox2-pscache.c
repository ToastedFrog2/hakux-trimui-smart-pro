#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#define hle_psh_key reference_psh_key
#include "hw/xbox/hle/shader/psh.c"
#undef hle_psh_key
static unsigned builds;
void hle_psh_key(const uint32_t *rs, HlePshKey *k) { builds++; reference_psh_key(rs, k); }
#include "xbox2_pscache.h"

static uint32_t seed = 0x882324;
static uint32_t random32(void) { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }
int main(void)
{
    HleCmdState state = {0};
    HakuxPshCache cache = {0};
    HlePshKey want;
    state.rs[HLE_PS_COUNT] = 8;
    for (unsigned i = 0; i < 100000; i++) {
        if (i % 5 == 0) {
            size_t off = random32() % sizeof(state);
            size_t len = 1 + random32() % 12;
            if (len > sizeof(state) - off) len = sizeof(state) - off;
            for (size_t j = 0; j < len; j++) ((unsigned char *)&state)[off+j] = random32();
            hakux_pscache_changed(&cache, off, len);
        }
        if (i % 997 == 0) { memset(&state, 0xa3, sizeof(state)); cache.valid = false; }
        reference_psh_key(state.rs, &want);
        HlePshKey got = *hakux_pscache_get(&cache, state.rs);
        assert(!memcmp(&got, &want, sizeof(got)));
        got.fog ^= 3; got.fbfetch ^= 15; got.vol ^= 15; got.debug ^= 4;
        assert(!memcmp(hakux_pscache_get(&cache, state.rs), &want, sizeof(want)));
    }
    cache.valid = true;
    hakux_pscache_changed(&cache, 0, 0); assert(cache.valid);
    hakux_pscache_changed(&cache, HLE_PS_REGS*4, 1); assert(cache.valid);
    hakux_pscache_changed(&cache, HLE_PS_REGS*4-1, 1); assert(!cache.valid);
    builds = 0; cache.valid = false;
    for (unsigned i = 0; i < 10000; i++) hakux_pscache_get(&cache, state.rs);
    assert(builds == 1);
    printf("PASS shader template: 100000 differential draws with partial/full updates; 10000 unchanged draws -> %u template build\n", builds);
    return 0;
}
