#include "../platform/menu.c"
#include <assert.h>
#include "native/dev/usb.h"
#include <sys/wait.h>
static Uint32 ticks;
static Uint8 buttons[SDL_CONTROLLER_BUTTON_MAX];
static Sint16 axes[SDL_CONTROLLER_AXIS_MAX];
static bool paused;
static void teardown_marker(void) {FILE *f=fopen("UNSAFE-TEARDOWN","w");if(f){fputs("ran",f);fclose(f);}}
static int aspect,filter,fxaa;
Uint32 SDL_GetTicks(void) { return ticks; }
Uint8 SDL_GameControllerGetButton(SDL_GameController *p,SDL_GameControllerButton b) { return buttons[b]; }
Sint16 SDL_GameControllerGetAxis(SDL_GameController *p,SDL_GameControllerAxis a) { return axes[a]; }
static NcPadState forwarded;
void nc_pad_set(unsigned p,const NcPadState *s) {assert(p==0);forwarded=*s;}
#include "pad-state.inc"
static float host_scale=.5f;
float hle_host_render_scale(void) {return host_scale;}
void nc_pause_set(bool b) {paused=b;}
bool nc_paused(void) {return paused;}
void nc_present_set_aspect(int n) {aspect=n;}
void nc_present_set_upscale(int n) {filter=n;}
void nc_present_set_fxaa(bool n) {fxaa=n;}
static unsigned draws,rect_count;
static unsigned bound_w,bound_h;
static void VKAPI_CALL record(VkCommandBuffer cb,uint32_t n,const VkClearAttachment *a,uint32_t m,const VkClearRect *r)
{
    assert(n==1&&a->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&m>0&&m<=8192);
    for(unsigned i=0;i<m;i++) {
        assert(r[i].rect.offset.x>=0&&r[i].rect.offset.y>=0&&r[i].layerCount==1);
        assert((unsigned)r[i].rect.offset.x+r[i].rect.extent.width<=bound_w);
        assert((unsigned)r[i].rect.offset.y+r[i].rect.extent.height<=bound_h);
    }
    draws++;rect_count+=m;
}
static SDL_GameController *pad=(SDL_GameController*)(uintptr_t)1;
static void press(SDL_GameControllerButton b) {
    buttons[b]=1;hakux_menu_input(pad);buttons[b]=0;hakux_menu_input(pad);
}
static void menu(void) {hakux_menu_key(true);hakux_menu_input(pad);hakux_menu_key(false);hakux_menu_input(pad);}
int main(void)
{
    char *argv[]={"hakux.aarch64","/tmp/hakux-disc.RANDOM/Halo 2.iso","hdd=hdd",NULL};
    hakux_menu_init(3,argv);hakux_menu_ready();
    assert(ui.scale==1&&!ui.open);
    assert(ui.aspect==0&&ui.filter==0&&ui.fxaa==0&&ui.color==0&&ui.frame_skip==0);
    /* Every fresh default forwards exactly one Xbox action. In particular,
     * L3/R3 cannot activate a D-pad bit or inherit a previous card's layout. */
    for(int i=0;i<MAP_ACTIONS;i++) {
        assert(controller_map[i]==i);
        if(i==6 || i==7)axes[i==6?SDL_CONTROLLER_AXIS_TRIGGERLEFT:SDL_CONTROLLER_AXIS_TRIGGERRIGHT]=32767;
        else buttons[map_buttons[i]]=1;
        pad_state(pad);
        assert(forwarded.buttons==(i>=8?1u<<(i-8):0));
        for(int j=0;j<8;j++)assert(forwarded.analog[j]==(i==j?255:0));
        memset(buttons,0,sizeof(buttons));memset(axes,0,sizeof(axes));
    }
    /* Actual mapping, including analog trigger pressure and disabled inputs. */
    uint8_t mapped[16];
    buttons[SDL_CONTROLLER_BUTTON_A]=1;axes[SDL_CONTROLLER_AXIS_TRIGGERLEFT]=16384;
    hakux_menu_map_buttons(pad,mapped);
    assert(mapped[0]==255&&mapped[1]==0&&mapped[6]==128&&mapped[7]==0);
    pad_state(pad);assert(forwarded.analog[0]==255&&forwarded.analog[6]==128);
    buttons[SDL_CONTROLLER_BUTTON_A]=0;axes[SDL_CONTROLLER_AXIS_TRIGGERLEFT]=0;
    menu();ui.row=CONTROLS;press(SDL_CONTROLLER_BUTTON_A);
    assert(ui.mapping&&paused);
    press(SDL_CONTROLLER_BUTTON_DPAD_RIGHT);assert(controller_map[0]==1);
    buttons[SDL_CONTROLLER_BUTTON_B]=1;hakux_menu_map_buttons(pad,mapped);
    assert(mapped[0]==255&&mapped[1]==255); /* Duplicate assignments allowed. */
    controller_map[12]=1;pad_state(pad);assert(forwarded.buttons&NC_PAD_START);controller_map[12]=12;
    buttons[SDL_CONTROLLER_BUTTON_B]=0;
    map_defaults();map_load();assert(controller_map[0]==1); /* Saved to disk. */
    ui.map_row=6;press(SDL_CONTROLLER_BUTTON_DPAD_LEFT);assert(controller_map[6]==5);
    buttons[SDL_CONTROLLER_BUTTON_LEFTSHOULDER]=1;hakux_menu_map_buttons(pad,mapped);
    assert(mapped[6]==255);buttons[SDL_CONTROLLER_BUTTON_LEFTSHOULDER]=0;
    ui.map_row=0;controller_map[0]=0;press(SDL_CONTROLLER_BUTTON_DPAD_LEFT);
    assert(controller_map[0]==MAP_ACTIONS);
    buttons[SDL_CONTROLLER_BUTTON_A]=1;hakux_menu_map_buttons(pad,mapped);assert(mapped[0]==0);
    buttons[SDL_CONTROLLER_BUTTON_A]=0;
    /* Remapping B never changes the physical B navigation control. */
    controller_map[1]=MAP_ACTIONS;press(SDL_CONTROLLER_BUTTON_B);assert(!ui.mapping&&ui.open);
    ui.row=CONTROLS;press(SDL_CONTROLLER_BUTTON_A);ui.map_row=MAP_RESET;press(SDL_CONTROLLER_BUTTON_A);
    for(int i=0;i<16;i++)assert(controller_map[i]==i);
    ui.map_row=MAP_BACK;press(SDL_CONTROLLER_BUTTON_A);assert(!ui.mapping);
    press(SDL_CONTROLLER_BUTTON_B);assert(!ui.open);
    assert(write_setting("controller-map","1 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 17"));
    map_load();for(int i=0;i<16;i++)assert(controller_map[i]==i);
    assert(write_setting("controller-map","1 1 0 2"));map_load();assert(controller_map[0]==0);
    assert(write_setting("controller-map","2 1 0 2 3 4 5 6 7 8 9 10 11 12 13 14 15"));map_load();assert(controller_map[0]==0);
    assert(map_save());
    ui.row=SCALE;change(1);assert(ui.scale==2 && scales[ui.scale]==.75f);
    change(1);assert(ui.scale==3 && scales[ui.scale]==1.0f);
    change(1);assert(ui.scale==0);change(-1);assert(ui.scale==3);
    ui.scale=1;ui.row=RESUME;
    assert(ui.frame_skip==0 && hakux_menu_frame_skip()==0);
    assert(write_setting("render-scale","0.5"));
    menu();assert(ui.open&&paused);
    press(SDL_CONTROLLER_BUTTON_DPAD_DOWN);assert(ui.row==SCALE);
    press(SDL_CONTROLLER_BUTTON_DPAD_LEFT);assert(ui.scale==0);
    FILE *f=fopen("render-scale","r");float value;assert(fscanf(f,"%f",&value)==1&&value==.5f);fclose(f);
    assert(hle_host_render_scale()==.5f); /* The running surface scale was untouched. */
    press(SDL_CONTROLLER_BUTTON_B);assert(!ui.open&&!paused);
    buttons[SDL_CONTROLLER_BUTTON_A]=1;menu();assert(ui.open&&ui.scale==0);
    buttons[SDL_CONTROLLER_BUTTON_A]=0;hakux_menu_input(pad);
    ui.row=ASPECT;press(SDL_CONTROLLER_BUTTON_DPAD_RIGHT);
    ui.row=FILTER;press(SDL_CONTROLLER_BUTTON_A);
    ui.row=FXAA;press(SDL_CONTROLLER_BUTTON_A);
    ui.row=FRAME_SKIP;press(SDL_CONTROLLER_BUTTON_DPAD_RIGHT);
    assert(ui.frame_skip==1 && hakux_menu_frame_skip()==0); /* never skip menu */
    f=fopen("menu-settings","r");int a,b,c,d,saved_skip;
    assert(fscanf(f,"%d %d %d %d %d",&a,&b,&c,&d,&saved_skip)==5 && saved_skip==1);fclose(f);
    menu();assert(!ui.open && hakux_menu_frame_skip()==1);
    menu();assert(ui.open && hakux_menu_frame_skip()==0);
    hakux_menu_video();assert(aspect==1&&filter==1&&fxaa==1);
    uint8_t src[3][256],dst[3][256];
    for(int c=0;c<3;c++)for(int i=0;i<256;i++)src[c][i]=i;
    ui.color=0;hakux_menu_ramp(dst,src);assert(!memcmp(src,dst,sizeof(src)));
    ui.color=1;hakux_menu_ramp(dst,src);assert(dst[0][255]==255&&dst[2][255]<255);
    ui.color=3;hakux_menu_ramp(dst,src);assert(dst[0][255]==255&&dst[0][100]==115);
    struct VolkDeviceTable table={.vkCmdClearAttachments=record};
    bound_w=1280;bound_h=720;hakux_menu_draw((VkCommandBuffer)1,&table,bound_w,bound_h);
    assert(draws==3&&rect_count>500);
    bound_w=640;bound_h=360;hakux_menu_draw((VkCommandBuffer)1,&table,bound_w,bound_h);
    assert(draws==6);
    ui.mapping=true;
    for(int i=0;i<MAP_ROWS;i++) {
        ui.map_row=i;hakux_menu_draw((VkCommandBuffer)1,&table,bound_w,bound_h);
    }
    ui.mapping=false;
    /* A close action cannot reach the emulated controller until released. */
    buttons[SDL_CONTROLLER_BUTTON_B]=1;assert(hakux_menu_input(pad));assert(!ui.open);
    assert(hakux_menu_input(pad));buttons[SDL_CONTROLLER_BUTTON_B]=0;assert(!hakux_menu_input(pad));
    menu();ui.row=RESTART;press(SDL_CONTROLLER_BUTTON_A);assert(ui.confirm);
    ui.scale=2; /* Confirm the new scale is actually written for the launcher. */
    pid_t child=fork();assert(child>=0);
    if(!child) {atexit(teardown_marker);press(SDL_CONTROLLER_BUTTON_A);_exit(99);}
    int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==20);
    assert(access("UNSAFE-TEARDOWN",F_OK)!=0);
    f=fopen("render-scale","r");assert(fscanf(f,"%f",&value)==1&&value==.75f);fclose(f);
    char request[80];f=fopen("menu-restart","r");assert(fgets(request,sizeof(request),f)&&!strcmp(request,"restart\n"));fclose(f);
    child=fork();assert(child>=0);
    if(!child) {atexit(teardown_marker);ui.row=QUIT;ui.confirm=false;press(SDL_CONTROLLER_BUTTON_A);press(SDL_CONTROLLER_BUTTON_A);_exit(99);}
    assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
    assert(access("UNSAFE-TEARDOWN",F_OK)!=0);
    /* Exercise the physical Menu/Guide evdev path independently of SDL mappings. */
    int pipefd[2];assert(pipe(pipefd)==0);fcntl(pipefd[0],F_SETFL,O_NONBLOCK);
    events[0]=pipefd[0];event_count=1;ui.open=false;ui.guide=false;ui.raw_key=false;
    struct input_event e={.type=EV_KEY,.code=BTN_MODE,.value=1};
    assert(write(pipefd[1],&e,sizeof(e))==sizeof(e));hakux_menu_input(NULL);assert(ui.open);
    close(pipefd[0]);close(pipefd[1]);
    /* Old four-value settings stay valid; the new fifth value is optional. */
    ui=(typeof(ui)){0};event_count=0;
    assert(write_setting("menu-settings","2 1 0 3"));hakux_menu_init(3,argv);
    assert(ui.aspect==2 && ui.filter==1 && ui.color==3 && ui.frame_skip==0);
    assert(write_setting("menu-settings","1 0 1 2 1"));hakux_menu_init(3,argv);
    assert(ui.aspect==1 && ui.color==2 && ui.frame_skip==1);
    assert(write_setting("menu-settings","1 0 1 2 99"));hakux_menu_init(3,argv);
    assert(ui.aspect==1 && ui.frame_skip==0);
    host_scale=.75f;hakux_menu_init(3,argv);assert(ui.scale==2);
    host_scale=1.0f;hakux_menu_init(3,argv);assert(ui.scale==3);
    puts("PASS actual menu: navigation, pause/resume, input suppression, live display settings, bounded Vulkan text, confirmed restart, physical Guide events");
}
