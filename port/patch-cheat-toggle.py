#!/usr/bin/env python3
"""Add reversible single-byte native cheat flags without changing existing codes."""
from pathlib import Path
p=Path(__file__).resolve().parent/'source/native/core/cheats.c'
s=p.read_text()
def replace(old,new):
 global s
 if new in s:return
 if old not in s:raise SystemExit('Cheat toggle patch context missing')
 s=s.replace(old,new,1)
replace('enum { OP_W, OP_IF, OP_ELSE, OP_END };','enum { OP_W, OP_IF, OP_ELSE, OP_END, OP_TOGGLE };')
replace("    uint32_t v;                 /* the value's bits */","    uint32_t v;                 /* the value's bits */\n    uint8_t saved;              /* toggle8: original flag, owned by the guest thread */\n    bool armed;")
replace('    char word[8];','    char word[16];')
replace('        const bool is_if = !strncmp(word, "if", 2);\n        const char *t = word + (is_if ? 2 : 1);\n        if (!is_if && word[0] != \'w\') {','        const bool is_if = !strncmp(word, "if", 2);\n        const bool toggle = !strcmp(word,"toggle8");\n        const char *t = toggle ? "8" : word + (is_if ? 2 : 1);\n        if (!is_if && !toggle && word[0] != \'w\') {')
replace('        op.kind = is_if ? OP_IF : OP_W;','        op.kind = toggle ? OP_TOGGLE : is_if ? OP_IF : OP_W;')
replace('        if (is_if && !comparison(&p, &op.cmp)) {','        if (toggle && op.a.steps) return fail(err,errlen,"toggle8 requires a fixed address");\n        if (is_if && !comparison(&p, &op.cmp)) {')
replace('        const Op *op = &g_ops[c->first + i];','        Op *op = &g_ops[c->first + i];')
replace('            if (memcmp(cur, b, op->width)) {','            if (op->kind==OP_TOGGLE && !op->armed) {op->saved=cur[0];op->armed=true;}\n            if (memcmp(cur, b, op->width)) {')
replace('unsigned nc_cheats_run(const NcCheatMem *m)\n{','/* Restore only flags this cheat changed, and only while they still hold\n * our value. Never overwrite a different value the game has since chosen. */\nstatic unsigned restore_toggles(Cheat *c, const NcCheatMem *m)\n{\n    unsigned wrote=0;\n    for(unsigned i=0;i<c->n;i++) {\n        Op *op=&g_ops[c->first+i];\n        if(op->kind!=OP_TOGGLE || !op->armed) continue;\n        uint8_t cur;\n        if(!m->read(m->opaque,op->a.base,&cur,1)) continue;\n        if(cur==op->v && cur!=op->saved) {\n            if(!m->write(m->opaque,op->a.base,&op->saved,1)) continue;\n            wrote++;\n        }\n        op->armed=false;\n    }\n    return wrote;\n}\n\nunsigned nc_cheats_run(const NcCheatMem *m)\n{')
replace('        if (!__atomic_load_n(&c->on, __ATOMIC_ACQUIRE)) {\n            continue;','        if (!__atomic_load_n(&c->on, __ATOMIC_ACQUIRE)) {\n            wrote += restore_toggles(c,m);\n            continue;')
p.write_text(s)
