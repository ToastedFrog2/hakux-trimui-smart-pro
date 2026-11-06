#!/usr/bin/env python3
"""Bound TrimUI GPU memory and buffer re-arms; budget published-clock reads."""
from pathlib import Path

root = Path(__file__).resolve().parent
src = root / 'source'


def replace(path, old, new):
    p = src / path
    text = p.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'stall-fix patch context missing: {path}: {old[:80]}')
    p.write_text(text.replace(old, new, 1))


# 1. Bound Vulkan upload arena & readback buffer sizes on 1 GiB TrimUI Smart Pro.
replace(
    'hw/xbox/hle/vk/back.c',
    '''    const char *what = hle_vk_guest_ram_init() ? "guest RAM" :
                       hle_vk_arena_init(g_hvk.caps.bc ? 32u << 20 : 64u << 20) ? "the upload arena" :
                       hle_vk_land_init(16u << 20) ? "the readback buffer" :''',
    '''#ifdef HAKUX_XBOX2
    const uint32_t arena_bytes = 32u << 20;
    const uint32_t land_bytes = 4u << 20;
#else
    const uint32_t arena_bytes = g_hvk.caps.bc ? 32u << 20 : 64u << 20;
    const uint32_t land_bytes = 16u << 20;
#endif
    const char *what = hle_vk_guest_ram_init() ? "guest RAM" :
                       hle_vk_arena_init(arena_bytes) ? "the upload arena" :
                       hle_vk_land_init(land_bytes) ? "the readback buffer" :''',
)

# 2. Bound resident uncompressed texture cache on 1 GiB TrimUI Smart Pro and cap recopied() mprotect churn.
replace(
    'hw/xbox/hle/pb/pbdraw.c',
    '''#define TEX_SLOTS 2048u                     /* the texture table (open addressing) */
#define TEX_MAX 1536u                       /* ... this full: the least recently used go (tex_evict) */''',
    '''#define TEX_SLOTS 2048u                     /* the texture table (open addressing) */
#ifdef HAKUX_XBOX2
#define TEX_MAX 768u                        /* ... this full: the least recently used go (tex_evict) */
#else
#define TEX_MAX 1536u                       /* ... this full: the least recently used go (tex_evict) */
#endif''',
)

replace(
    'hw/xbox/hle/pb/pbdraw.c',
    '''static bool recopied(uint32_t from, uint32_t len)
{
    static struct {
        uint32_t from, len;
        uint64_t swap;
        bool again;
    } t[1024];
    const unsigned i = (from ^ (from >> 12) ^ len * 31u) & 1023u;
    if (t[i].from != from || t[i].len != len) {
        t[i].from = from;
        t[i].len = len;
        t[i].again = false;
    } else if (t[i].swap == g_pd.swaps) {
        t[i].again = true;
    }
    t[i].swap = g_pd.swaps;
    return t[i].again;
}''',
    '''static bool recopied(uint32_t from, uint32_t len)
{
    static struct {
        uint32_t from, len;
        uint64_t swap;
        uint8_t arms;
        bool again;
    } t[1024];
    const unsigned i = (from ^ (from >> 12) ^ len * 31u) & 1023u;
    if (t[i].from != from || t[i].len != len) {
        t[i].from = from;
        t[i].len = len;
        t[i].arms = 0;
        t[i].again = false;
    } else if (t[i].swap == g_pd.swaps) {
        const bool first_repeat = !t[i].again;
        t[i].again = true;
        if (!first_repeat || t[i].arms >= 8) {
            return false;
        }
        t[i].arms++;
        return true;
    }
    t[i].swap = g_pd.swaps;
    if (!t[i].again || t[i].arms >= 8) {
        return false;
    }
    t[i].arms++;
    return true;
}''',
)

# 3. Amortize CLOCK_MONOTONIC_COARSE syscall in nc_ke_published_ns() on kernels without vDSO.
replace(
    'native/kernel/ke.c',
    '''static uint64_t g_pub_ns, g_pub_coarse;

void nc_ke_publish_time(uint64_t guest_ns)
{
    __atomic_store_n(&g_pub_coarse, coarse_ns(), __ATOMIC_RELAXED);
    __atomic_store_n(&g_pub_ns, guest_ns, __ATOMIC_RELEASE);
}

/* The published time, or 0 when there is none or the coarse clock says it
 * is stale (more than its tick, 4 ms on the RP5, without a publish: the
 * clock thread held off). */
uint64_t nc_ke_published_ns(void)
{
    const uint64_t pub = __atomic_load_n(&g_pub_ns, __ATOMIC_ACQUIRE);
    if (!pub || coarse_ns() - __atomic_load_n(&g_pub_coarse, __ATOMIC_RELAXED) > 4000000ull) {
        return 0;
    }
    return pub;
}''',
    '''static uint64_t g_pub_ns, g_pub_coarse;
static uint32_t g_pub_budget;

void nc_ke_publish_time(uint64_t guest_ns)
{
    __atomic_store_n(&g_pub_coarse, coarse_ns(), __ATOMIC_RELAXED);
    __atomic_store_n(&g_pub_budget, 64u, __ATOMIC_RELAXED);
    __atomic_store_n(&g_pub_ns, guest_ns, __ATOMIC_RELEASE);
}

/* The published time, or 0 when there is none or the coarse clock says it
 * is stale (more than its tick, 4 ms on the RP5, without a publish: the
 * clock thread held off). */
uint64_t nc_ke_published_ns(void)
{
    const uint64_t pub = __atomic_load_n(&g_pub_ns, __ATOMIC_ACQUIRE);
    if (!pub) {
        return 0;
    }
    const uint32_t b = __atomic_load_n(&g_pub_budget, __ATOMIC_RELAXED);
    if (b > 0) {
        __atomic_store_n(&g_pub_budget, b - 1, __ATOMIC_RELAXED);
        return pub;
    }
    if (coarse_ns() - __atomic_load_n(&g_pub_coarse, __ATOMIC_RELAXED) > 4000000ull) {
        return 0;
    }
    __atomic_store_n(&g_pub_budget, 64u, __ATOMIC_RELAXED);
    return pub;
}''',
)
