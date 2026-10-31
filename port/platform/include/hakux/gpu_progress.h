#ifndef HAKUX_GPU_PROGRESS_H
#define HAKUX_GPU_PROGRESS_H
#include <stdbool.h>
#include <stdint.h>

/* Sample published GPU counters, never a driver call. Loading/JIT/shader
 * compilation with an idle GPU must not trigger the recovery deadline. */
typedef struct HakuxGpuProgress {
    uint64_t completed, since_ms;
    bool pending;
} HakuxGpuProgress;

static inline bool hakux_gpu_stalled(HakuxGpuProgress *p, uint64_t now_ms,
                                      uint64_t submitted, uint64_t completed,
                                      uint64_t timeout_ms)
{
    if (!timeout_ms || completed >= submitted) {
        *p=(HakuxGpuProgress){.completed=completed};
        return false;
    }
    if (!p->pending || completed != p->completed || now_ms < p->since_ms) {
        *p=(HakuxGpuProgress){.completed=completed,.since_ms=now_ms,.pending=true};
        return false;
    }
    return now_ms-p->since_ms >= timeout_ms;
}
#endif
