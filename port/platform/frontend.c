/* TrimUI frontend: existing SDL2 controller support, direct Vulkan display. */
#include "native/app/app.h"
#include "native/dev/usb.h"
#include <SDL.h>
#include <android/native_window.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "hakux/menu.h"

void *nc_vk_layers(void *p) { return p; }
void nc_vsync_start(void) { /* Core uses its monotonic vblank clock. */ }

/* Always physical inputs, independent of mapping or an open settings menu. */
static void emergency_exit(SDL_GameController *pad) {
    static Uint32 held;
    if (pad && SDL_GameControllerGetButton(pad,SDL_CONTROLLER_BUTTON_START) &&
        SDL_GameControllerGetButton(pad,SDL_CONTROLLER_BUTTON_BACK)) {
        if (!held) held=SDL_GetTicks();
        if (SDL_GetTicks()-held>=1200) {
            fprintf(stderr,"hakuX TrimUI: exit requested\n"); _exit(0);
        }
    } else held=0;
}

static void pad_state(SDL_GameController *pad) {
    NcPadState s = {0};
    if (pad) {
#ifdef HAKUX_XBOX2
        uint8_t mapped[16];hakux_menu_map_buttons(pad,mapped);
        for(int i=0;i<8;i++)s.analog[i]=mapped[i];
        for(int i=0;i<8;i++)if(mapped[i+8]>127)s.buttons|=1u<<i;
#else
        const SDL_GameControllerButton analog[] = { SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_B,
            SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_Y, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER,
            SDL_CONTROLLER_BUTTON_LEFTSHOULDER };
        const SDL_GameControllerButton digital[] = { SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN,
            SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_BUTTON_DPAD_RIGHT, SDL_CONTROLLER_BUTTON_START,
            SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_LEFTSTICK, SDL_CONTROLLER_BUTTON_RIGHTSTICK };
        for (int i=0;i<6;i++) s.analog[i] = SDL_GameControllerGetButton(pad, analog[i]) ? 255 : 0;
        for (int i=0;i<8;i++) if (SDL_GameControllerGetButton(pad, digital[i])) s.buttons |= 1u << i;
        s.analog[6] = SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERLEFT) / 128;
        s.analog[7] = SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) / 128;
#endif
        s.lx = SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTX);
        s.ly = -SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTY);
        s.rx = SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_RIGHTX);
        s.ry = -SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_RIGHTY);

    }
    nc_pad_set(0, &s);
}

/* Poll independently of Vulkan waits: short presses must survive a slow frame. */
static void *input(void *unused) {
    pthread_setname_np(pthread_self(), "hakux-input");
    SDL_GameController *pad = NULL;
    for (;;) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
#ifdef HAKUX_XBOX2
            if ((e.type == SDL_KEYDOWN || e.type == SDL_KEYUP) && e.key.keysym.sym == SDLK_MENU)
                hakux_menu_key(e.type == SDL_KEYDOWN);
#endif
            if (e.type == SDL_CONTROLLERDEVICEADDED && !pad) {
                pad = SDL_GameControllerOpen(e.cdevice.which);
                fprintf(stderr,"hakuX TrimUI: controller=%s\n", pad ? SDL_GameControllerName(pad) : SDL_GetError());
            } else if (e.type == SDL_CONTROLLERDEVICEREMOVED && pad &&
                SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad)) == e.cdevice.which) {
                SDL_GameControllerClose(pad); pad = NULL;
            }
        }
        emergency_exit(pad);
#ifdef HAKUX_XBOX2
        if (hakux_menu_input(pad)) { NcPadState zero={0}; nc_pad_set(0,&zero); }
        else
#endif
        pad_state(pad);
        SDL_Delay(4);
    }
    return NULL;
}

static void *frontend(void *unused) {
    pthread_setname_np(pthread_self(), "hakux-display");
    struct ANativeWindow win = {1280,720};
    Uint32 last_log = SDL_GetTicks();
    for (;;) {
#ifdef HAKUX_XBOX2
        hakux_menu_video();
#endif
        if (!nc_present_frame(&win)) SDL_Delay(4);
        if (SDL_GetTicks()-last_log >= 10000) {
            float fps, avg, last; nc_present_stats(&fps,&avg,&last);
            fprintf(stderr,"hakuX TrimUI: %.2f FPS, %.1f ms/frame\n",fps,avg);
            last_log=SDL_GetTicks();
        }
    }
    return NULL;
}

void hakux_frontend_start(void) {
#ifdef HAKUX_XBOX2
    fprintf(stderr,"hakuX Xbox 2: experimental TrimUI renderer, build 2026-10-28\n");
#endif
    SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS,"1");
    Uint32 flags=SDL_INIT_AUDIO;
    if (!getenv("HAKUX_HEADLESS")) flags|=SDL_INIT_GAMECONTROLLER|SDL_INIT_EVENTS;
    if (SDL_Init(flags) < 0)
        fprintf(stderr,"hakuX TrimUI: SDL init: %s\n", SDL_GetError());
    if (getenv("HAKUX_HEADLESS")) return;
    nc_present_init();
    pthread_t t;
    if (pthread_create(&t,NULL,input,NULL)) {
        fprintf(stderr,"hakuX TrimUI: could not start input thread\n"); exit(1);
    }
    pthread_detach(t);
    if (pthread_create(&t,NULL,frontend,NULL)) {
        fprintf(stderr,"hakuX TrimUI: could not start display thread\n"); exit(1);
    }
    pthread_detach(t);
}
