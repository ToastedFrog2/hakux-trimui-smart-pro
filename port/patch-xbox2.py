#!/usr/bin/env python3
"""Optional Xbox 2 renderer changes; baseline builds compile the original path."""
from pathlib import Path

root = Path(__file__).resolve().parent
src = root / 'source'

def replace(path, old, new):
    p = src / path
    text = p.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Xbox 2 patch context missing: {path}: {old[:100]}')
    p.write_text(text.replace(old, new))

replace('native/CMakeLists.txt', 'set(CMAKE_C_STANDARD 11)', '''set(CMAKE_C_STANDARD 11)
option(HAKUX_XBOX2 "Experimental TrimUI Xbox 2 renderer" OFF)
if(HAKUX_XBOX2)
  add_compile_definitions(HAKUX_XBOX2=1)
  add_compile_options(-mcpu=cortex_a53)
  include_directories("${PORT_ROOT}/platform")
endif()''')
replace('native/CMakeLists.txt', '''    add_link_options("-Wl,--thinlto-cache-dir=${CMAKE_BINARY_DIR}/lto-cache")''',
'''    if(NOT HAKUX_XBOX2)
      add_link_options("-Wl,--thinlto-cache-dir=${CMAKE_BINARY_DIR}/lto-cache")
    endif() # Zig manages its own LTO cache.''')
replace('hw/xbox/hle/vk/draw.c', '#include "hw/xbox/hle/shader/psh.h"',
'''#include "hw/xbox/hle/shader/psh.h"
#ifdef HAKUX_XBOX2
#include "xbox2_pscache.h"
#endif''')
replace('hw/xbox/hle/vk/draw.c', '    bool st_valid;', '''    bool st_valid;
#ifdef HAKUX_XBOX2
    HakuxPshCache psh_cache;
#endif''')
replace('hw/xbox/hle/vk/draw.c', '''    g_dr.st = *s;
    g_dr.st_valid = true;''', '''    g_dr.st = *s;
    g_dr.st_valid = true;
#ifdef HAKUX_XBOX2
    g_dr.psh_cache.valid = false;
#endif''')
replace('hw/xbox/hle/vk/draw.c', '''        memcpy((uint8_t *)&g_dr.st + p->off, p + 1, p->len);''',
'''        memcpy((uint8_t *)&g_dr.st + p->off, p + 1, p->len);
#ifdef HAKUX_XBOX2
        hakux_pscache_changed(&g_dr.psh_cache, p->off, p->len);
#endif''')
replace('hw/xbox/hle/vk/draw.c', '''        hle_psh_key(s->rs, &k.pk);''',
'''#ifdef HAKUX_XBOX2
        k.pk = *hakux_pscache_get(&g_dr.psh_cache, s->rs);
#else
        hle_psh_key(s->rs, &k.pk);
#endif''')
replace('hw/xbox/hle/vk/draw.c', '''    unsigned first = s->rs[RS_POINTSPRITEENABLE] ? HLE_FF_SPRITE_STAGE : 0;
    for (unsigned st = first;''', '''#ifdef HAKUX_XBOX2
    /* Register-combiner draws replace all of this FF stage state below. */
    if (!s->psh) {
#endif
    unsigned first = s->rs[RS_POINTSPRITEENABLE] ? HLE_FF_SPRITE_STAGE : 0;
    for (unsigned st = first;''')
replace('hw/xbox/hle/vk/draw.c', '''    k.ps.fbfetch = (uint8_t)ff_fb_stages(c, rt_id);
    if (s->psh)''', '''    k.ps.fbfetch = (uint8_t)ff_fb_stages(c, rt_id);
#ifdef HAKUX_XBOX2
    }
#endif
    if (s->psh)''')
replace('hw/xbox/hle/vk/draw.c', '''        hle_batch_flush(cb);
        /* 16-bit indices''', '''#ifdef HAKUX_XBOX2
        hle_batch_prepare_indexed(cb);
#else
        hle_batch_flush(cb);
#endif
        /* 16-bit indices''')
replace('hw/xbox/hle/vk/draw.c', '''            T.vkCmdDrawIndexed(cb, g_hle_gpucut == 4 ? MIN(c->count, 3u) : c->count, 1,
                               c->ib_off / 2, (int32_t)vfirst, 0);''', '''#ifdef HAKUX_XBOX2
            if (q < 0 && g_hle_gpucut != 4 &&
                hle_batch_draw_indexed(cb, (VkPrimitiveTopology)c->prim,
                                       c->count, c->ib_off / 2, (int32_t)vfirst)) {
                /* Held until state changes or the command buffer ends. */
            } else
#endif
            T.vkCmdDrawIndexed(cb, g_hle_gpucut == 4 ? MIN(c->count, 3u) : c->count, 1,
                               c->ib_off / 2, (int32_t)vfirst, 0);''')
replace('hw/xbox/hle/vk/batch.h', 'void hle_batch_flush(VkCommandBuffer cb);',
'''void hle_batch_flush(VkCommandBuffer cb);
#ifdef HAKUX_XBOX2
void hle_batch_prepare_indexed(VkCommandBuffer cb);
bool hle_batch_draw_indexed(VkCommandBuffer cb, VkPrimitiveTopology prim,
                          uint32_t count, uint32_t first, int32_t base);
#endif''')
replace('hw/xbox/hle/vk/batch.c', '''/* Anything recorded on cb comes after the held run. */''',
'''#ifdef HAKUX_XBOX2
#include "xbox2_index_batch.h"
#endif

/* Anything recorded on cb comes after the held run. */''')
replace('hw/xbox/hle/vk/batch.c', '''static inline void batch_before(VkCommandBuffer cb)
{''', '''static inline void batch_before(VkCommandBuffer cb)
{
#ifdef HAKUX_XBOX2
    if (g_xbox2_index.cb == cb && cb) xbox2_index_flush();
#endif''')
replace('hw/xbox/hle/vk/batch.c', '''bool hle_batch_draw(VkCommandBuffer cb, VkPrimitiveTopology prim, uint32_t first, uint32_t count)
{''', '''bool hle_batch_draw(VkCommandBuffer cb, VkPrimitiveTopology prim, uint32_t first, uint32_t count)
{
#ifdef HAKUX_XBOX2
    xbox2_index_flush();
#endif''')
replace('hw/xbox/hle/vk/batch.c', '''void hle_batch_init(void)
{''', '''void hle_batch_init(void)
{
#ifdef HAKUX_XBOX2
    const char *index_mode = getenv("HAKUX_XBOX2_INDEX_BATCH");
    g_xbox2_index.enabled = batch_wanted() && (!index_mode || atoi(index_mode) != 0);
    hle_log("hakuX Xbox 2", "contiguous indexed batching %s",
            g_xbox2_index.enabled ? "on" : "off");
#endif''')
