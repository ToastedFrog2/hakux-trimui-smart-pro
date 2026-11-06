#!/usr/bin/env python3
"""Apply MMIO/RIP decoding fixes, stereo default and a coarse-expiring TLS time cache."""
from pathlib import Path
root=Path(__file__).resolve().parent/'source'
def replace(name,old,new):
    p=root/name;s=p.read_text()
    if new in s:return
    if old not in s:raise SystemExit('Safe vCPU patch context missing: '+name)
    p.write_text(s.replace(old,new,1))

replace('external/fex/FEXCore/Source/Interface/Core/OpcodeDispatcher.h',
'      if (TableInfo->Flags & X86Tables::InstFlags::FLAGS_DEBUG_MEM_ACCESS) {',
'      if (TableInfo->Flags & (X86Tables::InstFlags::FLAGS_DEBUG_MEM_ACCESS | X86Tables::InstFlags::FLAGS_MEM_OFFSET)) {')

replace('native/kernel/x86mmio.c',
'void nc_x86mmio_note(uint32_t eip)\n{\n    if (!eip || eip >= 0x80000000u) {\n        return; /* title code only (the slot marker of a removed site is the top bit) */\n    }\n    const unsigned n = g_npending;\n    if (n < PENDING) {\n        g_pending[n] = eip;\n        g_npending = n + 1;\n    }\n}',
'void nc_x86mmio_note(uint32_t eip)\n{\n    if (!eip || eip >= 0x80000000u) {\n        return; /* title code only (the slot marker of a removed site is the top bit) */\n    }\n    const unsigned s = slot_of(eip);\n    if (s < SITES && g_site[s] == eip) {\n        return;\n    }\n    const unsigned d = slot_of(eip | 0x80000000u);\n    if (d < SITES && g_site[d] == (eip | 0x80000000u) && g_strikes[d] >= MAX_STRIKE) {\n        return;\n    }\n    const unsigned n = g_npending;\n    for (unsigned i = 0; i < n; i++) {\n        if (g_pending[i] == eip) {\n            return;\n        }\n    }\n    if (n < PENDING) {\n        g_pending[n] = eip;\n        g_npending = n + 1;\n    }\n}')

replace('native/kernel/x86mmio.c',
'static bool decode(NcKernel *k, NcFrame *f, const uint8_t *p, Op *op)\n{\n    unsigned i = 0;\n    bool op16 = false;\n    uint32_t seg = 0;\n    for (;; i++) {\n        if (i >= 4) {\n            return false;\n        }\n        if (p[i] == 0x66) {\n            op16 = true;\n        } else if (p[i] == 0x64) {\n            seg = k->kpcr_va; /* FS: the KPCR */\n        } else if (p[i] == 0x2E || p[i] == 0x36 || p[i] == 0x3E || p[i] == 0x26) {\n            /* flat */\n        } else {\n            break;\n        }\n    }\n    memset(op, 0, sizeof(*op));\n    const uint8_t opc = p[i++];\n    unsigned mlen;\n    switch (opc) {\n    case 0x8B: case 0x89: case 0x8A: case 0x88:\n        if (!modrm_addr(f, p + i, &mlen, &op->addr, &op->reg)) {\n            return false;\n        }\n        i += mlen;\n        op->store = opc == 0x89 || opc == 0x88;\n        op->bytes = (opc & 1) ? (op16 ? 2 : 4) : 1;\n        break;',
'static uint32_t get_reg(NcFrame *f, int reg, unsigned bytes);\n\nstatic bool decode(NcKernel *k, NcFrame *f, const uint8_t *p, Op *op)\n{\n    unsigned i = 0;\n    bool op16 = false;\n    uint32_t seg = 0;\n    for (;; i++) {\n        if (i >= 4) {\n            return false;\n        }\n        if (p[i] == 0x66) {\n            op16 = true;\n        } else if (p[i] == 0x64) {\n            seg = k->kpcr_va; /* FS: the KPCR */\n        } else if (p[i] == 0x2E || p[i] == 0x36 || p[i] == 0x3E || p[i] == 0x26) {\n            /* flat */\n        } else {\n            break;\n        }\n    }\n    memset(op, 0, sizeof(*op));\n    const uint8_t opc = p[i++];\n    unsigned mlen;\n    switch (opc) {\n    case 0x8B: case 0x89: case 0x8A: case 0x88:\n        if (!modrm_addr(f, p + i, &mlen, &op->addr, &op->reg)) {\n            return false;\n        }\n        i += mlen;\n        op->store = opc == 0x89 || opc == 0x88;\n        op->bytes = (opc & 1) ? (op16 ? 2 : 4) : 1;\n        break;\n    case 0x85: case 0x84:                       /* TEST r/m, r */\n    case 0x39: case 0x38:                       /* CMP r/m, r */\n    case 0x3B: case 0x3A:                       /* CMP r, r/m */\n        if (!modrm_addr(f, p + i, &mlen, &op->addr, &op->reg)) {\n            return false;\n        }\n        i += mlen;\n        op->cmp = (opc == 0x85 || opc == 0x84) ? 1 : (opc == 0x3B || opc == 0x3A) ? 3 : 2;\n        op->bytes = (opc & 1) ? (op16 ? 2 : 4) : 1;\n        op->immv = get_reg(f, op->reg, op->bytes);\n        break;')

replace('native/kernel/x86mmio.c',
'    if (op.cmp) {\n        nc_frame_set_eflags(f, cmp_flags(nc_frame_eflags(f), op.cmp, (uint32_t)v, op.immv, op.bytes));\n        nc_frame_set_eip(f, eip + op.len);\n        return true;\n    }',
'    if (op.cmp) {\n        const uint32_t lhs = op.cmp == 3 ? op.immv : (uint32_t)v;\n        const uint32_t rhs = op.cmp == 3 ? (uint32_t)v : op.immv;\n        nc_frame_set_eflags(f, cmp_flags(nc_frame_eflags(f), op.cmp == 1 ? 1 : 2, lhs, rhs, op.bytes));\n        nc_frame_set_eip(f, eip + op.len);\n        return true;\n    }')

replace('native/core/mmio.c',
'    g_total++;\n    count(addr, store, *v);\n    return true;',
'    g_total++;\n    static int s_tally = -1;\n    if (__builtin_expect(s_tally < 0, 0)) {\n        const char *e = getenv("NC_MMIO_STATS");\n        s_tally = e && atoi(e) != 0;\n    }\n    if (__builtin_expect(s_tally, 0)) {\n        count(addr, store, *v);\n    }\n    return true;')

replace('native/dev/apu/apu.c',
'ApuConfig g_apu_config = {\n    .use_dsp = false,\n    .hrtf = true,\n    .volume_limit = 1.0f,\n    .num_workers = 0,\n};',
'ApuConfig g_apu_config = {\n    .use_dsp = false,\n#ifdef HAKUX_XBOX2\n    .hrtf = false,\n#else\n    .hrtf = true,\n#endif\n    .volume_limit = 1.0f,\n    .num_workers = 0,\n};')

replace('native/kernel/ke.c','static pthread_t g_entry_thread;\nstatic bool g_entry;','/* HAKUX_SAFE_TIME_CACHE: preserve coarse-tick expiry inside long entries. */\nstatic __thread bool t_in_entry;')

replace('native/kernel/ke.c','const bool mine = __atomic_load_n(&g_entry, __ATOMIC_RELAXED) &&\n                      pthread_equal(pthread_self(), g_entry_thread);','const bool mine = t_in_entry;')

replace('native/kernel/ke.c','    g_entry_thread = pthread_self();\n    g_entry_ns = 0;\n    __atomic_store_n(&g_entry, true, __ATOMIC_RELAXED);','    g_entry_ns = 0;\n    t_in_entry = true;')

replace('native/kernel/ke.c','    __atomic_store_n(&g_entry, false, __ATOMIC_RELAXED);','    t_in_entry = false;')
