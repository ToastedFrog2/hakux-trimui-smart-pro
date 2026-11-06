#!/usr/bin/env python3
"""Enable the depth-EQUAL step tolerance on PowerVR (Halo 2's black geometry)."""
from pathlib import Path
p=Path(__file__).resolve().parent/'source/hw/xbox/hle/vk/quirks.c'
original=p.read_text()
s=original
old='''static bool mali_g615(const HleDriver *d)'''
new='''/* PowerVR (vendor 0x1010), any driver */
static bool powervr(const HleDriver *d)
{
    return d->props.vendorID == 0x1010;
}

static bool turnip_or_powervr(const HleDriver *d)
{
    return mesa_turnip(d) || powervr(d);
}

static bool mali_g615(const HleDriver *d)'''
if new not in s:
    assert old in s
    s=s.replace(old,new,1)
old='''    { HLE_QUIRK_EQ_DEPTH_STEP, "eq_depth_step", mesa_turnip },'''
new='''    /* PowerVR GE8300 driver 1.19@6345021 (TrimUI Smart Pro): Halo 2's level
     * geometry drew black, the sky showing through, its lighting passes
     * missing the base pass's depth; on, it drew right (2026-11-03). */
    { HLE_QUIRK_EQ_DEPTH_STEP, "eq_depth_step", turnip_or_powervr },'''
if new not in s:
    assert old in s
    s=s.replace(old,new,1)
if s!=original:
    p.write_text(s)
