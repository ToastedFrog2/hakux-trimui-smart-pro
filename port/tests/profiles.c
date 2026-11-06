#include "../platform/profile.c"
#include <assert.h>
#include <fcntl.h>
#include <stdarg.h>
static char net[32];
bool nc_net_option(const char *s){snprintf(net,sizeof(net),"%s",s);return true;}
void nc_log(const char *tag,const char *fmt,...){(void)tag;(void)fmt;}
static void put(const char *path,const char *value){FILE *f=fopen(path,"w");assert(f);assert(fputs(value,f)>=0);assert(!fclose(f));}
static void expect(const char *name,const char *value){FILE *f=hakux_profile_open(name);assert(f);char line[128];assert(fgets(line,sizeof(line),f));fclose(f);assert(!strcmp(line,value));}
int main(int argc,char **argv)
{
    assert(argc==3);int a=open(argv[1],O_RDONLY),b=open(argv[2],O_RDONLY);assert(a>=0&&b>=0);
    put("menu-settings","0 0 0 0 0\n");put("controller-map","1 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15\n");
    setenv("HAKUX_RENDER_SCALE","0.5",1);
    hakux_profile_bootstrap(a);assert(!strcmp(hakux_profile_key(),"12345678.1"));
    expect("menu-settings","0 0 0 0 0\n");
    char path[160];assert(hakux_profile_path("menu-settings",path,sizeof(path)));put(path,"2 1 0 3 1\n");
    assert(hakux_profile_path("controller-map",path,sizeof(path)));put(path,"1 1 0 2 3 4 5 6 7 8 9 10 11 12 13 14 15\n");
    assert(hakux_profile_path("render-scale",path,sizeof(path)));put(path,"0.75\n");
    assert(hakux_profile_path("network-mode",path,sizeof(path)));put(path,"lan\n");
    hakux_profile_bootstrap(a);hakux_profile_network();assert(!strcmp(getenv("HAKUX_RENDER_SCALE"),"0.75")&&!strcmp(net,"net=lan"));
    expect("menu-settings","2 1 0 3 1\n");expect("controller-map","1 1 0 2 3 4 5 6 7 8 9 10 11 12 13 14 15\n");
    setenv("HAKUX_RENDER_SCALE","0.5",1);strcpy(net,"net=off");
    hakux_profile_bootstrap(b);hakux_profile_network();assert(!strcmp(hakux_profile_key(),"12345678.2"));
    assert(!strcmp(getenv("HAKUX_RENDER_SCALE"),"0.5")&&!strcmp(net,"net=off"));
    expect("menu-settings","0 0 0 0 0\n");expect("controller-map","1 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15\n");
    assert(hakux_profile_path("render-scale",path,sizeof(path)));put(path,"0.35; touch INJECTED\n");
    assert(hakux_profile_path("network-mode",path,sizeof(path)));put(path,"lan\noff\n");
    hakux_profile_bootstrap(b);hakux_profile_network();assert(!strcmp(getenv("HAKUX_RENDER_SCALE"),"0.5")&&!strcmp(net,"net=off"));assert(access("INJECTED",F_OK));
    put("profiles/12345678.2/menu-settings","");FILE *f=hakux_profile_open("menu-settings");assert(f&&fgetc(f)==EOF);fclose(f);
    hakux_profile_bootstrap(a);expect("menu-settings","2 1 0 3 1\n");
    assert(hakux_profile_path("menu-restart",path,sizeof(path))&&!strcmp(path,"menu-restart"));
    assert(pread(a,path,4,0)==4); /* Probe closed only its duplicate descriptor. */
    close(a);close(b);puts("PASS actual per-game profiles: XBE identity, version isolation, legacy defaults, scoped controls/video/scale/LAN, validated settings and descriptor ownership");
}
