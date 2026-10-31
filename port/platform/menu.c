/* TrimUI's menu shares the Vulkan presenter. No second display owner. */
#ifdef HAKUX_XBOX2
#include "hakux/menu.h"
#include "hakux/render_scale.h"
#include "native/app/app.h"
#include "native/core/irq.h"
#include "hw/xbox/hle/host.h"
#include <SDL.h>
#include <fcntl.h>
#include <linux/input.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { RESUME, SCALE, FRAME_SKIP, RESTART, ASPECT, FILTER, FXAA, COLOR, CONTROLS, QUIT, ROWS };
enum { MAP_ACTIONS=16, MAP_RESET=16, MAP_BACK=17, MAP_ROWS=18, MAP_VISIBLE=9 };
/* Output order matches NcPadState: eight analog buttons, eight digital bits.
 * Guide is intentionally absent; menu navigation always uses physical inputs. */
static const SDL_GameControllerButton map_buttons[MAP_ACTIONS]={
    SDL_CONTROLLER_BUTTON_A,SDL_CONTROLLER_BUTTON_B,SDL_CONTROLLER_BUTTON_X,SDL_CONTROLLER_BUTTON_Y,
    SDL_CONTROLLER_BUTTON_RIGHTSHOULDER,SDL_CONTROLLER_BUTTON_LEFTSHOULDER,
    SDL_CONTROLLER_BUTTON_INVALID,SDL_CONTROLLER_BUTTON_INVALID,
    SDL_CONTROLLER_BUTTON_DPAD_UP,SDL_CONTROLLER_BUTTON_DPAD_DOWN,
    SDL_CONTROLLER_BUTTON_DPAD_LEFT,SDL_CONTROLLER_BUTTON_DPAD_RIGHT,
    SDL_CONTROLLER_BUTTON_START,SDL_CONTROLLER_BUTTON_BACK,
    SDL_CONTROLLER_BUTTON_LEFTSTICK,SDL_CONTROLLER_BUTTON_RIGHTSTICK};
static const char *map_outputs[MAP_ACTIONS]={"XBOX A","XBOX B","XBOX X","XBOX Y","BLACK","WHITE",
    "LEFT TRIGGER","RIGHT TRIGGER","DPAD UP","DPAD DOWN","DPAD LEFT","DPAD RIGHT",
    "START","BACK","LEFT STICK CLICK","RIGHT STICK CLICK"};
static const char *map_sources[MAP_ACTIONS+1]={"A","B","X","Y","R1","L1","L2","R2",
    "DPAD UP","DPAD DOWN","DPAD LEFT","DPAD RIGHT","START","SELECT","L3","R3","DISABLED"};
static unsigned char controller_map[MAP_ACTIONS];
static const float scales[] = {.35f,.5f,.75f,1.0f};
static const char *scale_names[] = {"0.35X", "0.5X", "0.75X", "1X"};
static const char *aspect_names[] = {"AUTO", "4:3", "16:9", "STRETCH"};
static const char *color_names[] = {"ORIGINAL", "WARM", "COOL", "BRIGHT"};
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static struct {
    bool open, ready, key, raw_key, guide, block, paused_before, confirm, mapping;
    int map_row;
    int row, scale, aspect, filter, fxaa, color, frame_skip;
    unsigned previous, repeat_button;
    Uint32 repeat_at;
    uint64_t revision;
    char status[100];
} ui;
static int events[8], event_count;

static bool write_setting(const char *name, const char *value)
{
    char path[128]; snprintf(path,sizeof(path),"%s.tmp",name);
    FILE *f=fopen(path,"wb");
    if (!f) return false;
    bool ok=fprintf(f,"%s\n",value)>0 && fflush(f)==0;
    if (ok) ok=fsync(fileno(f))==0;
    if (fclose(f)) ok=false;
    if (ok) ok=rename(path,name)==0;
    if (!ok) unlink(path);
    return ok;
}

static bool persist(void)
{
    char value[80];
    snprintf(value,sizeof(value),"%d %d %d %d %d",ui.aspect,ui.filter,ui.fxaa,ui.color,ui.frame_skip);
    return write_setting("menu-settings",value);
}

static void map_defaults(void)
{
    for(int i=0;i<MAP_ACTIONS;i++)controller_map[i]=i;
}
static void map_load(void)
{
    map_defaults();
    FILE *f=fopen("controller-map","r");
    if(!f)return;
    int version,n;unsigned char candidate[MAP_ACTIONS];
    bool ok=fscanf(f,"%d",&version)==1 && version==1;
    for(int i=0;ok && i<MAP_ACTIONS;i++) {
        ok=fscanf(f,"%d",&n)==1 && n>=0 && n<=MAP_ACTIONS;
        if(ok)candidate[i]=n;
    }
    char extra;
    if(ok && fscanf(f," %c",&extra)!=EOF)ok=false;
    if(ok)memcpy(controller_map,candidate,sizeof(controller_map));
    fclose(f);
}
static bool map_save(void)
{
    char value[100];int len=snprintf(value,sizeof(value),"1");
    for(int i=0;i<MAP_ACTIONS;i++)len+=snprintf(value+len,sizeof(value)-len," %u",controller_map[i]);
    return write_setting("controller-map",value);
}
void hakux_menu_map_buttons(SDL_GameController *pad,uint8_t values[16])
{
    uint8_t physical[MAP_ACTIONS+1]={0};
    if(pad)for(int i=0;i<MAP_ACTIONS;i++) {
        if(i==6 || i==7) {
            int n=SDL_GameControllerGetAxis(pad,i==6?SDL_CONTROLLER_AXIS_TRIGGERLEFT:SDL_CONTROLLER_AXIS_TRIGGERRIGHT);
            physical[i]=n>0?n/128:0;
        } else physical[i]=SDL_GameControllerGetButton(pad,map_buttons[i])?255:0;
    }
    pthread_mutex_lock(&mu);
    for(int i=0;i<MAP_ACTIONS;i++)values[i]=physical[controller_map[i]];
    pthread_mutex_unlock(&mu);
}

void hakux_menu_init(int argc, char **argv)
{
    map_load();
    float current=hle_scale_clamp(hle_host_render_scale());
    ui.scale=current==.35f?0:current==.5f?1:current==.75f?2:3;
    FILE *f=fopen("menu-settings","r");
    int a,b,c,d,e=0;
    if(f) {
        int n=fscanf(f,"%d %d %d %d %d",&a,&b,&c,&d,&e);
        if(n>=4 &&
           a>=0 && a<4 && b>=0 && b<2 && c>=0 && c<2 && d>=0 && d<4) {
            ui.aspect=a;ui.filter=b;ui.fxaa=c;ui.color=d;
            ui.frame_skip=n==5 && e==1 ? 1 : 0;
        }
        fclose(f);
    }
    for(int i=0;i<8;i++) {
        char path[64];snprintf(path,sizeof(path),"/dev/input/event%d",i);
        int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC);
        if(fd>=0)events[event_count++]=fd;
    }
    fprintf(stderr,"hakuX menu: Menu/Guide opens settings; resolution changes restart the game\n");
}

void hakux_menu_ready(void) { pthread_mutex_lock(&mu);ui.ready=true;pthread_mutex_unlock(&mu); }
void hakux_menu_key(bool down) { pthread_mutex_lock(&mu);ui.key=down;pthread_mutex_unlock(&mu); }

static void toggle(bool open)
{
    ui.open=open;ui.confirm=false;ui.mapping=false;ui.block=true;ui.status[0]=0;ui.revision++;
    if(open) { ui.paused_before=nc_paused();nc_pause_set(true); }
    else nc_pause_set(ui.paused_before);
    fprintf(stderr,"hakuX menu: %s\n",open?"open":"resume");
}

static void restart(void)
{
    /* Render surfaces are recreated by a fresh process at the chosen scale. */
    char scale[20];snprintf(scale,sizeof(scale),"%g",scales[ui.scale]);
    if(!write_setting("render-scale",scale)) {
        snprintf(ui.status,sizeof(ui.status),"COULD NOT SAVE RENDER SCALE");return;
    }
    if(!write_setting("menu-restart","restart")) {
        snprintf(ui.status,sizeof(ui.status),"COULD NOT WRITE RESTART REQUEST");return;
    }
    /* The launcher starts a fresh process after this one closes every GPU
     * and input descriptor. MainUI remains suspended across the restart. */
    fprintf(stderr,"hakuX menu: restarting scale=%s\n",scale);
    _exit(20);
}

static void change(int delta)
{
    int *p=NULL,limit=0;
    switch(ui.row) {
        case SCALE:p=&ui.scale;limit=sizeof(scales)/sizeof(scales[0]);break;
        case FRAME_SKIP:p=&ui.frame_skip;limit=2;break;
        case ASPECT:p=&ui.aspect;limit=4;break;
        case FILTER:p=&ui.filter;limit=2;break;
        case FXAA:p=&ui.fxaa;limit=2;break;
        case COLOR:p=&ui.color;limit=4;break;
        default:return;
    }
    *p=(*p+delta+limit)%limit;
    if(ui.row==SCALE) snprintf(ui.status,sizeof(ui.status),"SELECT APPLY SCALE TO RESTART THE GAME");
    else if(!persist())snprintf(ui.status,sizeof(ui.status),"SETTINGS CHANGED BUT COULD NOT BE SAVED");
    else if(ui.row==FRAME_SKIP)snprintf(ui.status,sizeof(ui.status),"DISPLAY SKIP APPLIED - GAME RENDERING IS PRESERVED");
    else snprintf(ui.status,sizeof(ui.status),"DISPLAY SETTING APPLIED");
}

bool hakux_menu_input(SDL_GameController *pad)
{
    pthread_mutex_lock(&mu);
    for(int i=0;i<event_count;i++) {
        struct input_event e;
        while(read(events[i],&e,sizeof(e))==sizeof(e))
            if(e.type==EV_KEY && (e.code==BTN_MODE || e.code==KEY_MENU) && e.value!=2)ui.raw_key=e.value!=0;
    }
    bool key=ui.key||ui.raw_key||(pad&&SDL_GameControllerGetButton(pad,SDL_CONTROLLER_BUTTON_GUIDE));
    bool toggled=key && !ui.guide && ui.ready;
    if(toggled)toggle(!ui.open);
    ui.guide=key;
    unsigned buttons=0;
    if(pad) {
        const SDL_GameControllerButton b[]={SDL_CONTROLLER_BUTTON_DPAD_UP,SDL_CONTROLLER_BUTTON_DPAD_DOWN,
            SDL_CONTROLLER_BUTTON_DPAD_LEFT,SDL_CONTROLLER_BUTTON_DPAD_RIGHT,SDL_CONTROLLER_BUTTON_A,SDL_CONTROLLER_BUTTON_B};
        for(unsigned i=0;i<6;i++)if(SDL_GameControllerGetButton(pad,b[i]))buttons|=1u<<i;
    }
    unsigned edge=buttons&~ui.previous;
    if(toggled)edge=0; /* A held gameplay button cannot activate the menu. */
    Uint32 now=SDL_GetTicks();
    if(buttons!=ui.previous) {ui.repeat_button=buttons&15;ui.repeat_at=now+350;}
    else if(ui.repeat_button && (Sint32)(now-ui.repeat_at)>=0) {edge|=ui.repeat_button;ui.repeat_at=now+140;}
    ui.previous=buttons;
    if(ui.open && ui.mapping) {
        if(edge&32) {ui.mapping=false;ui.status[0]=0;ui.revision++;}
        else if(edge&3) {ui.map_row=(ui.map_row+(edge&1?-1:1)+MAP_ROWS)%MAP_ROWS;ui.status[0]=0;ui.revision++;}
        else if(edge&(12|16)) {
            if(ui.map_row<MAP_ACTIONS) {
                controller_map[ui.map_row]=(controller_map[ui.map_row]+(edge&4?MAP_ACTIONS:1))%(MAP_ACTIONS+1);
                snprintf(ui.status,sizeof(ui.status),map_save()?"MAPPING SAVED - APPLIES WHEN YOU RESUME":"MAPPING CHANGED BUT COULD NOT BE SAVED");
            } else if(edge&16) {
                if(ui.map_row==MAP_BACK) {ui.mapping=false;ui.status[0]=0;}
                else {map_defaults();snprintf(ui.status,sizeof(ui.status),map_save()?"DEFAULT MAPPING SAVED":"DEFAULTS APPLIED BUT COULD NOT BE SAVED");}
            }
            ui.revision++;
        }
    } else if(ui.open) {
        if(edge&32) { if(ui.confirm)ui.confirm=false;else toggle(false);ui.revision++; }
        else if(edge&3) {ui.row=(ui.row+(edge&1?-1:1)+ROWS)%ROWS;ui.confirm=false;ui.status[0]=0;ui.revision++;}
        else if(edge&12) {ui.confirm=false;change(edge&4?-1:1);ui.revision++;}
        else if(edge&16) {
            if(ui.row==RESUME)toggle(false);
            else if(ui.row==CONTROLS) {ui.mapping=true;ui.map_row=0;ui.status[0]=0;}
            else if(ui.row==RESTART || ui.row==QUIT) {
                if(!ui.confirm)ui.confirm=true;
                else if(ui.row==QUIT) {fprintf(stderr,"hakuX menu: exit\n");_exit(0);}
                else restart();
            } else change(1);
            ui.revision++;
        }
    }
    /* Suppress the close button until released, including axes/triggers. */
    if(ui.block && !ui.open) {
        bool neutral=!buttons&&!key;
        if(pad) {
            for(int i=0;i<SDL_CONTROLLER_BUTTON_MAX;i++)if(SDL_GameControllerGetButton(pad,i))neutral=false;
            for(int i=0;i<SDL_CONTROLLER_AXIS_MAX;i++)if(abs(SDL_GameControllerGetAxis(pad,i))>8000)neutral=false;
        }
        if(neutral)ui.block=false;
    }
    bool consume=ui.open||ui.block;
    pthread_mutex_unlock(&mu);
    return consume;
}

void hakux_menu_video(void)
{
    pthread_mutex_lock(&mu);
    nc_present_set_aspect(ui.aspect);nc_present_set_upscale(ui.filter);nc_present_set_fxaa(ui.fxaa);
    pthread_mutex_unlock(&mu);
}
uint64_t hakux_menu_key_revision(void)
{
    pthread_mutex_lock(&mu);uint64_t n=ui.revision;pthread_mutex_unlock(&mu);return n;
}
unsigned hakux_menu_frame_skip(void)
{
    pthread_mutex_lock(&mu);
    unsigned n=ui.open ? 0 : (unsigned)ui.frame_skip;
    pthread_mutex_unlock(&mu);
    return n;
}
void hakux_menu_ramp(uint8_t dst[3][256],const uint8_t src[3][256])
{
    pthread_mutex_lock(&mu);int color=ui.color;pthread_mutex_unlock(&mu);
    for(int c=0;c<3;c++)for(int i=0;i<256;i++) {
        float n=src[c][i];
        if(color==1)n*=c==2?.88f:c==1?.96f:1.0f;
        if(color==2)n*=c==0?.88f:c==1?.96f:1.0f;
        if(color==3)n*=1.15f;
        dst[c][i]=(uint8_t)(n>255?255:n);
    }
}

/* An original 5x7 block alphabet. Horizontal runs are batched into one
 * clear command per text colour, only when the visible menu changes. */
static const uint8_t glyphs[36][7]={
 {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
 {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
 {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
 {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
 {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
 {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
 {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
 {17,17,17,17,17,10,4},{17,17,17,21,21,27,17},{17,17,10,4,10,17,17},
 {17,17,10,4,4,4,4},{31,1,2,4,8,16,31},
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
 {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
 {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
 {14,17,17,15,1,1,14}};
static unsigned bits(char c,int y)
{
    if(c>='a'&&c<='z')c-=32;
    if(c>='A'&&c<='Z')return glyphs[c-'A'][y];
    if(c>='0'&&c<='9')return glyphs[26+c-'0'][y];
    if(c=='.')return y==6?4:0;
    if(c==':')return y==2||y==5?4:0;
    if(c=='-')return y==3?14:0;
    if(c=='/')return 1u<<(y<5?y:4);
    if(c=='(')return y==0||y==6?2:4;
    if(c==')')return y==0||y==6?8:4;
    if(c=='?')return y==0?14:y==1?17:y==2?2:y==3?4:y==6?4:0;
    return 0;
}
static VkClearRect rects[8192];
static unsigned nrect;
static void box(int x,int y,int w,int h,uint32_t iw,uint32_t ih)
{
    if(nrect>=8192)return;
    int x1=x*(int)iw/1280,y1=y*(int)ih/720,x2=(x+w)*(int)iw/1280,y2=(y+h)*(int)ih/720;
    if(x1<0)x1=0;if(y1<0)y1=0;if(x2>(int)iw)x2=iw;if(y2>(int)ih)y2=ih;
    if(x2>x1&&y2>y1)rects[nrect++]=(VkClearRect){.rect={{x1,y1},{x2-x1,y2-y1}},.layerCount=1};
}
static void text(int x,int y,const char *s,int size,uint32_t w,uint32_t h)
{
    for(int i=0;s[i]&&i<95;i++)for(int row=0;row<7;row++) {
        unsigned b=bits(s[i],row);
        for(int col=0;col<5;) {
            if(!(b&(16u>>col))) {col++;continue;}
            int start=col;while(col<5&&(b&(16u>>col)))col++;
            box(x+(i*6+start)*size,y+row*size,(col-start)*size,size,w,h);
        }
    }
}
static void clear_rects(VkCommandBuffer cb,const struct VolkDeviceTable *t,float r,float g,float b)
{
    if(nrect) {
        VkClearAttachment a={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,.clearValue={.color={{r,g,b,1}}}};
        t->vkCmdClearAttachments(cb,1,&a,nrect,rects);
    }
    nrect=0;
}
void hakux_menu_draw(VkCommandBuffer cb,const struct VolkDeviceTable *t,uint32_t w,uint32_t h)
{
    pthread_mutex_lock(&mu);
    if(!ui.open) {pthread_mutex_unlock(&mu);return;}
    box(100,36,1080,648,w,h);clear_rects(cb,t,.025f,.04f,.07f);
    int first=ui.map_row>=MAP_VISIBLE?ui.map_row-MAP_VISIBLE+1:0;
    box(120,125+(ui.mapping?ui.map_row-first:ui.row)*40,1040,34,w,h);clear_rects(cb,t,.08f,.22f,.34f);
    text(140,64,ui.mapping?"XBOX - CONTROLLER MAPPING":"XBOX - SETTINGS",3,w,h);
    char lines[ROWS][80]={[RESUME]="RESUME GAME",[RESTART]="APPLY SCALE AND RESTART GAME",[CONTROLS]="CONTROLLER MAPPING"};
    snprintf(lines[SCALE],80,"RENDER SCALE: %s (RESTART)",scale_names[ui.scale]);
    snprintf(lines[FRAME_SKIP],80,"FRAME SKIP: %s",ui.frame_skip?"SKIP 1 (DISPLAY)":"OFF");
    snprintf(lines[ASPECT],80,"SCREEN SHAPE: %s",aspect_names[ui.aspect]);
    snprintf(lines[FILTER],80,"UPSCALE FILTER: %s",ui.filter?"SGSR":"BILINEAR");
    snprintf(lines[FXAA],80,"EDGE SMOOTHING: %s",ui.fxaa?"FXAA ON":"OFF");
    snprintf(lines[COLOR],80,"COLOR: %s",color_names[ui.color]);
    snprintf(lines[QUIT],80,"EXIT GAME");
    if(ui.mapping) {
        for(int i=first;i<MAP_ROWS && i<first+MAP_VISIBLE;i++) {
            char line[80];
            if(i<MAP_ACTIONS)snprintf(line,sizeof(line),"%s: %s",map_outputs[i],map_sources[controller_map[i]]);
            else snprintf(line,sizeof(line),"%s",i==MAP_RESET?"RESET TO DEFAULTS":"BACK TO SETTINGS");
            text(144,133+(i-first)*40,line,3,w,h);
        }
    } else for(int i=0;i<ROWS;i++)text(144,133+i*40,lines[i],3,w,h);
    text(144,550,"UP/DOWN SELECT   LEFT/RIGHT CHANGE   A CHOOSE",2,w,h);
    text(144,574,ui.mapping?"B BACK   MENU RESUME   START AND SELECT HOLD TO EXIT":"B OR MENU RESUME   SCALE CHANGES RESTART GAME",2,w,h);
    text(144,618,ui.confirm?"A CONFIRM - UNSAVED PROGRESS WILL BE LOST : B CANCEL":ui.status,2,w,h);
    clear_rects(cb,t,.88f,.94f,1);
    pthread_mutex_unlock(&mu);
}
#endif
