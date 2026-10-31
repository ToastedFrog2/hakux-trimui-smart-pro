#!/usr/bin/env python3
"""Wire the Xbox 2 menu into the existing input and Vulkan presentation."""
from pathlib import Path
root=Path(__file__).resolve().parent
def replace(name,old,new):
    p=root/'source'/name;t=p.read_text()
    if new in t:return
    if old not in t:raise SystemExit('Menu patch context missing: '+name)
    p.write_text(t.replace(old,new))
replace('native/CMakeLists.txt','target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/fastmem.c")',
'''target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/fastmem.c")
target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/menu.c")''')
replace('native/run/xboxrun.c','#include "native/app/app.h"',
        '#include "native/app/app.h"\n#include "hakux/menu.h"')
replace('native/run/xboxrun.c','    nc_options_apply(&opt);',
'''#ifdef HAKUX_XBOX2
    hakux_menu_init(argc, argv);
#endif
    nc_options_apply(&opt);''')
replace('native/run/xboxrun.c','    dump_ranges(getenv("NC_DUMP"));',
'''#ifdef HAKUX_XBOX2
    hakux_menu_ready();
#endif
    dump_ranges(getenv("NC_DUMP"));''')
replace('native/app/present.c','#include "native/app/app.h"',
        '#include "native/app/app.h"\n#include "hakux/menu.h"')
replace('native/app/present.c','(uint64_t)(uint32_t)g_aspect << 8;',
'''(uint64_t)(uint32_t)g_aspect << 8
#ifdef HAKUX_XBOX2
                         | hakux_menu_key_revision() << 16
#endif
                         ;''')
replace('hw/xbox/hle/vk/swapchain.c','#include "hw/xbox/hle/vk/swapchain.h"',
        '#include "hw/xbox/hle/vk/swapchain.h"\n#include "hakux/menu.h"')
replace('hw/xbox/hle/vk/swapchain.c','''    if (f->ramp_stale) {
        memcpy(g_ps.ubo_map + (size_t)g_ps.cur * PS_RAMP, g_ps.ramp, 768);''',
'''#ifdef HAKUX_XBOX2
    /* The acquired frame's buffer is no longer in flight (present_begin). */
    hakux_menu_ramp((uint8_t (*)[256])(g_ps.ubo_map + (size_t)g_ps.cur * PS_RAMP), g_ps.ramp);
#endif
    if (f->ramp_stale) {
#ifndef HAKUX_XBOX2
        memcpy(g_ps.ubo_map + (size_t)g_ps.cur * PS_RAMP, g_ps.ramp, 768);
#endif''')
replace('hw/xbox/hle/vk/swapchain.c','''    T.vkCmdEndRendering(cb);
    barrier(cb, dst, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,''',
'''#ifdef HAKUX_XBOX2
    hakux_menu_draw(cb, &T, iw, ih);
#endif
    T.vkCmdEndRendering(cb);
    barrier(cb, dst, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,''')
