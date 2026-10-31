#!/usr/bin/env python3
"""Check actual patch reruns cannot change an already-patched build tree."""
from pathlib import Path
import hashlib,subprocess
root=Path(__file__).resolve().parent
assert (root/'source/native/core/xbe_load.c').is_file(),'Unpack the pinned source first'
order=['source','xbox2','halfscale','menu','recovery','shader-compat','memory','objects','halo2-save','frame-skip','scale075']
def apply():
    for name in order:subprocess.run(['python3',str(root/f'patch-{name}.py')],check=True)
def hashes():
    return {str(p.relative_to(root/'source')):hashlib.sha256(p.read_bytes()).digest()
            for p in (root/'source').rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
apply();before=hashes();apply();after=hashes()
assert before==after,[n for n in before if before[n]!=after.get(n)]
s=(root/'source/native/core/xbe_load.c').read_text()
assert s.count('k_patches[]')==1,'Duplicate legacy title-patch table'
assert s.count('if (k_patches[i].title == 0x4d530064u)')==1,'Xbox preview must retain the Halo legacy-override guard'
h=(root/'source/hw/xbox/hle/shader/ff.h').read_text()
assert h.count('extern bool g_hle_glsl_scale035;')==1
assert h.count('extern bool g_hle_glsl_scale075;')==1
print('PASS actual complete build-patch rerun: source contents unchanged, exactly one guarded legacy Halo patch table')
