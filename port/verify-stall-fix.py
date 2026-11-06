#!/usr/bin/env python3
"""Check the actual memory limits, copied-range re-arms and clock read budget."""
from pathlib import Path
import os,re,subprocess,tempfile
r=Path(__file__).resolve().parent
draw=(r/'source/hw/xbox/hle/pb/pbdraw.c').read_text()
back=(r/'source/hw/xbox/hle/vk/back.c').read_text()
clock=(r/'source/native/kernel/ke.c').read_text()
def function(text,name):
 start=re.search(r'(?m)^static bool '+name+r'\(',text).start();brace=text.index('{',start)
 depth=1;end=brace+1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
caps=re.search(r'#ifdef HAKUX_XBOX2\n#define TEX_MAX.*?#endif',draw,re.S)[0]
buffers=re.search(r'#ifdef HAKUX_XBOX2\n    const uint32_t arena_bytes.*?#endif',back,re.S)[0]
resources='''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
static struct {struct {bool bc;} caps;} g_hvk;
'''+caps+'\nstatic void check(void) {\n'+buffers+'''
#ifdef HAKUX_XBOX2
 assert(TEX_MAX==768 && arena_bytes==(32u<<20) && land_bytes==(4u<<20));
#else
 assert(TEX_MAX==1536 && arena_bytes==((g_hvk.caps.bc?32u:64u)<<20) && land_bytes==(16u<<20));
#endif
}
int main(void){check();g_hvk.caps.bc=true;check();}
'''
rearms='''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
static struct {uint64_t swaps;} g_pd={1};
'''+function(draw,'recopied')+'''
int main(void) {
 unsigned arms=0;uint32_t from=0x1a71000,len=384;
 assert(!recopied(from,len));arms+=recopied(from,len);
 for(unsigned i=0;i<1000;i++)assert(!recopied(from,len));
 for(g_pd.swaps=2;g_pd.swaps<30;g_pd.swaps++) {
  arms+=recopied(from,len);
  for(unsigned i=0;i<100;i++)assert(!recopied(from,len));
 }
 assert(arms==8);
 uint32_t collision=from^(1u<<22);
 assert(!recopied(collision,len));assert(recopied(collision,len));assert(!recopied(collision,len));
 assert(!recopied(from+16,len));assert(recopied(from+16,len));
}
'''
start=clock.index('static uint64_t g_pub_ns, g_pub_coarse;');end=clock.index('/* KeTickCount',start)
publish='''#include <stdint.h>
#include <assert.h>
static uint64_t now;static unsigned reads;
static uint64_t coarse_ns(void){reads++;return now;}
'''+clock[start:end]+'''
int main(void) {
 assert(!nc_ke_published_ns()&&!reads);nc_ke_publish_time(1000);assert(reads==1);
 for(unsigned i=0;i<64;i++)assert(nc_ke_published_ns()==1000);
 assert(reads==1);assert(nc_ke_published_ns()==1000&&reads==2);
 for(unsigned i=0;i<64;i++)assert(nc_ke_published_ns()==1000);
 now=5000000;assert(!nc_ke_published_ns()&&reads==3);
 nc_ke_publish_time(2000);assert(reads==4);
 for(unsigned i=0;i<64;i++)assert(nc_ke_published_ns()==2000);
 assert(reads==4);
}
'''
# This checks a call-count budget, not a strict wall-clock expiry guarantee.
clock_code=re.sub(r'/\*.*?\*/|//[^\n]*','',clock,flags=re.S)
assert 'cntvct_el0' not in clock_code and 'clock_gettime(CLOCK_MONOTONIC, &ts)' in clock_code
with tempfile.TemporaryDirectory(prefix='hakux-stall-check-') as td:
 t=Path(td)
 for name,body,flags in [('limits-trimui',resources,['-DHAKUX_XBOX2']),('limits-original',resources,[]),('rearms',rearms,[]),('published-clock',publish,[])]:
  source=t/(name+'.c');source.write_text(body);exe=t/name
  subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=address,undefined',*flags,str(source),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True,timeout=5)
  print('PASS actual stall fix: '+name)
