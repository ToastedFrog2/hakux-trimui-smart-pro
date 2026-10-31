#ifndef HAKUX_PREBUILD_BUDGET_H
#define HAKUX_PREBUILD_BUDGET_H
#include <stdint.h>
#include <stdlib.h>

/* One GiB is shared with guest RAM, FEX, textures, and the system UI. Keep
 * the full disk record, but avoid instantiating every past level at boot. */
static inline uint32_t hakux_prebuild_budget(uint32_t max, const char *option)
{
    unsigned long budget=512;
    if (option && *option>='0' && *option<='9') {
        char *end;
        unsigned long parsed=strtoul(option,&end,10);
        if (end!=option && !*end) budget=parsed;
    }
    return budget>max ? max : (uint32_t)budget;
}
#endif
