#!/usr/bin/env python3
"""Exercise the actual menu and launcher without starting a game or display."""
from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='hakux-menu-check-') as temp:
    temp=Path(temp)
    flags=['-std=gnu11','-O1','-g','-DHAKUX_XBOX2=1','-DHLE_HOST_TEST=1','-DVK_NO_PROTOTYPES',
           '-Itests/menu-stubs','-Isource','-Iplatform/include','-Ideps/SDL2/include','-Ideps/volk',
           '-Ideps/Vulkan-Headers/include']
    if os.environ.get('HAKUX_TEST_SANITIZE'): flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
    frontend=(root/'platform/frontend.c').read_text()
    a=frontend.index('static void pad_state(');b=frontend.index('/* Poll independently',a)
    (temp/'pad-state.inc').write_text(frontend[a:b])
    flags+=['-I'+str(temp)]
    exe=temp/'menu-check'
    subprocess.run([os.environ.get('CC','cc'),*flags,'tests/menu.c','-o',str(exe),'-lpthread'],cwd=root,check=True)
    subprocess.run([str(exe)],cwd=temp,check=True)
    # Run the real launcher with a small fake emulator, exercising scale restart,
    # XBE relaunch, quoted paths, and ownership/cleanup of the awake marker.
    app=temp/'app with spaces';app.mkdir()
    runner=(root/'package/hakux/run.sh').read_text().replace('APP=/mnt/SDCARD/Data/ports/hakux','APP='+repr(str(app)))
    runner=runner.replace('/tmp/stay_awake',str(temp/'stay_awake'))
    (temp/'run.sh').write_text(runner)
    (app/'render-scale').write_text('0.5\n')
    rom=temp/'game with spaces.iso';rom.write_bytes(b'test')
    fake='''#!/bin/sh
set -eu
N=0
[ ! -f count ] || N=$(cat count)
N=$((N+1))
echo "$N" > count
test "$1" = "$EXPECTED_ROM"
test "$2" = "hdd=$PWD/hdd"
case "$N" in
 1) test "$HAKUX_RENDER_SCALE" = 0.5
    echo 0.75 > render-scale
    echo restart > menu-restart
    exit 20;;
 2) test "$HAKUX_RENDER_SCALE" = 0.75
    test "$#" = 2
    touch relaunch.bin
    exit 10;;
 3) test "$3" = relaunch
    echo restart > menu-restart
    exit 20;;
 4) test "$#" = 2
    exit 0;;
 *) exit 98;;
esac
'''
    (app/'hakux.aarch64').write_text(fake);(app/'hakux.aarch64').chmod(0o755)
    binpath=temp/'bin';binpath.mkdir()
    (binpath/'pidof').write_text('#!/bin/sh\nexit 1\n');(binpath/'pidof').chmod(0o755)
    env=dict(os.environ,PATH=str(binpath)+':'+os.environ['PATH'],EXPECTED_ROM=str(rom))
    env.pop('HAKUX_RENDER_SCALE',None)
    subprocess.run(['/bin/sh',str(temp/'run.sh'),str(rom)],env=env,cwd=temp,check=True)
    assert (app/'count').read_text().strip()=='4'
    assert not (temp/'stay_awake').exists()
    assert not (app/'menu-restart').exists()
    print('PASS actual launcher: scale restart, game XBE relaunch, paths with spaces, awake cleanup')
