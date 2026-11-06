#include "hakux/extras.h"
#include "native/core/mods.h"
#include "native/core/cheats.h"
#include "hw/xbox/hle/core/xbe.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <unistd.h>
static uint8_t image[0x3000];static unsigned overlays,patches;
void nc_log(const char *tag,const char *fmt,...){va_list ap;va_start(ap,fmt);vfprintf(stderr,fmt,ap);fputc(10,stderr);va_end(ap);}
void hakux_menu_notice(const char *s){}
void hakux_menu_capture_hide(bool hide){}
bool nc_disc_find(const NcDisc *d,const char *p,NcDiscFile *f){*f=(NcDiscFile){.size=sizeof(image)};return !strcasecmp(*p=='\\'?p+1:p,"default.xbe");}
bool nc_disc_read(const NcDisc *d,const NcDiscFile *f,uint64_t off,void *b,size_t n){if(off+n>sizeof(image))return false;memcpy(b,image+off,n);return true;}
bool nc_disc_find_orig(const NcDisc *d,const char *p,NcDiscFile *f){return nc_disc_find(d,p,f);}
bool nc_disc_read_orig(const NcDisc *d,const NcDiscFile *f,uint64_t off,void *b,size_t n){return nc_disc_read(d,f,off,b,n);}
bool nc_disc_overlay_file(NcDisc *d,const char *p,const char *host){assert(!strcmp(p,"data.bin"));overlays++;return true;}
void nc_disc_overlay_seal(NcDisc *d){}
bool nc_disc_overlay_patch(NcDisc *d,const char *p,uint64_t at,const uint8_t *b,uint32_t n){assert(at==0x20&&n==1&&b[0]==1);patches++;return true;}
void nc_dev_nv2a_vblank_multiply(unsigned n){}
int hle_xbe_parse(const uint8_t *hdr,uint32_t len,HleXbeInfo *x){memset(x,0,sizeof(*x));x->base=0x10000;x->sizeof_headers=0x2000;return 0;}
static uint8_t guest[16];
static bool read_mem(void *p,uint32_t a,void *b,unsigned n){if(a<0x10000||a+n>0x10010)return false;memcpy(b,guest+a-0x10000,n);return true;}
static bool write_mem(void *p,uint32_t a,const void *b,unsigned n){if(a<0x10000||a+n>0x10010)return false;memcpy(guest+a-0x10000,b,n);return true;}
static void put32(unsigned at,uint32_t v){memcpy(image+at,&v,4);}
int main(void){
 put32(0,0x48454258);put32(0x104,0x10000);put32(0x108,0x2000);put32(0x118,0x10180);put32(0x180,0x1d0);put32(0x188,0x12345678);put32(0x22c,3);
 NcDisc disc={0};hakux_extras_prepare(&disc);assert(!strcmp(hakux_extras_game_key(),"12345678.3"));nc_mods_install(&disc);
 assert(nc_cheat_count()==2&&hakux_extras_rows()==5);assert(!nc_cheat_on(0)&&!nc_cheat_on(1));
 char line[100],status[100];hakux_extras_line(0,line,sizeof(line));assert(strstr(line,"MOD [OFF]"));
 hakux_extras_choose(1,status,sizeof(status));assert(nc_cheat_on(0));
 NcCheatMem mem={NULL,read_mem,write_mem};nc_cheats_run(&mem);assert(guest[0]==42);
 hakux_extras_choose(3,status,sizeof(status));assert(!nc_cheat_on(0)&&!nc_cheat_on(1));
 hakux_extras_choose(0,status,sizeof(status));assert(strstr(status,"RESTART"));
 nc_cheats_reset();nc_mods_set_manifest("");hakux_extras_prepare(&disc);nc_mods_install(&disc);
 fprintf(stderr,"counts overlays=%u patches=%u\n",overlays,patches);assert(overlays==1&&patches==1);assert(nc_cheat_count()==2&&!nc_cheat_on(0));
 hakux_extras_choose(2,status,sizeof(status));assert(nc_cheat_on(1));nc_cheats_run(&mem);assert(guest[1]==7);
 guest[1]=0;nc_cheats_run(&mem);assert(guest[1]==0); /* once cheat stays once */
 nc_cheats_reset();nc_mods_set_manifest("");hakux_extras_prepare(&disc);nc_mods_install(&disc);assert(nc_cheat_on(1));
 /* Another certificate version cannot inherit this title's mods or choices. */
 put32(0x22c,4);nc_cheats_reset();nc_mods_set_manifest("");hakux_extras_prepare(&disc);nc_mods_install(&disc);assert(nc_cheat_count()==0&&hakux_extras_rows()==2);
 assert(hakux_extras_screenshot());usleep(500000);
 puts("PASS actual mod catalog + native engine: version isolation, defaults off, guarded patches, file overlays, live toggles, once cheats, disable-all and persistent choices");
}
