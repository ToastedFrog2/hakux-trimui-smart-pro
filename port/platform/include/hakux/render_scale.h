/* Shared CPU/shader contract for the optional half-resolution renderer. */
#ifndef HAKUX_RENDER_SCALE_H
#define HAKUX_RENDER_SCALE_H
#include <math.h>
#include <stdint.h>

/* Codes 1..4 retain their existing meaning. 128 is 0.5x, 129 is 0.35x, 130 is 0.75x in the
 * existing push-constant bytes, leaving the serialized pipeline key intact. */
static inline uint32_t hle_scale_code(float scale) { return scale == .75f ? 130u : scale == .35f ? 129u : scale < 1.0f ? 128u : (uint32_t)scale; }
static inline float hle_scale_decode(uint32_t code) { return code == 130u ? .75f : code == 129u ? .35f : code == 128u ? 0.5f : (float)(code ? code : 1u); }
static inline float hle_scale_clamp(float scale) {
    if (!isfinite(scale)) return 1.0f;
    if (scale == 0.5f || scale == .35f || scale == .75f) return scale;
    return scale < 1.0f ? 1.0f : scale > 4.0f ? 4.0f : (float)(unsigned)scale;
}
static inline uint32_t hle_scale_extent(uint32_t size, float scale) {
    if (!size) return 0;
    uint32_t n = (uint32_t)ceilf((float)size * scale);
    return n ? n : 1;
}
static inline int32_t hle_scale_lo(int32_t n, float scale) { return (int32_t)floorf((float)n * scale); }
static inline int32_t hle_scale_hi(int32_t n, float scale) { return (int32_t)ceilf((float)n * scale); }
static inline uint32_t hle_scale_samples(uint64_t samples, uint32_t divisor, float scale) {
    uint64_t div = divisor ? divisor : 1;
    if (scale == .75f) {
        __uint128_t n = (__uint128_t)samples * 16 / (div * 9);
        return n > UINT32_MAX ? UINT32_MAX : (uint32_t)n;
    }
    if (scale == .35f) {
        __uint128_t n = (__uint128_t)samples * 400 / (div * 49);
        return n > UINT32_MAX ? UINT32_MAX : (uint32_t)n;
    }
    if (scale == 0.5f) {
        if (samples > UINT64_MAX / 4) return UINT32_MAX;
        uint64_t n = samples * 4 / div;
        return n > UINT32_MAX ? UINT32_MAX : (uint32_t)n;
    }
    div *= (uint32_t)(scale * scale);
    return (uint32_t)(samples / div);
}

typedef struct HleScaledRect { int32_t x, y; uint32_t w, h; } HleScaledRect;
static inline HleScaledRect hle_scale_rect(int32_t x1, int32_t y1, int32_t x2, int32_t y2,
                                          float scale, uint32_t width, uint32_t height) {
    HleScaledRect r = {0};
    if (x2 <= x1 || y2 <= y1) return r;
    int32_t lo_x = hle_scale_lo(x1,scale), lo_y = hle_scale_lo(y1,scale);
    int32_t hi_x = hle_scale_hi(x2,scale), hi_y = hle_scale_hi(y2,scale);
    if (lo_x < 0) lo_x = 0;
    if (lo_y < 0) lo_y = 0;
    if (hi_x > (int32_t)width) hi_x = width;
    if (hi_y > (int32_t)height) hi_y = height;
    if (hi_x <= lo_x || hi_y <= lo_y) return r;
    return (HleScaledRect){lo_x,lo_y,(uint32_t)(hi_x-lo_x),(uint32_t)(hi_y-lo_y)};
}
#endif
