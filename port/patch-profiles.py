#!/usr/bin/env python3
"""Load per-title settings before renderer/network initialization."""
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'source/native/run/xboxrun.c';s=p.read_text()
h='#include "hakux/profile.h"'
if h not in s:s=s.replace('#include "hakux/menu.h"','#include "hakux/menu.h"\n'+h,1)
a='    NcOptions opt;\n    nc_options_init(&opt);'
b='''#ifdef HAKUX_XBOX2
    hakux_profile_bootstrap(fd);
#endif
'''+a
if b not in s:
 assert a in s;s=s.replace(a,b,1)
a='    hakux_menu_init(argc, argv);'
b='    hakux_profile_network();\n'+a
if b not in s:
 assert a in s;s=s.replace(a,b,1)
p.write_text(s)
p=r/'source/native/CMakeLists.txt';s=p.read_text();line='target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/profile.c")'
if line not in s:s+='\n'+line+'\n'
p.write_text(s)
