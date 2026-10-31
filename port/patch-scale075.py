#!/usr/bin/env python3
"""Add a separate 0.75x GLSL decoder, preserving older scales' shader text."""
from pathlib import Path
root=Path(__file__).resolve().parent

def edit(name,old,new):
    p=root/'source'/name
    s=p.read_text()
    if new in s:return
    if old not in s:raise SystemExit('0.75x patch context missing: '+name)
    p.write_text(s.replace(old,new,1))

edit('hw/xbox/hle/shader/ff.h','extern bool g_hle_glsl_scale035;',r'''extern bool g_hle_glsl_scale035;
extern bool g_hle_glsl_scale075;
#define HLE_SCALE_075_GLSL "float nvScale(uint n) { return n == 130u ? 0.75 : n == 129u ? 0.35 : n == 128u ? 0.5 : float(max(n, 1u)); }\n"
#define HLE_PUSH_075_GLSL \
    "layout(push_constant, std430) uniform Push {\n" HLE_PUSH_MEMBERS_GLSL "} pc;\n" HLE_SCALE_075_GLSL
#define HLE_PUSH_SSBO_075_GLSL \
    "layout(set = 3, binding = 0, std430) readonly buffer Push {\n" HLE_PUSH_MEMBERS_GLSL "} pc;\n" HLE_SCALE_075_GLSL''')
edit('hw/xbox/hle/shader/ff.h',
     '    if (!g_hle_glsl_scale035) {',
'''    if (g_hle_glsl_scale075) {
        return g_hle_push_ssbo ? HLE_PUSH_SSBO_075_GLSL : HLE_PUSH_075_GLSL;
    }
    if (!g_hle_glsl_scale035) {''')
edit('hw/xbox/hle/shader/ff_gen.c',
     'bool g_hle_glsl_scale035;                /* ff.h */',
'''bool g_hle_glsl_scale035;                /* ff.h */
bool g_hle_glsl_scale075;                /* ff.h */''')
edit('hw/xbox/hle/vk/draw.c',
     '    g_hle_glsl_scale035 = hle_scale_code(hle_host_render_scale()) == 129u;',
'''    g_hle_glsl_scale035 = hle_scale_code(hle_host_render_scale()) == 129u;
    g_hle_glsl_scale075 = hle_scale_code(hle_host_render_scale()) == 130u;''')
