#!/usr/bin/env python3
"""Bound GPU hangs and avoid global teardown racing live Vulkan workers."""
from pathlib import Path
root=Path(__file__).resolve().parent
def replace(name,old,new):
    p=root/'source'/name;s=p.read_text()
    if new in s:return
    if old not in s:raise SystemExit('Recovery patch context missing: '+name)
    p.write_text(s.replace(old,new))
replace('native/run/xboxrun.c','#include "hakux/menu.h"',
        '#include "hakux/menu.h"\n#include "hakux/gpu_progress.h"')
replace('native/run/xboxrun.c','''    uint64_t frames = hle_back_swap_count(), since = mono_ms();
    for (;;) {''','''    uint64_t frames = hle_back_swap_count(), since = mono_ms();
#ifdef HAKUX_XBOX2
    HakuxGpuProgress gpu = {0};
#endif
    for (;;) {''')
replace('native/run/xboxrun.c','''        const uint64_t n = hle_back_swap_count(), now = mono_ms();
        if (n != frames) {''','''        const uint64_t n = hle_back_swap_count(), now = mono_ms();
#ifdef HAKUX_XBOX2
        const uint64_t submitted = hle_tl_submitted(), completed = hle_tl_completed();
        if (hakux_gpu_stalled(&gpu, now, submitted, completed, 15000)) {
            nc_log("hakuX-native-frontier", "GPU recovery: no completion for 15 s (%llu/%llu); returning to launcher",
                   (unsigned long long)completed, (unsigned long long)submitted);
            _exit(9);
        }
#endif
        if (n != frames) {''')
replace('native/run/xboxrun.c',
'''    return k->quit || k->relaunch ? 10 : k->stop ? 7 : 0;''',
'''    const int result = k->quit || k->relaunch ? 10 : k->stop ? 7 : 0;
#ifdef HAKUX_XBOX2
    /* SDL/Vulkan/FEX worker threads are still live. Let the kernel close
     * their descriptors together; the shell restores MainUI and syncs. */
    _exit(result);
#else
    return result;
#endif''')
