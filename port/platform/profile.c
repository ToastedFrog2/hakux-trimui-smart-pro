/* Settings are keyed by the original XBE certificate, never a temporary mount path. */
#include "hakux/profile.h"
#include "native/net/net.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static char profile_key[32];

bool hakux_disc_game_key(const NcDisc *disc, char *key, size_t size)
{
    NcDiscFile xbe;
    uint8_t header[0x11c], cert[0xb0];
    if (!nc_disc_find_orig(disc, "\\default.xbe", &xbe) ||
        !nc_disc_read_orig(disc, &xbe, 0, header, sizeof(header))) return false;
    uint32_t base=nc_rd32(header+0x104), va=nc_rd32(header+0x118);
    if (nc_rd32(header)!=0x48454258u || va<base ||
        (uint64_t)(va-base)+sizeof(cert)>xbe.size ||
        !nc_disc_read_orig(disc,&xbe,va-base,cert,sizeof(cert)) ||
        nc_rd32(cert)<sizeof(cert)) return false;
    return snprintf(key,size,"%08X.%u",nc_rd32(cert+8),nc_rd32(cert+0xac))<(int)size;
}

const char *hakux_profile_key(void) { return profile_key; }

static bool scoped(const char *name)
{
    return !strcmp(name,"menu-settings") || !strcmp(name,"controller-map") ||
           !strcmp(name,"render-scale") || !strcmp(name,"network-mode");
}

bool hakux_profile_path(const char *name, char *path, size_t size)
{
    if (profile_key[0] && scoped(name))
        return snprintf(path,size,"profiles/%s/%s",profile_key,name)<(int)size;
    return snprintf(path,size,"%s",name)<(int)size;
}

FILE *hakux_profile_open(const char *name)
{
    char path[160];
    if (!hakux_profile_path(name,path,sizeof(path))) return NULL;
    FILE *f=fopen(path,"r");
    /* Missing overrides inherit the old installation defaults. A broken
     * override never falls through to a different game's choices. */
    if (!f && errno==ENOENT && strcmp(path,name)) f=fopen(name,"r");
    return f;
}

static FILE *override(const char *name)
{
    char path[160];
    if (!profile_key[0] || !hakux_profile_path(name,path,sizeof(path))) return NULL;
    return fopen(path,"r");
}

void hakux_profile_bootstrap(int disc_fd)
{
    profile_key[0]=0;
    NcDisc disc;
    int fd=dup(disc_fd);
    if (fd<0) return;
    if (nc_disc_open(&disc,fd)) hakux_disc_game_key(&disc,profile_key,sizeof(profile_key));
    nc_disc_close(&disc);
    if (!profile_key[0]) return;
    mkdir("profiles",0755);
    char path[96];snprintf(path,sizeof(path),"profiles/%s",profile_key);mkdir(path,0755);
    FILE *f=override("render-scale");
    if (f) {
        char value[32],extra;
        if (fscanf(f,"%31s",value)==1 && fscanf(f," %c",&extra)==EOF &&
            (!strcmp(value,"0.35") || !strcmp(value,"0.5") ||
             !strcmp(value,"0.75") || !strcmp(value,"1")))
            setenv("HAKUX_RENDER_SCALE",value,1);
        fclose(f);
    }
    nc_log("hakuX-menu","settings profile %s",profile_key);
}

void hakux_profile_network(void)
{
    FILE *f=override("network-mode");
    if (f) {
        char value[16],extra;
        if (fscanf(f,"%15s",value)==1 && fscanf(f," %c",&extra)==EOF) {
            if (!strcmp(value,"off")) nc_net_option("net=off");
            else if (!strcmp(value,"lan")) nc_net_option("net=lan");
        }
        fclose(f);
    }
}
