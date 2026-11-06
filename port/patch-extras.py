#!/usr/bin/env python3
"""Wire the TrimUI mods/cheats catalog into the existing native engine."""
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'source/native/core/mods.c';s=p.read_text()
h='#ifdef HAKUX_XBOX2\n#include "hakux/extras.h"\n#endif'
if h not in s:s=s.replace('#include "native/core/mods.h"','#include "native/core/mods.h"\n'+h,1)
a='void nc_mods_install(NcDisc *disc)\n{'
b=a+'\n#ifdef HAKUX_XBOX2\n    if (!g_manifest[0]) hakux_extras_prepare(disc);\n#endif'
if b not in s:
    assert a in s;s=s.replace(a,b,1)
p.write_text(s)
p=r/'source/native/CMakeLists.txt';s=p.read_text();line='target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/extras.c")'
if line not in s:s+='\n'+line+'\n'
line='target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/png.c")'
if line not in s:
 anchor='target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/extras.c")'
 s=s.replace(anchor,anchor+'\n'+line,1)
p.write_text(s)
