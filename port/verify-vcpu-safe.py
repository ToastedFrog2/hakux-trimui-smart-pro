#!/usr/bin/env python3
"""Regression checks against actual current C functions and archived faulty variants."""
from pathlib import Path
import re,subprocess,tempfile,os
root=Path(__file__).resolve().parent
before=root/'tests/fixtures/vcpu-before'
def function(s,name):
    at=re.search(r'(?m)^(?:static )?(?:bool|void|uint64_t|unsigned) '+re.escape(name)+r'\(',s).start()
    brace=s.index('{',at)
    masked=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),s,flags=re.S)
    n=1;end=brace+1
    while n:
        if masked[end]=='{':n+=1
        if masked[end]=='}':n-=1
        end+=1
    return s[at:end]
clock_prefix='''#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <assert.h>
#ifndef CLOCK_MONOTONIC_COARSE
#define CLOCK_MONOTONIC_COARSE 99
#endif
static uint64_t fake_ns=1000000000ull,g_boot_ns,g_time_offset;
static int test_clock_gettime(int which,struct timespec *ts) {
 uint64_t n=which==CLOCK_MONOTONIC_COARSE?fake_ns/4000000*4000000:fake_ns;
 ts->tv_sec=n/1000000000;ts->tv_nsec=n%1000000000;return 0;
}
#define clock_gettime test_clock_gettime
/* Exercise cache expiry using the fake clock, not Apple hardware counters. */
#undef __aarch64__
'''
clock_test='''
int main(void) {
 nc_ke_time_enter();uint64_t first=nc_ke_now_ns();assert(first==1000000000ull);
 fake_ns+=1000000;assert(nc_ke_now_ns()==first);
 fake_ns+=5000000;assert(nc_ke_now_ns()==fake_ns); /* long entry must refresh */
 fake_ns+=1000000;nc_ke_time_stale();assert(nc_ke_now_ns()==fake_ns);
 nc_ke_time_leave();fake_ns+=1000000;assert(nc_ke_now_ns()==fake_ns);
 nc_ke_pause_begin();uint64_t paused=nc_ke_now_ns();fake_ns+=1000000000ull;
 assert(nc_ke_now_ns()==paused);assert(nc_ke_pause_end()==1000000000ull);
 assert(nc_ke_now_ns()==paused);return 0;
}
'''
barrier_prefix='''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
static uint64_t g_ram=8192;static uint32_t spans[2],*g_cspan=spans;
static uint8_t faults[2],*g_cspan_faults=faults;
static void catchup(void){} static void (*g_catch_up)(void)=catchup;
static unsigned protections;
static uint64_t hle_ram_addr_base(void){return 0;}
static void hle_host_mem_test_and_clear(uint64_t a,uint64_t n){assert(a==0&&n==4096);protections++;}
'''
barrier_test='''
int main(void) {
 for(unsigned i=0;i<32;i++) {
  spans[0]=0;faults[0]=i;hle_barrier_arm_copied(16,32);
  assert(spans[0]==(16u|(48u<<16)));assert(protections==i+1);
 }
 return 0;
}
'''
kernel_prefix='''#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <assert.h>
enum NcSysOp {NC_SYSOP_INT=1,NC_SYSOP_HOOK=2};
#define NC_KCALL_VECTOR 0x3f
#define NC_T_RUNNING 1
typedef struct {uint32_t eip;} NcFrame;
typedef struct {int state;} NcThread;
typedef struct {void *vm;NcThread *current;bool stop,resched,force_switch;uint64_t interrupts;uint32_t stop_va;} NcKernel;
static int g_nc_in_sysop,g_slow_sysops=0;
static uint64_t g_sysop_kind[32],g_sysops;
static struct {uint64_t idles;} g_nc_sched;
static unsigned pauses,entries,leaves,common;
static void nc_kernel_pause_point(void *k,NcFrame *f,bool idle){pauses++;}
static void nc_ke_time_enter(void){entries++;} static void nc_ke_time_leave(void){leaves++;}
static uint64_t slow_now_ns(void){return 1;}
static uint32_t nc_frame_eip(NcFrame *f){return f->eip;}
static const uint8_t *nc_vm_host(void *v,uint32_t a){static uint8_t b[4];return b;}
static uint16_t nc_rd16(const uint8_t *p){return 0;}
static void slow_sysop(NcKernel *k,int op,uint32_t eip,unsigned ordinal,uint64_t a,uint64_t b,uint64_t c){}
static bool sysop(void *k,NcFrame *f,enum NcSysOp op,unsigned size){common++;return true;}
static bool nc_x86mmio_hook(NcKernel *k,NcFrame *f,uint32_t eip){return true;}
static void stats_tick(NcKernel *k){}
static unsigned nc_irq_lines(void){return 0;}
static bool nc_frame_if(NcFrame *f){return true;}
static void nc_intr_dispatch(NcKernel *k,bool r){}
static uint8_t *pcr_irql(NcKernel *k){static uint8_t n;return &n;}
static void nc_ps_schedule(NcKernel *k,NcFrame *f){}
static void nc_frame_set_eip(NcFrame *f,uint32_t e){f->eip=e;}
'''
kernel_test='''
int main(void) {NcKernel k={0};NcFrame f={0x1234};
 for(unsigned i=0;i<10000;i++)assert(nc_kernel_sysop(&k,&f,NC_SYSOP_HOOK,1));
 assert(pauses==10000&&entries==10000&&leaves==10000&&common==10000);
 assert(!g_nc_in_sysop);return 0;}
'''
with tempfile.TemporaryDirectory(prefix='hakux-vcpu-safe-') as t:
    t=Path(t)
    for kind,prefix,test,path in [
        ('clock',clock_prefix,clock_test,'native/kernel/ke.c'),
        ('barrier',barrier_prefix,barrier_test,'hw/xbox/hle/mem/barrier.c'),
        ('kernel',kernel_prefix,kernel_test,'native/kernel/kernel.c')]:
        for fixed,folder in [(True,root/'source'),(False,before)]:
            s=(folder/path).read_text()
            if kind=='clock':
                start=s.index('static __thread bool t_in_entry;');end=s.index('static uint64_t since_boot_100ns',start);body=s[start:end]
            elif kind=='barrier':body=function(s,'hle_barrier_arm_copied')
            else:body=function(s,'nc_kernel_sysop')
            src=t/(kind+str(fixed)+'.c');src.write_text(prefix+'\n'+body+'\n'+test)
            exe=src.with_suffix('')
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g',str(src),'-o',str(exe)],check=True,capture_output=True)
            r=subprocess.run([str(exe)],cwd=t,capture_output=True,timeout=3)
            assert (r.returncode==0)==fixed,kind+' regression control did not distinguish fixed/broken code'
        print('PASS actual '+kind+': corrected code passes; previous optimized code reproduces the failure')
