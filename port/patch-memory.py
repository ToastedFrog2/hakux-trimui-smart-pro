#!/usr/bin/env python3
"""Bound Xbox 2's resident startup pipelines without deleting disk caches."""
from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'source/hw/xbox/hle/vk/pipeasync.c'
original=p.read_text()
s=original
old='#include "hw/xbox/hle/vk/vkdev.h"'
new=old+'\n#ifdef HAKUX_XBOX2\n#include "hakux/prebuild_budget.h"\n#endif'
if new not in s:
    assert old in s
    s=s.replace(old,new)
old='    uint32_t n = MIN(g_pa.nlist, max);'
new='''#ifdef HAKUX_XBOX2
    max = hakux_prebuild_budget(max, getenv("HAKUX_HLE_PREBUILD_LIMIT"));
    hle_log("hakuX-hle-pipe", "TrimUI resident prebuild budget: %u (full disk record retained)", max);
#endif
    uint32_t n = MIN(g_pa.nlist, max);'''
if new not in s:
    assert old in s
    s=s.replace(old,new)
if s!=original:
    p.write_text(s)
