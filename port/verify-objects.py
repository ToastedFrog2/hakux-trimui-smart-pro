#!/usr/bin/env python3
"""Run actual object manager and NtCreateEvent with mapped test guest memory."""
from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parent
ob=(root/'source/native/kernel/ob.c').read_text().replace('#include "native/kernel/kernel.h"','')
ke=(root/'source/native/kernel/ke.c').read_text()
event=ke[ke.index('static uint64_t NtCreateEvent('):ke.index('/* NtSetEvent(')]
semaphore=ke[ke.index('static uint64_t NtCreateSemaphore('):ke.index('/* NtReleaseSemaphore(')]
mutant=ke[ke.index('static uint64_t NtCreateMutant('):ke.index('/* NtReleaseMutant(')]
prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define HAKUX_XBOX2 1
#define NC_PAGE 4096u
#define NC_MAX_HANDLES 16384u
#define NC_STATUS_SUCCESS 0u
#define NC_STATUS_INVALID_HANDLE 0xC0000008u
#define NC_STATUS_INVALID_PARAMETER 0xC000000Du
#define NC_STATUS_OBJECT_TYPE_MISMATCH 0xC0000024u
#define NC_STATUS_INSUFFICIENT_RESOURCES 0xC000009Au
#define NC_OB_TYPES 9
enum NcObType {NC_OB_THREAD,NC_OB_EVENT,NC_OB_SEMAPHORE,NC_OB_MUTANT,NC_OB_TIMER,NC_OB_FILE,NC_OB_DEVICE,NC_OB_SYMLINK,NC_OB_DIRECTORY};
typedef struct {unsigned object;enum NcObType type;} NcHandle;
typedef struct {unsigned id,ethread;} Thread;
typedef struct {unsigned char base[1<<20];} NcVm;
typedef struct {NcVm *vm;unsigned type_va[NC_OB_TYPES];unsigned pool_ob;Thread *current;NcHandle handle_table[NC_MAX_HANDLES];} NcKernel;
typedef int NcFrame;
#define NC_ESP 0
static unsigned next=0x10000;
static unsigned nc_vm_rd32(NcVm *v,unsigned a){unsigned x;assert(a<sizeof(v->base)-3);memcpy(&x,v->base+a,4);return x;}
static void nc_vm_wr32(NcVm *v,unsigned a,unsigned x){assert(a<sizeof(v->base)-3);memcpy(v->base+a,&x,4);}
static void *nc_vm_host(NcVm *v,unsigned a){assert(a<sizeof(v->base));return v->base+a;}
static unsigned nc_vm_phys(NcVm *v,unsigned a){return a<sizeof(v->base)?a:UINT32_MAX;}
static unsigned nc_pool_alloc(NcKernel *k,unsigned n){unsigned p=next;next=(next+n+15)&~15;assert(next<sizeof(k->vm->base));memset(k->vm->base+p,0,n);return p;}
static void nc_pool_free(NcKernel *k,unsigned p,unsigned n){}
static void nc_io_close(NcKernel *k,unsigned o){}
static unsigned nc_frame_gpr(NcFrame *f,int r){return 0;}
static void nc_log(const char *a,const char *b,...){}
static void nc_kernel_impl(NcKernel *k,const char *n,uint64_t(*fn)(NcKernel*,NcFrame*,const uint32_t*)){}
static void init_header(NcKernel *k,unsigned ev,unsigned char type,int size,int state){nc_vm_wr32(k->vm,ev+4,state);}
#define OBJ_SEMAPHORE 5
#define SEMAPHORE_LIMIT 16
static void init_mutant(NcKernel *k,unsigned m,bool owned){nc_vm_wr32(k->vm,m+4,owned?0:1);}
'''
main=r'''
static NcVm vm;static NcKernel k;
static void attrs(const char *name,unsigned flags){
 unsigned n=strlen(name);memcpy(vm.base+0x300,name,n);
 nc_vm_wr32(&vm,0x200,n|(n<<16));nc_vm_wr32(&vm,0x204,0x300);
 nc_vm_wr32(&vm,0x100,0);nc_vm_wr32(&vm,0x104,0x200);nc_vm_wr32(&vm,0x108,flags);
}
static uint32_t create(unsigned out,unsigned attrs,unsigned state){uint32_t a[]={out,attrs,0,state};return NtCreateEvent(&k,NULL,a);}
static uint32_t open(unsigned attrs,unsigned type,unsigned out){uint32_t a[]={attrs,type,0,out};return ObOpenObjectByName(&k,NULL,a);}
int main(void){
 k.vm=&vm;for(unsigned i=0;i<NC_OB_TYPES;i++)k.type_va[i]=0x80012000+64*i;
 attrs("ChicagoEvent",0x40);
 /* XAPI's -4 root used by Halo CE mutexes and San Andreas semaphores. */
 attrs("Streaming",0x80);nc_vm_wr32(&vm,0x100,0xfffffffcu);
 uint32_t sa[]={0x450,0x100,0,5};
 assert(NtCreateSemaphore(&k,NULL,sa)==0);
 unsigned sh=nc_vm_rd32(&vm,0x450),so=nc_ob_lookup(&k,sh,NULL);
 assert(nc_vm_rd32(&vm,so+4)==0 && nc_vm_rd32(&vm,so+16)==5);
 sa[0]=0x454;sa[2]=3;sa[3]=8;
 assert(NtCreateSemaphore(&k,NULL,sa)==OB_NAME_EXISTS);
 assert(nc_ob_lookup(&k,nc_vm_rd32(&vm,0x454),NULL)==so);
 assert(nc_vm_rd32(&vm,so+4)==0 && nc_vm_rd32(&vm,so+16)==5);
 attrs("\\Win32NamedObjects\\Streaming",0);
 assert(open(0x100,k.type_va[NC_OB_SEMAPHORE],0x458)==0);
 assert(nc_ob_lookup(&k,nc_vm_rd32(&vm,0x458),NULL)==so);
 attrs("Streaming",0);assert(open(0x100,0,0x45c)==OB_NAME_NOT_FOUND);
 attrs("HaloMutex",0x80);nc_vm_wr32(&vm,0x100,0xfffffffcu);
 uint32_t ha[]={0x460,0x100,1};assert(NtCreateMutant(&k,NULL,ha)==0);
 unsigned mo=nc_ob_lookup(&k,nc_vm_rd32(&vm,0x460),NULL);
 assert(nc_vm_rd32(&vm,mo+4)==0);
 ha[0]=0x464;ha[2]=0;assert(NtCreateMutant(&k,NULL,ha)==OB_NAME_EXISTS);
 assert(nc_ob_lookup(&k,nc_vm_rd32(&vm,0x464),NULL)==mo && nc_vm_rd32(&vm,mo+4)==0);
 attrs("halomutex",0x40);nc_vm_wr32(&vm,0x100,0xfffffffcu);
 assert(open(0x100,k.type_va[NC_OB_MUTANT],0x468)==0);
 assert(open(0x100,k.type_va[NC_OB_EVENT],0x46c)==NC_STATUS_OBJECT_TYPE_MISMATCH);
 nc_vm_wr32(&vm,0x100,0xfffffffdu);assert(open(0x100,0,0x46c)==0xc000003au);
 attrs("\\bad",0);nc_vm_wr32(&vm,0x100,0xfffffffcu);
 assert(open(0x100,0,0x46c)==OB_NAME_INVALID);
 char longname[1024];memset(longname,'x',1023);longname[1023]=0;
 attrs(longname,0);nc_vm_wr32(&vm,0x100,0xfffffffcu);
 assert(open(0x100,0,0x46c)==OB_NAME_INVALID);
 attrs("ChicagoEvent",0x40);
 nc_vm_wr32(&vm,0x400,0xdeadbeef);
 assert(open(0x100,k.type_va[NC_OB_EVENT],0x400)==OB_NAME_NOT_FOUND);
 assert(nc_vm_rd32(&vm,0x400)==0xdeadbeef);
 assert(create(0x400,0x100,1)==0);
 unsigned h1=nc_vm_rd32(&vm,0x400),obj=nc_ob_lookup(&k,h1,NULL);
 assert(obj && nc_vm_rd32(&vm,obj+4)==1);
 attrs("chicagoevent",0x40);
 assert(open(0x100,k.type_va[NC_OB_EVENT],0x404)==0);
 unsigned h2=nc_vm_rd32(&vm,0x404);assert(h1!=h2 && nc_ob_lookup(&k,h2,NULL)==obj);
 assert(open(0x100,k.type_va[NC_OB_TIMER],0x408)==NC_STATUS_OBJECT_TYPE_MISMATCH);
 assert(create(0x408,0x100,0)==OB_NAME_COLLISION);
 attrs("ChicagoEvent",0xC0);assert(create(0x408,0x100,0)==OB_NAME_EXISTS);
 unsigned h3=nc_vm_rd32(&vm,0x408);assert(nc_ob_lookup(&k,h3,NULL)==obj);
 assert(nc_vm_rd32(&vm,obj+4)==1); /* existing signal state must survive create/open */
 assert(nc_ob_close(&k,h1));assert(nc_ob_close(&k,h2));
 assert(open(0x100,0,0x40c)==0);unsigned h4=nc_vm_rd32(&vm,0x40c);
 assert(nc_ob_close(&k,h3));assert(nc_ob_close(&k,h4));
 assert(open(0x100,0,0x40c)==OB_NAME_NOT_FOUND);
 assert(create(0x400,0x100,0)==0);assert(nc_ob_lookup(&k,nc_vm_rd32(&vm,0x400),NULL)!=obj);
 attrs("CHICAGOEVENT",0);assert(open(0x100,0,0x404)==OB_NAME_NOT_FOUND);
 assert(create(0x404,0,1)==0); /* unnamed objects remain supported */
 assert(open(0xfffffffc,0,0x404)==NC_STATUS_INVALID_PARAMETER);
 assert(open(0x100,0,0)==NC_STATUS_INVALID_PARAMETER);
 nc_vm_wr32(&vm,0x200,1024|(1024<<16));assert(open(0x100,0,0x404)==OB_NAME_INVALID);
 attrs("bad",0);nc_vm_wr32(&vm,0x300,0);assert(open(0x100,0,0x404)==OB_NAME_INVALID);
 attrs("ChicagoEvent",0x40);
 for(unsigned i=1;i<NC_MAX_HANDLES;i++)if(!k.handle_table[i].object)k.handle_table[i]=(NcHandle){obj,NC_OB_EVENT};
 assert(open(0x100,0,0x404)==NC_STATUS_INSUFFICIENT_RESOURCES);
 puts("PASS actual object manager + NtCreateEvent/Semaphore/Mutant: Win32 pseudo-directory, absolute aliases, namespace isolation, case rules, typed handles, collision/open-if, state preservation, lifetime, bounds and invalid inputs");
}
'''
with tempfile.TemporaryDirectory(prefix='hakux-objects-') as td:
    p=Path(td)/'test.c'; p.write_text(prefix+ob+event+semaphore+mutant+main)
    exe=Path(td)/'test'
    subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer','-I'+str(root/'platform/include'),str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
