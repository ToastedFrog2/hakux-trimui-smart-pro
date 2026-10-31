#ifndef HAKUX_FRAME_SKIP_H
#define HAKUX_FRAME_SKIP_H
#include <stdbool.h>
#include <stdint.h>

/* Display-only policy: never suppress guest draws, fences, queries or flips.
 * A skipped unique front frame stays skipped across repeated panel refreshes;
 * otherwise this would only delay it one refresh rather than skip it. */
typedef struct HakuxFrameSkip {
    uint32_t generation, frame;
    bool seen, skip;
} HakuxFrameSkip;

static inline void hakux_frame_skip_reset(HakuxFrameSkip *s)
{
    *s = (HakuxFrameSkip){0};
}

static inline bool hakux_frame_skip_display(HakuxFrameSkip *s, unsigned mode,
                                           uint32_t generation, uint32_t frame)
{
    if (mode != 1) {
        hakux_frame_skip_reset(s);
        return false;
    }
    if (!s->seen || s->generation != generation) {
        *s = (HakuxFrameSkip){.generation=generation, .frame=frame, .seen=true};
        return false;
    }
    if (s->frame != frame) {
        s->frame = frame;
        s->skip = !s->skip;
    }
    return s->skip;
}
#endif
