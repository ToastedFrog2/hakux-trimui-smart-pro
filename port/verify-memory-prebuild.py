#!/usr/bin/env python3
"""Exercise the actual bounded prebuild and its worker without a GPU."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parent
s=(root/'source/hw/xbox/hle/vk/pipeasync.c').read_text()
start=s.index('static void *prebuild_worker(')
functions=s[start:s.index('\nvoid hle_pipe_progress(',start)]
prefix=r'''
#include "hakux/prebuild_budget.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define HAKUX_XBOX2 1
#define PREBUILD_THREADS 6
#define MIN(a,b) ((a)<(b)?(a):(b))
#define hle_atomic_read(p) (*(p))
#define hle_atomic_set(p,v) (*(p)=(v))
#define hle_atomic_inc(p) (++*(p))
typedef uintptr_t VkPipeline;
typedef enum {HLE_PB_OK,HLE_PB_COMPILE} HlePbResult;
typedef struct {uint32_t *tok,nslots;} Prog;
typedef struct {uint64_t hash,vsh;void *key;VkPipeline pipe;HlePbResult r;} RecPipe;
typedef int HleThread;
#define HLE_THREAD_JOINABLE 1
static struct {bool prebuild;char *path;unsigned nlist,pb_total,pb_done,pb_next;RecPipe list[5000];HlePbResult (*build)(const void*,const uint32_t*,uint32_t,bool,VkPipeline*);} g_pa;
static unsigned builds,added;
static const Prog *prog_find(uint64_t h) {return NULL;}
static int64_t g_get_monotonic_time(void){return 1000;}
static void hle_log(const char *a,const char *b,...){ }
static void hle_thread_create(HleThread *t,const char *n,void *(*fn)(void*),void *arg,int flags){fn(arg);}
static void hle_thread_join(HleThread *t){ }
static HlePbResult build(const void *key,const uint32_t *tok,uint32_t n,bool cache,VkPipeline *out){
 assert((uintptr_t)key==builds+1);builds++;*out=(uintptr_t)key;return HLE_PB_OK;
}
static void add(uint64_t hash,VkPipeline p){assert(hash==added+1 && p==hash);added++;}
'''
main=r'''
static void run(const char *option,unsigned count,unsigned caller_max,unsigned expected){
 memset(&g_pa,0,sizeof(g_pa));builds=added=0;
 if(option)setenv("HAKUX_HLE_PREBUILD_LIMIT",option,1);else unsetenv("HAKUX_HLE_PREBUILD_LIMIT");
 g_pa.prebuild=true;g_pa.path="record";g_pa.nlist=count;g_pa.build=build;
 for(unsigned i=0;i<count;i++){g_pa.list[i].hash=i+1;g_pa.list[i].key=(void*)(uintptr_t)(i+1);}
 hle_pipe_prebuild(caller_max,add);
 assert(builds==expected && added==expected && g_pa.nlist==count);
 assert(!g_pa.pb_total && !g_pa.pb_done);
 for(unsigned i=expected;i<count;i++)assert(!g_pa.list[i].pipe);
}
int main(void){
 run(NULL,1627,4096,512);run(NULL,200,4096,200);run(NULL,1627,100,100);
 run("0",1627,4096,0);run("16",1627,4096,16);run("9000",4500,4096,4096);
 run("bad",1627,4096,512);run("-1",1627,4096,512);run("512x",1627,4096,512);
 run(" -1",1627,4096,512);run("16 ",1627,4096,512);run("",1627,4096,512);
 g_pa.prebuild=false;builds=0;hle_pipe_prebuild(4096,add);assert(!builds);
 puts("PASS actual prebuild and worker: default 512 resident pipelines, newest input order, disk records retained, bounded overrides, small records and disabled prebuild");
}
'''
with tempfile.TemporaryDirectory(prefix='hakux-prebuild-budget-') as td:
 p=Path(td)/'test.c';p.write_text(prefix+functions+main)
 exe=Path(td)/'test'
 subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O2','-fsanitize=address,undefined',
                 '-fno-omit-frame-pointer','-I'+str(root/'platform/include'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
