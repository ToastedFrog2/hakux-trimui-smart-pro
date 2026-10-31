#!/usr/bin/env python3
"""Exercise the real watchdog and manual exit without a graphics driver."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parent
os.chdir(root)
flags=['-std=gnu11','-O1','-g','-DHAKUX_XBOX2=1','-Iplatform/include']
if os.environ.get('HAKUX_TEST_SANITIZE'):flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
with tempfile.TemporaryDirectory(prefix='hakux-recovery-check-') as tmp:
    tmp=Path(tmp)
    source=(root/'source/native/run/xboxrun.c').read_text()
    a=source.index('static void *watchdog(');b=source.index('\nint main(',a)
    harness=r'''
#include "hakux/gpu_progress.h"
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static int mode;
static unsigned g_hang_s;
static uint64_t clock_ms;
enum { NC_FATAL_GPU_LOST=9 };
static int nc_hle_fatal_kind(void){return 0;}
static const char *nc_hle_fatal(void){return 0;}
static uint64_t mono_ms(void){return clock_ms;}
static uint64_t hle_back_swap_count(void){return 100;}
static uint64_t hle_tl_submitted(void){return mode==0?0:mode==1?clock_ms/100+5:6;}
static uint64_t hle_tl_completed(void){return mode==0?0:mode==1?clock_ms/100:1;}
static void report_guest(void *p,int n){}
static void nc_log(const char *tag,const char *fmt,...){
 va_list ap;va_start(ap,fmt);vfprintf(stderr,fmt,ap);va_end(ap);fputc('\n',stderr);
}
static int fake_sleep(unsigned n){clock_ms+=n/1000;if(clock_ms>=30000)_exit(mode==2?99:0);return 0;}
#define usleep fake_sleep
'''
    main=r'''
static void bad_teardown(void){FILE *f=fopen("UNSAFE-TEARDOWN","w");if(f)fclose(f);}
int main(int argc,char **argv){mode=atoi(argv[1]);atexit(bad_teardown);watchdog(0);return 99;}
'''
    p=tmp/'watchdog.c';p.write_text(harness+source[a:b]+main)
    exe=tmp/'watchdog'
    subprocess.run([os.environ.get('CC','cc'),*flags,str(p),'-o',str(exe)],check=True)
    for case,code in [(0,0),(1,0),(2,9)]:
        r=subprocess.run([str(exe),str(case)],cwd=tmp,text=True,capture_output=True)
        assert r.returncode==code,(case,r.returncode,r.stderr)
        assert not (tmp/'UNSAFE-TEARDOWN').exists()
        if case==2:assert 'GPU recovery: no completion for 15 s (1/6)' in r.stderr
    # Actual Start+Select handler, compiled against SDL and core declarations.
    frontend=(root/'platform/frontend.c').read_text();a=frontend.index('static void emergency_exit(');b=frontend.index('static void pad_state(',a)
    harness=r'''
#include "native/dev/usb.h"
#include <SDL.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static Uint32 clock_ms=100;
Uint32 SDL_GetTicks(void){return clock_ms;}
Uint8 SDL_GameControllerGetButton(SDL_GameController *p,SDL_GameControllerButton b){return b==SDL_CONTROLLER_BUTTON_START||b==SDL_CONTROLLER_BUTTON_BACK;}
Sint16 SDL_GameControllerGetAxis(SDL_GameController *p,SDL_GameControllerAxis a){return 0;}
void nc_pad_set(unsigned p,const NcPadState *s){}
'''
    main=r'''
static void bad_teardown(void){FILE *f=fopen("UNSAFE-TEARDOWN","w");if(f)fclose(f);}
int main(void){atexit(bad_teardown);emergency_exit((SDL_GameController*)1);clock_ms+=1201;emergency_exit((SDL_GameController*)1);return 99;}
'''
    p=tmp/'pad.c';p.write_text(harness+frontend[a:b]+main)
    subprocess.run([os.environ.get('CC','cc'),*flags,'-Isource','-Ideps/SDL2/include',str(p),'-o',str(tmp/'pad')],check=True)
    r=subprocess.run([str(tmp/'pad')],cwd=tmp,capture_output=True,text=True)
    assert r.returncode==0 and 'exit requested' in r.stderr
    assert not (tmp/'UNSAFE-TEARDOWN').exists()
print('PASS actual watchdog: idle loading allowed, ongoing GPU progress allowed, stuck GPU exits after 15s; Start+Select and recovery skip unsafe global teardown.')
