/* Regression fixture: previous implementation, retained to demonstrate the failure. */
void hle_barrier_arm_copied(uint32_t pa, uint32_t len)
{
    if (!g_cspan || !__atomic_load_n(&g_catch_up, __ATOMIC_ACQUIRE) || !len ||
        (uint64_t)pa + len > g_ram) {
        return;
    }
    if (g_cspan_faults) {
        for (uint32_t p = pa >> 12, last = (uint32_t)(((uint64_t)pa + len - 1) >> 12); p <= last; p++) {
            if (__atomic_load_n(&g_cspan_faults[p], __ATOMIC_RELAXED) > 8) {
                return;
            }
        }
    }
    const uint64_t end = (uint64_t)pa + len;
    for (uint64_t a = pa; a < end; a = (a | 4095) + 1) {
        const uint32_t lo = (uint32_t)(a & 4095);
        const uint32_t hi = end - (a & ~4095ull) < 4096 ? (uint32_t)(end & 4095) : 4096;
        uint32_t *s = &g_cspan[a >> 12];
        uint32_t old = __atomic_load_n(s, __ATOMIC_RELAXED), v;
        do {
            v = old ? MIN(old & 0xFFFF, lo) | MAX(old >> 16, hi) << 16 : lo | hi << 16;
        } while (!__atomic_compare_exchange_n(s, &old, v, true, __ATOMIC_RELEASE, __ATOMIC_RELAXED));
    }
    /* protected after the spans are set: a store from now on faults and
     * finds its span */
    uint64_t lo = pa & ~4095u;
    hle_host_mem_test_and_clear(hle_ram_addr_base() + lo, ((end + 4095) & ~4095ull) - lo);
}
