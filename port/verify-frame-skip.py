#!/usr/bin/env python3
"""Exercise real presenter decisions and display pickup without a GPU."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parent
source=Path(os.environ.get('HAKUX_TEST_SOURCE',root/'source'))
s=(source/'hw/xbox/hle/vk/swapchain.c').read_text()
a=s.index('bool hle_present_unchanged(')
unchanged=s[a:s.index('\nbool hle_present_begin(',a)]
s=(source/'native/app/present.c').read_text()
frame=s[s.index('bool nc_present_frame('):]
prefix=r'''
#include "hakux/frame_skip.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct ANativeWindow {unsigned w,h;};
static unsigned ANativeWindow_getWidth(struct ANativeWindow *w){return w->w;}
static unsigned ANativeWindow_getHeight(struct ANativeWindow *w){return w->h;}
static struct ANativeWindow win={1280,720};
static struct {
 bool shown,stale,have;struct ANativeWindow *win;unsigned sc;
 uint64_t shown_key;struct {unsigned width,height;}wsize;
 unsigned ramp_gen;struct {unsigned gen,swap_id;}f;
}g_ps;
static HakuxFrameSkip g_frame_skip;
static bool front=true;static unsigned generation=1,swap_id,ramp;
static unsigned mode,pickups,waits,begins,ends,polls,counts;static uint64_t revision;
static bool begin_ok=true;
static unsigned hle_disp_gamma_seq(void){return ramp;}
static bool hle_disp_front(uint32_t *gen,uint32_t *id){*gen=generation;*id=swap_id;return front;}
static unsigned hakux_menu_frame_skip(void){return mode;}
static uint64_t hakux_menu_key_revision(void){return revision;}
static void count_frames(void){counts++;}
static void debug_poll(void){polls++;}
static bool g_fxaa,g_widescreen,g_shown;static int g_upscale,g_aspect;
static struct{int fxaa,upscale;bool average;}g_dbg={-1,-1,false};
static uint64_t now_ns(void){return 10;}
static void nc_dev_nv2a_display_pickup(uint64_t n){assert(n==10);pickups++;}
static void wait_next_vsync(void){waits++;}
static bool hle_present_begin(struct ANativeWindow *w,uint32_t *ww,uint32_t *wh){begins++;*ww=w->w;*wh=w->h;return begin_ok;}
static bool hle_present_frame(uint32_t *fw,uint32_t *fh){*fw=640;*fh=480;g_ps.f.gen=generation;g_ps.f.swap_id=swap_id;g_ps.have=front;return front;}
static void place(uint32_t fw,uint32_t fh,uint32_t ww,uint32_t wh,float *sx,float *sy){*sx=*sy=1;}
static void hle_present_end(float sx,float sy,bool fxaa,int upscale,bool average,uint64_t key){ends++;g_ps.shown=true;g_ps.shown_key=key;g_ps.ramp_gen=ramp;g_ps.stale=false;g_ps.wsize.width=win.w;g_ps.wsize.height=win.h;}
'''
main=r'''
static void reset(void){
 memset(&g_ps,0,sizeof(g_ps));hakux_frame_skip_reset(&g_frame_skip);
 g_ps.shown=g_ps.have=true;g_ps.win=&win;g_ps.sc=1;
 g_ps.wsize.width=win.w;g_ps.wsize.height=win.h;
 generation=1;swap_id=ramp=0;g_ps.f.gen=1;
 mode=1;revision=0;front=true;begin_ok=true;
 pickups=waits=begins=ends=polls=counts=0;
}
static void step(unsigned id){swap_id=id;assert(nc_present_frame(&win));}
int main(void){
 HakuxFrameSkip p={0};
 assert(!hakux_frame_skip_display(&p,1,1,10));
 assert(hakux_frame_skip_display(&p,1,1,11));
 for(int i=0;i<100;i++)assert(hakux_frame_skip_display(&p,1,1,11));
 assert(!hakux_frame_skip_display(&p,1,1,12));
 assert(!hakux_frame_skip_display(&p,1,2,1));
 assert(!hakux_frame_skip_display(&p,0,2,2));
 assert(!hakux_frame_skip_display(&p,99,2,2));
 hakux_frame_skip_reset(&p);
 assert(!hakux_frame_skip_display(&p,1,7,UINT32_MAX));
 assert(hakux_frame_skip_display(&p,1,7,0));
 reset();step(1);assert(begins==1 && ends==1 && pickups==1 && !waits);
#ifdef HAKUX_XBOX2
 step(2);assert(begins==1 && ends==1 && pickups==2 && waits==1);
 for(int i=0;i<5;i++)step(2);
 assert(begins==1 && ends==1 && pickups==7 && waits==6);
 step(3);assert(begins==2 && ends==2 && pickups==8);
 step(4);assert(ends==2); /* selected to skip */
 revision++;step(4);assert(ends==3); /* menu/picture changes force display */
 mode=0;revision++;step(5);step(6);assert(ends==5);
 mode=1;revision++;step(7);step(8);step(9); /* next skip selection */
 unsigned before=ends;step(9);assert(ends==before);
 ramp++;step(9);assert(ends==before+1); /* gamma changes cannot be skipped */
 step(10);step(11);before=ends;g_ps.stale=true;step(11);assert(ends==before+1);
 step(12);step(13);before=ends;win.w=640;step(13);assert(ends==before+1);
 win.w=1280;revision++;step(14);step(15);step(16);before=ends;
 generation++;swap_id=0;assert(nc_present_frame(&win));assert(ends==before+1);
#else
 for(unsigned i=2;i<20;i++)step(i);
 assert(ends==19 && begins==19); /* non-Xbox2 build stays unchanged */
#endif
 reset();mode=0;for(unsigned i=1;i<=100;i++)step(i);
 assert(ends==100 && pickups==100 && !waits);
 step(100);assert(ends==100 && waits==1 && pickups==101);
 front=false;step(101);assert(ends==101 && !g_ps.have);
 step(102);assert(ends==101); /* no front frame: no extra composition */
 reset();g_ps.stale=true;begin_ok=false;assert(!nc_present_frame(&win));assert(!ends && !pickups);
 puts("PASS actual unchanged/present-frame integration: alternate unique frames, persistent skip on repeat refresh, Off/baseline behavior, settings/gamma/window/reset forcing, display pickup and pacing preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='hakux-frame-skip-') as td:
    p=Path(td)/'test.c';p.write_text(prefix+unchanged+frame+main)
    for feature in [False,True]:
        exe=Path(td)/('skip' if feature else 'baseline')
        subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-fsanitize=address,undefined',
          '-fno-omit-frame-pointer',*(['-DHAKUX_XBOX2=1'] if feature else []),
          '-I'+str(root/'platform/include'),str(p),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
