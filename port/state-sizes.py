#!/usr/bin/env python3
"""Refresh host struct sizes for glibc, retaining all savestate field checks.

Unlike upstream's stdout assembly probe, this also works with Zig's compiler.
"""
import json, re, shlex, subprocess, tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
found = {}
with tempfile.TemporaryDirectory(prefix='hakux-state-') as tmp:
    asm = Path(tmp) / 'record.s'
    for entry in json.loads((root/'build/core/compile_commands.json').read_text()):
        source = Path(entry['file'])
        if 'native/state/def.h' not in source.read_text(errors='replace'): continue
        args = shlex.split(entry['command'])
        # Probe target assembly even when the release build emits LTO bitcode.
        args = [a for a in args if not a.startswith('-flto')]
        i = args.index('-o'); del args[i:i+2]
        args.remove('-c')
        subprocess.run(args+['-DNC_STATE_PROBE','-S','-o',str(asm)], cwd=entry['directory'],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for name,size in re.findall(r'^nc_probe_size_(\w+):\s*\n\s*\.(?:xword|quad|word)\s+(\d+)',asm.read_text(),re.M):
            found[name]=int(size)
count = 0
for path in (root/'source/native/state').glob('*.def'):
    original=path.read_text()
    def fix(match):
        global count
        name,size=match.groups()
        if name not in found: raise SystemExit(f'No target size for {name}')
        if int(size)!=found[name]: count+=1
        return f'NC_REC({name}, {found[name]})'
    updated=re.sub(r'NC_REC\(\s*(\w+)\s*,\s*(\d+)\s*\)',fix,original)
    if updated!=original:path.write_text(updated)
print(f'{len(found)} record sizes checked, {count} adjusted for glibc')
