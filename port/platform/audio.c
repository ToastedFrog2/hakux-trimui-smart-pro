/* SDL2/ALSA output preserving the core's single-producer/single-consumer ring. */
#include "native/dev/apu/apu_int.h"
#include <SDL.h>
#include <time.h>
#include <stdlib.h>

static struct {
    uint8_t *buf;
    uint32_t cap;
    uint64_t head, tail;
    uint32_t callbacks, short_callbacks;
    pthread_cond_t *wake;
    SDL_AudioDeviceID device;
} out;

int apu_out_queued(void) { return (int)(apu_ld_acq(&out.head)-apu_ld_acq(&out.tail)); }
void apu_out_push(const void *frame, int bytes) {
    uint64_t h=out.head;
    assert(h+(uint64_t)bytes-apu_ld_acq(&out.tail)<=out.cap);
    uint32_t at=h%out.cap, first=MIN((uint32_t)bytes,out.cap-at);
    memcpy(out.buf+at,frame,first);
    memcpy(out.buf,(const uint8_t*)frame+first,(uint32_t)bytes-first);
    apu_st_rel(&out.head,h+(uint64_t)bytes);
}
static void fill(void *unused, Uint8 *data, int bytes) {
    if (nc_paused()) { memset(data,0,bytes); return; }
    uint64_t t=out.tail;
    int n=MIN((uint64_t)bytes,apu_ld_acq(&out.head)-t);
    uint32_t at=t%out.cap,first=MIN((uint32_t)n,out.cap-at);
    memcpy(data,out.buf+at,first); memcpy(data+first,out.buf,(uint32_t)n-first);
    apu_st_rel(&out.tail,t+(uint64_t)n);
    apu_inc(&out.callbacks);
    if(n<bytes){apu_inc(&out.short_callbacks);memset(data+n,0,bytes-n);}
    pthread_cond_broadcast(out.wake);
}
void apu_out_stats(uint32_t *callbacks,uint32_t *short_callbacks) {
    *callbacks=apu_xchg(&out.callbacks,0); *short_callbacks=apu_xchg(&out.short_callbacks,0);
}
static void *silent_clock(void *unused) {
    uint8_t data[1024];
    struct timespec now; clock_gettime(CLOCK_MONOTONIC,&now);
    for (;;) {
        fill(NULL,data,sizeof(data));
        now.tv_nsec+=5333333;
        if(now.tv_nsec>=1000000000){now.tv_nsec-=1000000000;now.tv_sec++;}
        clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&now,NULL);
    }
    return NULL;
}
int apu_out_open(int capacity_bytes,int samples,pthread_cond_t *wake) {
    out.buf=calloc(1,capacity_bytes);out.cap=capacity_bytes;out.wake=wake;
    SDL_AudioSpec wanted={0},got={0};
    wanted.freq=48000;wanted.format=AUDIO_S16SYS;wanted.channels=2;
    wanted.samples=samples;wanted.callback=fill;
    out.device=SDL_OpenAudioDevice(NULL,0,&wanted,&got,SDL_AUDIO_ALLOW_SAMPLES_CHANGE);
    if(out.device){
        nc_log("hakuX-apu","SDL2 audio: 48000 Hz stereo, %d samples",got.samples);
        SDL_PauseAudioDevice(out.device,0);return got.samples*4;
    }
    nc_log("hakuX-apu","audio unavailable: %s; silent clock",SDL_GetError());
    pthread_t t;pthread_create(&t,NULL,silent_clock,NULL);pthread_detach(t);
    return samples*4;
}
void nc_audio_set_paused(bool paused) { if(out.device)SDL_PauseAudioDevice(out.device,paused); }
