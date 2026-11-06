/* Android-compatible per-title mod catalog, native cheat toggles, and PNG captures. */
#include "hakux/extras.h"
#include "hakux/profile.h"
#include "hakux/capture.h"
#include "native/core/mods.h"
#include "native/core/cheats.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <spawn.h>
#include <sys/wait.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#define MAX_MODS 64
#define MAX_CHEATS 256
static struct {char id[128],name[64],path[512];bool on;unsigned refresh;} mods[MAX_MODS];
static struct {char name[64];bool once,on;} cheats[MAX_CHEATS];
static unsigned nmods,ncheats;
static char game[32]="UNKNOWN",directory[512];
static bool screenshot_busy;
extern char **environ;
extern void hakux_menu_capture_hide(bool hide);
extern void hakux_menu_notice(const char *message);
const char *hakux_extras_game_key(void){return game;}
static char *trim(char *s){while(*s==' '||*s=='\t')s++;size_t n=strlen(s);while(n&&(s[n-1]=='\r'||s[n-1]=='\n'||s[n-1]==' '||s[n-1]=='\t'))s[--n]=0;return s;}
static bool clean_name(const char *s){return *s && strcmp(s,".") && strcmp(s,"..") && !strpbrk(s,"/\\\t\r\n");}
static bool join(char *out,size_t n,const char *a,const char *b){return snprintf(out,n,"%s/%s",a,b)<(int)n;}
static bool regular(const char *p){struct stat s;return !lstat(p,&s)&&S_ISREG(s.st_mode);}
static bool saved_cheat(const char *name){char path[600],line[128];snprintf(path,sizeof(path),"%s/enabled-cheats",directory);FILE *f=fopen(path,"r");if(!f)return false;bool found=false;while(fgets(line,sizeof(line),f))if(!strcmp(trim(line),name))found=true;fclose(f);return found;}
static bool save_cheats(void){char path[600],temp[610];snprintf(path,sizeof(path),"%s/enabled-cheats",directory);snprintf(temp,sizeof(temp),"%s.tmp",path);FILE *f=fopen(temp,"w");if(!f)return false;bool ok=true;for(unsigned i=0;i<nc_cheat_count();i++)if(nc_cheat_on(i)&&fprintf(f,"%s\n",nc_cheat_name(i))<0)ok=false;if(fflush(f)||fsync(fileno(f)))ok=false;if(fclose(f))ok=false;if(ok)ok=rename(temp,path)==0;if(!ok)unlink(temp);return ok;}
static bool save_mod(unsigned i){char path[600],temp[610];snprintf(path,sizeof(path),"%s/enabled",mods[i].path);snprintf(temp,sizeof(temp),"%s.tmp",path);FILE *f=fopen(temp,"w");if(!f)return false;bool ok=fprintf(f,"%d\n",mods[i].on)>0;if(fflush(f)||fsync(fileno(f)))ok=false;if(fclose(f))ok=false;if(ok)ok=rename(temp,path)==0;if(!ok)unlink(temp);return ok;}
static int mod_compare(const void *a,const void *b){return strcmp(((const __typeof__(mods[0])*)a)->id,((const __typeof__(mods[0])*)b)->id);}
static bool files(FILE *out,const char *root,const char *rel,unsigned depth){
 if(depth>16)return false;char path[1024];if(*rel){if(!join(path,sizeof(path),root,rel))return false;}else snprintf(path,sizeof(path),"%s",root);
 DIR *d=opendir(path);if(!d)return access(path,F_OK)!=0;bool ok=true;struct dirent *e;
 while(ok&&(e=readdir(d))){if(e->d_name[0]=='.'||!clean_name(e->d_name))continue;char sub[1024],host[1536];if(*rel){if(!join(sub,sizeof(sub),rel,e->d_name)){ok=false;break;}}else snprintf(sub,sizeof(sub),"%s",e->d_name);if(!join(host,sizeof(host),root,sub)){ok=false;break;}struct stat st;if(lstat(host,&st)){ok=false;break;}if(S_ISDIR(st.st_mode))ok=files(out,root,sub,depth+1);else if(S_ISREG(st.st_mode))ok=fprintf(out,"file\t%s\t%s\n",sub,host)>0;
 }closedir(d);return ok;
}
void hakux_extras_prepare(NcDisc *disc){
 nmods=ncheats=0;snprintf(game,sizeof(game),"UNKNOWN");directory[0]=0;
 if(!hakux_disc_game_key(disc,game,sizeof(game)))return;
 char root[512];const char *where=getenv("HAKUX_MODS_DIR");snprintf(root,sizeof(root),"%s",where&&*where?where:"mods");DIR *d=opendir(root);if(!d)return;struct dirent *e;bool found=false;
 while((e=readdir(d)))if(clean_name(e->d_name)&&!strcasecmp(e->d_name,game)){found=join(directory,sizeof(directory),root,e->d_name);break;}closedir(d);if(!found)return;
 d=opendir(directory);if(!d)return;
 while(nmods<MAX_MODS&&(e=readdir(d))){if(e->d_name[0]=='.'||!clean_name(e->d_name)||strlen(e->d_name)>=sizeof(mods[0].id))continue;char p[512],text[600];if(!join(p,sizeof(p),directory,e->d_name))continue;struct stat st;if(lstat(p,&st)||!S_ISDIR(st.st_mode)||!join(text,sizeof(text),p,"mod.txt")||!regular(text))continue;unsigned i=nmods++;snprintf(mods[i].id,sizeof(mods[i].id),"%s",e->d_name);snprintf(mods[i].name,sizeof(mods[i].name),"%s",e->d_name);snprintf(mods[i].path,sizeof(mods[i].path),"%s",p);mods[i].on=false;mods[i].refresh=0;char enabled[600];join(enabled,sizeof(enabled),p,"enabled");FILE *f=fopen(enabled,"r");int on=0;if(f){if(fscanf(f,"%d",&on)==1)mods[i].on=on==1;fclose(f);}f=fopen(text,"r");char line[1024];if(f){while(fgets(line,sizeof(line),f)){char *s=trim(line);if(*s=='[')break;if(!strncasecmp(s,"name:",5))snprintf(mods[i].name,sizeof(mods[i].name),"%s",trim(s+5));if(!strncasecmp(s,"refresh:",8)){unsigned hz=strtoul(trim(s+8),NULL,10);if(hz>=30&&hz<=240)mods[i].refresh=hz;}}fclose(f);}}
 closedir(d);qsort(mods,nmods,sizeof(mods[0]),mod_compare);
 char cheat_path[600];join(cheat_path,sizeof(cheat_path),directory,"cheats.txt");FILE *f=regular(cheat_path)?fopen(cheat_path,"r"):NULL;char line[1024];int current=-1;
 if(f){while(fgets(line,sizeof(line),f)){char *s=trim(line);size_t len=strlen(s);if(!*s||*s=='#'||strchr(s,'\t'))continue;if(*s=='['&&len>2&&s[len-1]==']'){current=-1;if(ncheats<MAX_CHEATS){s[len-1]=0;current=ncheats++;snprintf(cheats[current].name,sizeof(cheats[current].name),"%s",trim(s+1));for(char *p=cheats[current].name;*p;p++)if(*p=='\t')*p=' ';cheats[current].once=false;cheats[current].on=saved_cheat(cheats[current].name);}}else if(current>=0&&!strcasecmp(s,"once"))cheats[current].once=true;}fclose(f);}
 if(!nmods&&!ncheats)return;
 mkdir("cache",0755);FILE *out=fopen("cache/menu-mods.manifest.tmp","w");if(!out)return;bool ok=true;unsigned refresh=0;
 for(unsigned i=0;i<nmods&&ok;i++)if(mods[i].on){char p[600];join(p,sizeof(p),mods[i].path,"files");ok=files(out,p,"",0);if(mods[i].refresh>refresh)refresh=mods[i].refresh;}
 for(unsigned i=0;i<nmods&&ok;i++){char p[600],xbe_name[128]="";join(p,sizeof(p),mods[i].path,"mod.txt");f=fopen(p,"r");if(!f){ok=false;break;}while(fgets(line,sizeof(line),f)){char *s=trim(line);size_t n=strlen(s);if(!*s||*s=='#'||strchr(s,'\t'))continue;if(*s=='['&&n>2&&s[n-1]==']'){s[n-1]=0;snprintf(xbe_name,sizeof(xbe_name),"%s",trim(s+1));}else if(*xbe_name)if(fprintf(out,"%s\t%s\t%s\t%s\n",mods[i].on?"patch":"patchoff",xbe_name,mods[i].id,s)<0)ok=false;}fclose(f);}
 if(refresh)fprintf(out,"refresh\t%u\n",refresh);
 f=ncheats?fopen(cheat_path,"r"):NULL;current=-1;
 if(f){while(fgets(line,sizeof(line),f)){char *s=trim(line);size_t n=strlen(s);if(!*s||*s=='#'||strchr(s,'\t'))continue;if(*s=='['&&n>2&&s[n-1]==']'){current++;if((unsigned)current<ncheats)fprintf(out,"cheat\t%d\t%d\t%s\n",cheats[current].on,cheats[current].once,cheats[current].name);}else if(current>=0&&(unsigned)current<ncheats&&strcasecmp(s,"once")&&strncasecmp(s,"note:",5))fprintf(out,"code\t%s\n",s);}fclose(f);}
 if(ferror(out)||fflush(out)||fsync(fileno(out)))ok=false;if(fclose(out))ok=false;
 if(ok&&rename("cache/menu-mods.manifest.tmp","cache/menu-mods.manifest")==0){nc_mods_set_manifest("cache/menu-mods.manifest");nc_log("hakuX-menu","%s: %u mods, %u cheats (defaults off)",game,nmods,ncheats);}else {unlink("cache/menu-mods.manifest.tmp");nmods=ncheats=0;nc_log("hakuX-menu","mod manifest could not be prepared; starting without catalog");}
}
unsigned hakux_extras_rows(void){return nmods+nc_cheat_count()+2;}
void hakux_extras_line(unsigned row,char *out,size_t n){
 unsigned nc=nc_cheat_count();
 if(row<nmods)snprintf(out,n,"MOD [%s] %.39s",mods[row].on?"ON":"OFF",mods[row].name);
 else if(row<nmods+nc)snprintf(out,n,"CHEAT [%s] %.36s",nc_cheat_on(row-nmods)?"ON":"OFF",nc_cheat_name(row-nmods));
 else snprintf(out,n,"%s",row==nmods+nc?"DISABLE ALL CHEATS":"BACK TO SETTINGS");
}
bool hakux_extras_choose(unsigned row,char *status,size_t n){
 unsigned nc=nc_cheat_count();
 if(row<nmods){mods[row].on=!mods[row].on;bool ok=save_mod(row);if(!ok)mods[row].on=!mods[row].on;snprintf(status,n,ok?"MOD SAVED - APPLY SETTINGS AND RESTART":"COULD NOT SAVE MOD CHOICE");}
 else if(row<nmods+nc){unsigned i=row-nmods;bool was=nc_cheat_on(i);nc_cheat_set(i,!was);bool ok=directory[0]&&save_cheats();snprintf(status,n,ok?"CHEAT CHANGED - APPLIES ON RESUME":"CHEAT CHANGED - COULD NOT SAVE CHOICE");}
 else if(row==nmods+nc){for(unsigned i=0;i<nc;i++)nc_cheat_set(i,false);bool ok=directory[0]&&save_cheats();snprintf(status,n,ok?"ALL CHEATS DISABLED":"CHEATS DISABLED FOR THIS SESSION");}
 else return true;
 return false;
}
static void *screenshot(void *unused){
 const char *custom=getenv("HAKUX_SCREENSHOT_DIR");char dir[512];snprintf(dir,sizeof(dir),"%s",custom&&*custom?custom:"/mnt/SDCARD/Screenshots/XBOX");
 if(!custom||!*custom)mkdir("/mnt/SDCARD/Screenshots",0755);mkdir(dir,0755);
 char path[768];time_t now=time(NULL);struct tm tm;localtime_r(&now,&tm);char stamp[40];strftime(stamp,sizeof(stamp),"%Y%m%d-%H%M%S",&tm);snprintf(path,sizeof(path),"%s/%s-%s-XXXXXX.png",dir,game,stamp);
 int fd=mkstemps(path,4);bool ok=false;
 if(fd>=0){
  close(fd);hakux_menu_capture_hide(true);usleep(250000);
  const char *tool=getenv("HAKUX_SCREENSHOT_TOOL");if(!tool||!*tool)tool="/usr/trimui/bin/fbscreencap";
  char *args[]={(char*)tool,"-a",path,NULL};pid_t pid;int status;
  if(!posix_spawn(&pid,tool,NULL,NULL,args,environ)) {
   while(waitpid(pid,&status,0)<0) {if(errno!=EINTR){status=-1;break;}}
   ok=status>=0&&WIFEXITED(status)&&WEXITSTATUS(status)==0;
  }
  hakux_menu_capture_hide(false);if(ok)ok=hakux_png_opaque(path);if(!ok)unlink(path);
 }
 __atomic_store_n(&screenshot_busy,false,__ATOMIC_RELEASE);
 hakux_menu_notice(ok?"SCREENSHOT SAVED IN SCREENSHOTS/XBOX":"SCREENSHOT FAILED - CHECK FREE SPACE");return NULL;
}
bool hakux_extras_screenshot(void){bool no=false;if(!__atomic_compare_exchange_n(&screenshot_busy,&no,true,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return false;pthread_t t;if(pthread_create(&t,NULL,screenshot,NULL)){__atomic_store_n(&screenshot_busy,false,__ATOMIC_RELEASE);return false;}pthread_detach(t);return true;}
