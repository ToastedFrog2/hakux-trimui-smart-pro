#!/usr/bin/env python3
"""Add live display-only frame skipping to the presenter's unchanged path."""
from pathlib import Path
p=Path(__file__).resolve().parent/'source/hw/xbox/hle/vk/swapchain.c'
s=p.read_text()
old='#include "hakux/menu.h"'
new=old+'\n#ifdef HAKUX_XBOX2\n#include "hakux/frame_skip.h"\nstatic HakuxFrameSkip g_frame_skip;\n#endif'
if new not in s:
    assert old in s
    s=s.replace(old,new,1)
# Match the full actual guard tail, preserving upstream window/gamma checks.
old='''(uint32_t)ANativeWindow_getHeight(win) != g_ps.wsize.height || hle_disp_gamma_seq() != g_ps.ramp_gen) {
        return false;'''
new='''(uint32_t)ANativeWindow_getHeight(win) != g_ps.wsize.height || hle_disp_gamma_seq() != g_ps.ramp_gen) {
#ifdef HAKUX_XBOX2
        hakux_frame_skip_reset(&g_frame_skip);
#endif
        return false;'''
if new not in s:
    assert old in s
    s=s.replace(old,new,1)
old='''    if (front != g_ps.have) {
        return false;
    }
    return !front || (gen == g_ps.f.gen && swap_id == g_ps.f.swap_id);'''
new='''    if (front != g_ps.have) {
#ifdef HAKUX_XBOX2
        hakux_frame_skip_reset(&g_frame_skip);
#endif
        return false;
    }
    if (!front || (gen == g_ps.f.gen && swap_id == g_ps.f.swap_id)) {
        return true;
    }
#ifdef HAKUX_XBOX2
    /* Skip final scanout/composition only. All Xbox rendering and display
     * pickup/vblank acknowledgement continue through nc_present_frame. */
    return hakux_frame_skip_display(&g_frame_skip, hakux_menu_frame_skip(), gen, swap_id);
#else
    return false;
#endif'''
if new not in s:
    assert old in s
    s=s.replace(old,new,1)
p.write_text(s)
