/* Regression fixture: previous implementation, retained to demonstrate the failure. */
static __thread bool t_in_entry;
static uint64_t g_entry_ns;

static uint64_t raw_ns(void)
{
#if defined(__aarch64__)
    static uint64_t base_ns, base_cnt, freq;
    if (__builtin_expect(!__atomic_load_n(&freq, __ATOMIC_ACQUIRE), 0)) {
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        uint64_t c, f;
        do {
            __asm__ volatile("isb; mrs %0, cntvct_el0" : "=r"(c));
        } while (__builtin_expect(((c + 1u) & 0x1FFu) <= 1u, 0));
        __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(f));
        base_ns = (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
        base_cnt = c;
        __atomic_store_n(&freq, f ? f : 24000000ull, __ATOMIC_RELEASE);
    }
    uint64_t c;
    do {
        __asm__ volatile("isb; mrs %0, cntvct_el0" : "=r"(c));
    } while (__builtin_expect(((c + 1u) & 0x1FFu) <= 1u, 0));
    const uint64_t d = c - base_cnt;
    const uint64_t f = __atomic_load_n(&freq, __ATOMIC_RELAXED);
    return base_ns + (uint64_t)(((__uint128_t)d * 1000000000ull) / f);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}

static uint64_t coarse_ns(void)
{
    return raw_ns();
}

/* The emulation paused (nc_kernel_pause_point): the guest's time stops where
 * the pause began and goes on from there, the time paused left out (g_off,
 * host ns). A seqlock: the guest's CPU writes, any thread reads. */
static uint32_t g_tseq;
static bool g_tpaused;
static uint64_t g_tpause_raw, g_off;

static uint64_t guest_of_raw(uint64_t raw)
{
    for (;;) {
        const uint32_t s = __atomic_load_n(&g_tseq, __ATOMIC_ACQUIRE);
        if (s & 1) {
            continue;                   /* the guest's CPU is writing it */
        }
        const bool p = __atomic_load_n(&g_tpaused, __ATOMIC_RELAXED);
        const uint64_t pr = __atomic_load_n(&g_tpause_raw, __ATOMIC_RELAXED);
        const uint64_t off = __atomic_load_n(&g_off, __ATOMIC_RELAXED);
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (__atomic_load_n(&g_tseq, __ATOMIC_RELAXED) == s) {
            return (p ? pr : raw) - off;
        }
    }
}

static void time_write(bool paused)
{
    const uint64_t raw = raw_ns();
    __atomic_fetch_add(&g_tseq, 1, __ATOMIC_ACQ_REL);
    if (paused) {
        __atomic_store_n(&g_tpause_raw, raw, __ATOMIC_RELAXED);
    } else {
        __atomic_store_n(&g_off, g_off + (raw - g_tpause_raw), __ATOMIC_RELAXED);
    }
    __atomic_store_n(&g_tpaused, paused, __ATOMIC_RELAXED);
    __atomic_fetch_add(&g_tseq, 1, __ATOMIC_RELEASE);
    g_entry_ns = 0;
}

void nc_ke_pause_begin(void)
{
    time_write(true);
}

uint64_t nc_ke_pause_end(void)
{
    const uint64_t was = g_off;
    time_write(false);
    return g_off - was;
}

void nc_ke_state(uint64_t *boot_ns, uint64_t *time_offset, uint64_t *guest_ns)
{
    *boot_ns = g_boot_ns;
    *time_offset = g_time_offset;
    *guest_ns = guest_of_raw(raw_ns());
}

/* A savestate's: the guest's time goes on from guest_ns, now. */
void nc_ke_state_set(uint64_t boot_ns, uint64_t time_offset, uint64_t guest_ns)
{
    g_boot_ns = boot_ns;
    g_time_offset = time_offset;
    const uint64_t raw = raw_ns();
    __atomic_fetch_add(&g_tseq, 1, __ATOMIC_ACQ_REL);
    __atomic_store_n(&g_off, raw - guest_ns, __ATOMIC_RELAXED);
    __atomic_store_n(&g_tpause_raw, raw, __ATOMIC_RELAXED);
    __atomic_store_n(&g_tpaused, false, __ATOMIC_RELAXED);
    __atomic_fetch_add(&g_tseq, 1, __ATOMIC_RELEASE);
    g_entry_ns = 0;
}

uint64_t nc_ke_host_ns(uint64_t guest_ns)
{
    return guest_ns + __atomic_load_n(&g_off, __ATOMIC_RELAXED);
}

uint64_t nc_ke_now_ns(void)
{
    if (t_in_entry && g_entry_ns) {
        return g_entry_ns;
    }
    const uint64_t v = guest_of_raw(raw_ns());
    if (t_in_entry) {
        g_entry_ns = v;
    }
    return v;
}

void nc_ke_time_enter(void)
{
    g_entry_ns = 0;
    t_in_entry = true;
}

void nc_ke_time_leave(void)
{
    t_in_entry = false;
}

void nc_ke_time_stale(void)
{
    g_entry_ns = 0;
}


static uint64_t since_boot_100ns;
