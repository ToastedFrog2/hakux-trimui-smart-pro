#!/usr/bin/env python3
"""Let Halo 2 use its signed profile progress instead of legacy forced values."""
from pathlib import Path
p=Path(__file__).resolve().parent/'source/native/core/xbe_load.c'
s=p.read_text()
old='''            if (k_patches[i].title != x->title_id) {'''
new='''#ifdef HAKUX_XBOX2
            /* The old 0x68 override capped campaign selection at Cairo Station
             * and interfered with imported completed profiles. Native signed
             * saves contain the correct campaign progress. */
            if (k_patches[i].title == 0x4d530064u) {
                continue;
            }
#endif
            if (k_patches[i].title != x->title_id) {'''
if new not in s:
    assert old in s
    p.write_text(s.replace(old,new,1))
