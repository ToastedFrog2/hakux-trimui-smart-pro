#include "native/core/cheats.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static unsigned char mem[16];static bool mapped=true;
static bool rd(void *p,uint32_t a,void *b,unsigned n){if(!mapped||a+n>sizeof(mem))return false;memcpy(b,mem+a,n);return true;}
static bool wr(void *p,uint32_t a,const void *b,unsigned n){if(!mapped||a+n>sizeof(mem))return false;memcpy(mem+a,b,n);return true;}
int main(void)
{
 NcCheatMem m={0,rd,wr};char err[100];
 assert(nc_cheat_add("Guarded reversible flag",false,false)==0);
 assert(nc_cheat_line("if8 0 == 42",err,sizeof(err)));
 assert(nc_cheat_line("toggle8 1 1",err,sizeof(err)));
 assert(nc_cheat_line("end",err,sizeof(err)));
 assert(!nc_cheat_line("toggle8 [2] 1",err,sizeof(err)));
 nc_cheats_run(&m);assert(mem[1]==0);
 nc_cheat_set(0,true);nc_cheats_run(&m);assert(mem[1]==0); /* bad build guard */
 mem[0]=42;assert(nc_cheats_run(&m)==1&&mem[1]==1);
 assert(!nc_cheats_run(&m));nc_cheat_set(0,false);
 mapped=false;nc_cheats_run(&m);assert(mem[1]==1);
 mapped=true;assert(nc_cheats_run(&m)==1&&mem[1]==0);
 mem[1]=1;nc_cheat_set(0,true);nc_cheats_run(&m);nc_cheat_set(0,false);nc_cheats_run(&m);assert(mem[1]==1); /* pre-existing flag preserved */
 mem[1]=0;nc_cheat_set(0,true);nc_cheats_run(&m);mem[1]=7;nc_cheat_set(0,false);nc_cheats_run(&m);assert(mem[1]==7); /* game changed it */
 nc_cheats_reset();assert(nc_cheat_add("Existing write",true,false)==0);assert(nc_cheat_line("w8 2 9",err,sizeof(err)));nc_cheats_run(&m);nc_cheat_set(0,false);nc_cheats_run(&m);assert(mem[2]==9);
 nc_cheats_reset();assert(nc_cheat_add("Existing once",true,true)==0);assert(nc_cheat_line("w8 3 9",err,sizeof(err)));nc_cheats_run(&m);mem[3]=0;nc_cheats_run(&m);assert(mem[3]==0);
 puts("PASS native toggle8: guarded writes, restore on disable, retry unmapped flags, preserve pre-existing/game-changed values; existing write and once codes unchanged");
}
