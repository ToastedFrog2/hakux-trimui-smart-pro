#!/usr/bin/env python3
"""Keep the verified 0.5x shader text/cache keys when adding 0.35x support."""
from pathlib import Path
root = Path(__file__).resolve().parent
def replace(name, old, new):
    p = root/'source'/name
    text = p.read_text()
    if new in text:
        return
    # Later scale patches extend this declaration block. Its stable marker
    # prevents reinserting the old block on a rebuild.
    if name == 'hw/xbox/hle/shader/ff.h' and old == 'extern bool g_hle_push_ssbo;' and 'extern bool g_hle_glsl_scale035;' in text:
        return
    if old not in text:
        raise SystemExit('Shader compatibility context missing: '+name)
    p.write_text(text.replace(old, new))

replace('hw/xbox/hle/shader/ff.h',
        'extern bool g_hle_push_ssbo;',
'''extern bool g_hle_push_ssbo;
/* Set before pipeline prebuild; a scale change restarts the process. */
extern bool g_hle_glsl_scale035;
#define HLE_SCALE_05_GLSL "float nvScale(uint n) { return n == 128u ? 0.5 : float(max(n, 1u)); }\\n"
#define HLE_PUSH_05_GLSL \\
    "layout(push_constant, std430) uniform Push {\\n" HLE_PUSH_MEMBERS_GLSL "} pc;\\n" HLE_SCALE_05_GLSL
#define HLE_PUSH_SSBO_05_GLSL \\
    "layout(set = 3, binding = 0, std430) readonly buffer Push {\\n" HLE_PUSH_MEMBERS_GLSL "} pc;\\n" HLE_SCALE_05_GLSL''')
replace('hw/xbox/hle/shader/ff.h',
'''    return g_hle_push_ssbo ? HLE_PUSH_SSBO_GLSL : HLE_PUSH_GLSL;''',
'''    if (!g_hle_glsl_scale035) {
        return g_hle_push_ssbo ? HLE_PUSH_SSBO_05_GLSL : HLE_PUSH_05_GLSL;
    }
    return g_hle_push_ssbo ? HLE_PUSH_SSBO_GLSL : HLE_PUSH_GLSL;''')
replace('hw/xbox/hle/shader/ff_gen.c',
        'bool g_hle_push_ssbo;                   /* ff.h */',
'''bool g_hle_push_ssbo;                   /* ff.h */
bool g_hle_glsl_scale035;                /* ff.h */''')
replace('hw/xbox/hle/vk/draw.c',
        '    g_hle_push_ssbo = !g_hvk.caps.push;     /* before any shader is made */',
'''    g_hle_push_ssbo = !g_hvk.caps.push;     /* before any shader is made */
    /* Device scale is configured before this init; cmd_device has not run
     * yet, so g_hle_rscale still has its default. Use the requested scale. */
    g_hle_glsl_scale035 = hle_scale_code(hle_host_render_scale()) == 129u;''')
