#!/usr/bin/env python3
"""Fractional render extents with matched shader, copy and readback coordinates."""
from pathlib import Path
root=Path(__file__).resolve().parent
def replace(name,old,new):
    p=root/'source'/name; text=p.read_text()
    if new in text: return
    if old not in text: raise SystemExit(f'Half-scale context missing: {name}: {old[:90]}')
    p.write_text(text.replace(old,new))

replace('native/hle/hle_native.h','nc_hle_set_render_scale(int scale)','nc_hle_set_render_scale(float scale)')
replace('hw/xbox/hle/host.h','int hle_host_render_scale(void);','float hle_host_render_scale(void);')
replace('native/hle/host_native.c','#include <dlfcn.h>','#include <dlfcn.h>\n#include "hakux/render_scale.h"')
replace('native/hle/host_native.c', '''static int g_render_scale = 1;

void nc_hle_set_render_scale(int scale)
{
    g_render_scale = scale < 1 ? 1 : scale > 4 ? 4 : scale;
}

int hle_host_render_scale(void)''', '''static float g_render_scale = 1.0f;

void nc_hle_set_render_scale(float scale)
{
    g_render_scale = hle_scale_clamp(scale);
}

float hle_host_render_scale(void)''')
replace('native/core/options.c','nc_hle_set_render_scale(atoi(v));','nc_hle_set_render_scale(strtof(v, NULL));')
replace('native/core/options.c', '''    *o = (NcOptions){ .async_pipe = true, .prebuild = true, .video = -1, .av_pack = NC_AV_PACK_HDTV };''',
'''    *o = (NcOptions){ .async_pipe = true, .prebuild = true, .video = -1, .av_pack = NC_AV_PACK_HDTV };
    const char *scale = getenv("HAKUX_RENDER_SCALE");
    if (scale) nc_hle_set_render_scale(strtof(scale, NULL));''')
replace('hw/xbox/hle/vk/back_int.h', 'extern uint32_t g_hle_rscale;',
        '#include "hakux/render_scale.h"\nextern float g_hle_rscale;')
replace('hw/xbox/hle/vk/back_int.h','    uint32_t scale;             /* host pixels per guest pixel',
        '    float scale;                /* host pixels per guest pixel')
replace('hw/xbox/hle/vk/surf.c','static uint32_t surf_scale(', 'static float surf_scale(')
replace('hw/xbox/hle/vk/surf.c', '''    return small ? 1 : g_hle_rscale;''',
'''    /* Keep paired small swizzled colour/depth targets at guest resolution. */
    bool small_half = g_hle_rscale < 1.0f && !d->role && !d->pitch && !d->parent &&
                      d->levels <= 1 && d->faces <= 1 && MAX(d->w,d->h) <= SURF_UNSCALED_MAX;
    return small || small_half ? 1.0f : g_hle_rscale;''')
replace('hw/xbox/hle/vk/surf.c','s->w = d->w * s->scale;', 's->w = hle_scale_extent(d->w, s->scale);')
replace('hw/xbox/hle/vk/surf.c','s->h = d->h * s->scale;', 's->h = hle_scale_extent(d->h, s->scale);')
replace('hw/xbox/hle/vk/back.c','uint32_t g_hle_rscale = 1;', 'float g_hle_rscale = 1.0f;')
replace('hw/xbox/hle/vk/back.c','uint32_t scale = MIN(MAX(hle_host_render_scale(), 1), 4);',
        'float scale = hle_scale_clamp(hle_host_render_scale());')
replace('hw/xbox/hle/vk/back.c','hle_disp_init(c->disp_w * scale, c->disp_h * scale);',
        'hle_disp_init(hle_scale_extent(c->disp_w, scale), hle_scale_extent(c->disp_h, scale));')
replace('hw/xbox/hle/vk/back.c','surfaces=%u present=%u scale=%u', 'surfaces=%u present=%u scale=%.2f')
replace('hw/xbox/hle/vk/back.c', 'uint32_t index, div, nparts, parts[VIS_MAX_PARTS];',
        'uint32_t index, div, nparts, parts[VIS_MAX_PARTS];\n        float scale;')
replace('hw/xbox/hle/vk/back.c', '''    uint32_t vsc = vrt ? vrt->scale : g_hle_rscale;
    p->div = MAX(c->div, 1u) * vsc * vsc;               /* guest pixels */''',
'''    p->scale = vrt ? vrt->scale : g_hle_rscale;
    p->div = MAX(c->div, 1u);                         /* guest sample divisor */''')
replace('hw/xbox/hle/vk/back.c','uint32_t count = (uint32_t)(sum / p->div);',
        'uint32_t count = hle_scale_samples(sum, p->div, p->scale);')
replace('hw/xbox/hle/vk/back.c','(parts %u, div %u, report', '(parts %u, div %g, report')
replace('hw/xbox/hle/vk/back.c','p->index, count, p->nparts, p->div, p->report,',
        'p->index, count, p->nparts, (double)p->div * p->scale * p->scale, p->report,')
replace('hw/xbox/hle/vk/back.c','uint32_t sc = rt->scale, gx = g_pix.host ? g_pix.x / sc : g_pix.x;',
        'float sc = rt->scale;\n    uint32_t gx = g_pix.host ? g_pix.x / sc : g_pix.x;')
replace('hw/xbox/hle/vk/back.c','uint32_t w = rt->w, h = rt->h, sc = rt->scale;',
        'uint32_t w = rt->w, h = rt->h;\n    float sc = rt->scale;')
replace('hw/xbox/hle/vk/back.c', '''            int32_t x1 = MAX(c->rect[i].x1 * (int32_t)sc, 0);
            int32_t y1 = MAX(c->rect[i].y1 * (int32_t)sc, 0);
            int32_t x2 = MIN(c->rect[i].x2 * (int32_t)sc, (int32_t)w);
            int32_t y2 = MIN(c->rect[i].y2 * (int32_t)sc, (int32_t)h);''',
'''            HleScaledRect sr = hle_scale_rect(c->rect[i].x1,c->rect[i].y1,
                                               c->rect[i].x2,c->rect[i].y2,sc,w,h);
            int32_t x1 = sr.x, y1 = sr.y, x2 = sr.x + sr.w, y2 = sr.y + sr.h;''')
replace('hw/xbox/hle/vk/back.c','int32_t sc = (int32_t)(rt ? rt->scale : ds->scale);',
        'float sc = rt ? rt->scale : ds->scale;')
replace('hw/xbox/hle/vk/back.c', '''        int32_t x1 = MAX(c->rect[i].x1 * sc, 0), y1 = MAX(c->rect[i].y1 * sc, 0);
        int32_t x2 = MIN(c->rect[i].x2 * sc, (int32_t)w);
        int32_t y2 = MIN(c->rect[i].y2 * sc, (int32_t)h);''',
'''        HleScaledRect sr = hle_scale_rect(c->rect[i].x1,c->rect[i].y1,
                                           c->rect[i].x2,c->rect[i].y2,sc,w,h);
        int32_t x1 = sr.x, y1 = sr.y, x2 = sr.x + sr.w, y2 = sr.y + sr.h;''')
replace('hw/xbox/hle/vk/back.c','MIN(src->w, c->src_w * src->scale)', 'MIN(src->w, hle_scale_extent(c->src_w, src->scale))')
replace('hw/xbox/hle/vk/back.c','MIN(src->h, c->src_h * src->scale)', 'MIN(src->h, hle_scale_extent(c->src_h, src->scale))')
replace('hw/xbox/hle/vk/back.c','if (o->scale > 1) {', 'if (o->scale != 1.0f) {')
replace('hw/xbox/hle/vk/back.c','if (s->scale > 1 || w != s->d.w || h != s->d.h)',
        'if (s->scale != 1.0f || w != s->d.w || h != s->d.h)')
replace('hw/xbox/hle/vk/back.c','int32_t k = (int32_t)s->scale, kd = (int32_t)d->scale;',
        'float k = s->scale, kd = d->scale;\n    bool same_extents = true;')
replace('hw/xbox/hle/vk/back.c', '''        int32_t w = MIN(MIN(r->x2, (int32_t)s->w / k) - r->x1, (int32_t)d->w / kd - c->x[i]);
        int32_t h = MIN(MIN(r->y2, (int32_t)s->h / k) - r->y1, (int32_t)d->h / kd - c->y[i]);''',
'''        int32_t w = MIN(MIN(r->x2, (int32_t)s->d.w) - r->x1, (int32_t)d->d.w - c->x[i]);
        int32_t h = MIN(MIN(r->y2, (int32_t)s->d.h) - r->y1, (int32_t)d->d.h - c->y[i]);''')
old='''        cr[n] = (VkImageCopy2){
            .sType = VK_STRUCTURE_TYPE_IMAGE_COPY_2,
            .srcSubresource = ss, .srcOffset = { r->x1 * k, r->y1 * k, 0 },
            .dstSubresource = ds, .dstOffset = { c->x[i] * k, c->y[i] * k, 0 },
            .extent = { (uint32_t)(w * k), (uint32_t)(h * k), 1 } };
        br[n] = (VkImageBlit2){
            .sType = VK_STRUCTURE_TYPE_IMAGE_BLIT_2,
            .srcSubresource = ss,
            .srcOffsets = { { r->x1 * k, r->y1 * k, 0 }, { (r->x1 + w) * k, (r->y1 + h) * k, 1 } },
            .dstSubresource = ds,
            .dstOffsets = { { c->x[i] * kd, c->y[i] * kd, 0 },
                            { (c->x[i] + w) * kd, (c->y[i] + h) * kd, 1 } } };'''
new='''        HleScaledRect sr = hle_scale_rect(r->x1,r->y1,r->x1+w,r->y1+h,k,s->w,s->h);
        HleScaledRect dr = hle_scale_rect(c->x[i],c->y[i],c->x[i]+w,c->y[i]+h,kd,d->w,d->h);
        if (!sr.w || !sr.h || !dr.w || !dr.h) continue;
        if (s->img == d->img && sr.x == dr.x && sr.y == dr.y && sr.w == dr.w && sr.h == dr.h) continue;
        same_extents &= sr.w == dr.w && sr.h == dr.h;
        cr[n] = (VkImageCopy2){
            .sType = VK_STRUCTURE_TYPE_IMAGE_COPY_2,
            .srcSubresource = ss, .srcOffset = { sr.x, sr.y, 0 },
            .dstSubresource = ds, .dstOffset = { dr.x, dr.y, 0 },
            .extent = { sr.w, sr.h, 1 } };
        br[n] = (VkImageBlit2){
            .sType = VK_STRUCTURE_TYPE_IMAGE_BLIT_2,
            .srcSubresource = ss,
            .srcOffsets = { {sr.x,sr.y,0}, {sr.x+(int32_t)sr.w,sr.y+(int32_t)sr.h,1} },
            .dstSubresource = ds,
            .dstOffsets = { {dr.x,dr.y,0}, {dr.x+(int32_t)dr.w,dr.y+(int32_t)dr.h,1} } };'''
replace('hw/xbox/hle/vk/back.c',old,new)
replace('hw/xbox/hle/vk/back.c','if (s->fmt == d->fmt && k == kd) {', 'if (s->fmt == d->fmt && k == kd && same_extents) {')
replace('hw/xbox/hle/vk/back.c','int32_t k = d ? (int32_t)MAX(d->scale, 1u) : 1, n = 0;',
        'float k = d ? d->scale : 1.0f;\n    int32_t n = 0;')
replace('hw/xbox/hle/vk/back.c','(int32_t)d->w / k - c->x[i]', '(int32_t)d->d.w - c->x[i]')
replace('hw/xbox/hle/vk/back.c','(int32_t)d->h / k - c->y[i]', '(int32_t)d->d.h - c->y[i]')
replace('hw/xbox/hle/vk/back.c', '''            .dstOffsets = { { c->x[i] * k, c->y[i] * k, 0 },
                            { (c->x[i] + w) * k, (c->y[i] + h) * k, 1 } } };''',
'''            .dstOffsets = { { hle_scale_lo(c->x[i],k), hle_scale_lo(c->y[i],k), 0 },
                            { hle_scale_hi(c->x[i]+w,k), hle_scale_hi(c->y[i]+h,k), 1 } } };''')
replace('hw/xbox/hle/vk/draw.c', 'uint32_t rs = rt ? rt->scale : ds->scale;', 'float rs = rt ? rt->scale : ds->scale;')
replace('hw/xbox/hle/vk/draw.c', '''    VkRect2D sc = full ? (VkRect2D){ { 0, 0 }, { sw, sh } } :
                         (VkRect2D){ { (int32_t)(vpc->x * rs), (int32_t)(vpc->y * rs) },
                                     { vpc->w * rs, vpc->h * rs } };''',
'''    HleScaledRect vr = hle_scale_rect(vpc->x,vpc->y,vpc->x+vpc->w,vpc->y+vpc->h,rs,sw,sh);
    VkRect2D sc = full ? (VkRect2D){ {0,0}, {sw,sh} } :
                         (VkRect2D){ {vr.x,vr.y}, {vr.w,vr.h} };''')
replace('hw/xbox/hle/vk/draw.c', '''        sc = (VkRect2D){ { x1 * (int32_t)rs, y1 * (int32_t)rs },
                         { x2 > x1 ? (uint32_t)(x2 - x1) * rs : 0,
                           y2 > y1 ? (uint32_t)(y2 - y1) * rs : 0 } };''',
'''        HleScaledRect cr = hle_scale_rect(x1,y1,x2,y2,rs,sw,sh);
        sc = (VkRect2D){ {cr.x,cr.y}, {cr.w,cr.h} };''')
replace('hw/xbox/hle/vk/draw.c', 'MIN(rs, 255u) << 16 | MIN(g_hle_rscale, 255u) << 24',
        'hle_scale_code(rs) << 16 | hle_scale_code(g_hle_rscale) << 24')
replace('hw/xbox/hle/vk/zread.c', 'halves ? dst->scale : map[1]', 'halves ? hle_scale_code(dst->scale) : map[1]')

# Decode the scale byte consistently in all generated shaders, including the
# fallback storage-buffer push block. Old codes (0..4) keep their semantics.
if '#define HLE_SCALE_GLSL ' not in (root/'source/hw/xbox/hle/shader/ff.h').read_text():
    replace('hw/xbox/hle/shader/ff.h', '#define HLE_PUSH_GLSL',
'''#define HLE_SCALE_GLSL "float nvScale(uint n) { return n == 128u ? 0.5 : float(max(n, 1u)); }\\n"
#define HLE_PUSH_GLSL''')
replace('hw/xbox/hle/shader/ff.h',
        'return n == 128u ? 0.5 : float(max(n, 1u));',
        'return n == 129u ? 0.35 : n == 128u ? 0.5 : float(max(n, 1u));')
replace('hw/xbox/hle/shader/ff.h', 'HLE_PUSH_MEMBERS_GLSL "} pc;\\n"',
        'HLE_PUSH_MEMBERS_GLSL "} pc;\\n" HLE_SCALE_GLSL')
replace('hw/xbox/hle/shader/ff.h', 'uint rsc = (pc.flags >> 16) & 255u;', 'float rsc = nvScale((pc.flags >> 16) & 255u);')
replace('hw/xbox/hle/shader/ff.h', 'if (rsc > 1u &&', 'if (rsc > 1.0 &&')
replace('hw/xbox/hle/shader/ff_gen.c', 'float(max((pc.flags >> 16) & 255u, 1u))', 'nvScale((pc.flags >> 16) & 255u)')
replace('hw/xbox/hle/shader/vsh.c', 'float(max((pc.flags >> 16) & 255u, 1u))', 'nvScale((pc.flags >> 16) & 255u)')
for path in ['hw/xbox/hle/shader/psh.c','hw/xbox/hle/shader/ff_gen.c']:
    replace(path, 'float(pc.flags >> 24)', 'nvScale(pc.flags >> 24)')
replace('hw/xbox/hle/shader/ff_gen.c',
        'gl_PointSize = clamp(ps, f[%u].y, f[%u].z) * f[%u].w *',
        'gl_PointSize = max(clamp(ps, f[%u].y, f[%u].z) * f[%u].w *')
replace('hw/xbox/hle/shader/ff_gen.c',
        'nvScale((pc.flags >> 16) & 255u); }', 'nvScale((pc.flags >> 16) & 255u), 1.0); }')
replace('hw/xbox/hle/shader/vsh.c',
        'gl_PointSize = max(oPts.x, 1.0) * nvScale((pc.flags >> 16) & 255u);',
        'gl_PointSize = max(max(oPts.x, 1.0) * nvScale((pc.flags >> 16) & 255u), 1.0);')
