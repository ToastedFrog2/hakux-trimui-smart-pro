/* Xbox 2: cache the state-only part of an NV2A pixel shader.
 * Per-draw texture formats, fog, alpha test and debug overrides still apply
 * to a copy, never to this template. Only command-state writers invalidate it.
 */
#ifndef HAKUX_XBOX2_PSCACHE_H
#define HAKUX_XBOX2_PSCACHE_H
#include "hw/xbox/hle/front/cmd.h"
#include "hw/xbox/hle/shader/psh.h"
#include <stdbool.h>
#include <stddef.h>

typedef struct HakuxPshCache {
    HlePshKey key;
    bool valid;
} HakuxPshCache;

static inline void hakux_pscache_changed(HakuxPshCache *cache, size_t off, size_t len)
{
    const size_t first = offsetof(HleCmdState, rs);
    const size_t end = first + HLE_PS_REGS * sizeof(uint32_t);
    if (len && off < end && (off >= first || len > first - off)) {
        cache->valid = false;
    }
}

static inline const HlePshKey *hakux_pscache_get(HakuxPshCache *cache, const uint32_t *rs)
{
    if (!cache->valid) {
        hle_psh_key(rs, &cache->key);
        cache->valid = true;
    }
    return &cache->key;
}
#endif
