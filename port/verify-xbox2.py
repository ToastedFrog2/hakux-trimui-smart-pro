#!/usr/bin/env python3
"""Host checks for the actual optional renderer and shader implementation."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parent
os.chdir(root)
cc = os.environ.get('CC', 'cc')
sanitizers = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if os.environ.get('HAKUX_TEST_SANITIZE') else []
includes = ['-Isource', '-Iplatform', '-Iplatform/include', '-Isource/native/compat/glib',
            '-Ideps/volk', '-Ideps/Vulkan-Headers/include', '-Isource/tests/hle']
with tempfile.TemporaryDirectory(prefix='hakux-xbox2-check-') as tmp:
    for name, sources in (
        ('pscache', ['tests/xbox2-pscache.c', 'tests/xbox2-host-stubs.c']),
        ('batch', ['tests/xbox2-batch.c']),
        ('shader', ['source/tests/hle/test_psh.c', 'source/hw/xbox/hle/shader/psh.c',
                    'source/hw/xbox/hle/shader/ff_gen.c']),
    ):
        exe = str(Path(tmp) / name)
        subprocess.run([cc, '-std=gnu11', '-O2', '-DHLE_HOST_TEST=1', '-DVK_NO_PROTOTYPES',
                        *sanitizers, *includes, *sources, '-o', exe], check=True)
        subprocess.run([exe], check=True)

    # Exercise the actual draw.c stage-setup fragment in both compile modes.
    # Resource lookups are deterministic stand-ins; compare the complete
    # resulting shader key and push block, including FF point-sprite cases.
    draw = Path('source/hw/xbox/hle/vk/draw.c').read_text()
    enums = draw[draw.index('/* 5659 render-state indices'):draw.index('/* Two floats')]
    types = draw[draw.index('typedef struct ViKey {'):draw.index('/* The key\'s bytes hashed')]
    start = draw.index('    /* POINTSPRITEENABLE: the cascade')
    end = draw.index('        k.psh = 1;', start) + len('        k.psh = 1;')
    fragment = draw[start:end] + '\n    }\n'
    stage_test = Path(tmp) / 'stages.c'
    prefix = r'''
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "hw/xbox/hle/front/cmd.h"
#include "hw/xbox/hle/shader/ff.h"
#include "hw/xbox/hle/shader/vsh.h"
#include "hw/xbox/hle/shader/psh.h"
static unsigned stage_calls, sampler_calls;
static struct { HleCmdState st; } g_dr;
static unsigned shadow_fmt(uint32_t t) { return t && t % 13 == 0; }
static uint32_t stage_slot(const HleCmdDraw *c, unsigned st, uint32_t rt, uint32_t *flags) {
    stage_calls++; *flags |= (c->tex[st] & 1) << st; return c->tex[st] % 4096;
}
static uint32_t stage_lod_down(const HleCmdDraw *c, unsigned st, uint32_t rt) { return st * 16; }
static uint32_t sampler_index(const uint32_t *t, uint32_t lod) {
    sampler_calls++; return (t[0] + t[1] + lod) % 256;
}
static unsigned ff_fb_stages(const HleCmdDraw *c, uint32_t rt) { return g_dr.st.psh ? 0 : 5; }
'''
    def function(name):
        return f'''static Result {name}(const HleCmdDraw *c) {{
    const HleCmdState *s = &g_dr.st; uint32_t rt_id = 1;
    PipeKey k = {{0}}; HleFfPush pc = {{0}};
''' + fragment + '\n    return (Result){k, pc};\n}\n'
    main = r'''
static uint32_t seed = 0x927427;
static uint32_t rnd(void) { seed ^= seed<<13; seed ^= seed>>17; seed ^= seed<<5; return seed; }
int main(void) {
    for (unsigned n = 0; n < 20000; n++) {
        HleCmdDraw c = {0};
        for (unsigned st=0; st<4; st++) {
            c.tex[st] = rnd()%100;
            for (unsigned i=0; i<HLE_TSS_COUNT; i++) g_dr.st.tss[st][i] = rnd();
            g_dr.st.tss[st][TSS_COLOROP] = rnd()%5;
        }
        g_dr.st.rs[RS_POINTSPRITEENABLE] = rnd()%2;
        g_dr.st.psh = rnd()%2;
        stage_calls = sampler_calls = 0;
        Result a = baseline(&c);
        unsigned old_stages = stage_calls, old_samplers = sampler_calls;
        stage_calls = sampler_calls = 0;
        Result b = optimized(&c);
        assert(!memcmp(&a.key, &b.key, sizeof(a.key)));
        assert(!memcmp(&a.push, &b.push, sizeof(a.push)));
        if (g_dr.st.psh) { assert(stage_calls == 4 && sampler_calls == 4); }
        else { assert(stage_calls == old_stages && sampler_calls == old_samplers); }
    }
    puts("PASS stage setup: 20000 differential draws, identical shader keys/push data; programmable path prepares each stage once");
}
'''
    stage_test.write_text(prefix + enums + types +
                          '\ntypedef struct { PipeKey key; HleFfPush push; } Result;\n' +
                          function('baseline') + '\n#define HAKUX_XBOX2 1\n' + function('optimized') + main)
    exe = str(Path(tmp) / 'stages')
    subprocess.run([cc, '-std=gnu11', '-O2', '-DHLE_HOST_TEST=1', *sanitizers, *includes,
                    str(stage_test), '-o', exe], check=True)
    subprocess.run([exe], check=True)
