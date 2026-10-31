#ifndef HAKUX_TRIMUI_MENU_H
#define HAKUX_TRIMUI_MENU_H
#include <stdbool.h>
#include <stdint.h>
#ifdef HAKUX_XBOX2
#include <volk.h>
struct _SDL_GameController;
void hakux_menu_init(int argc, char **argv);
void hakux_menu_ready(void);
bool hakux_menu_input(struct _SDL_GameController *pad);
void hakux_menu_map_buttons(struct _SDL_GameController *pad, uint8_t values[16]);
void hakux_menu_key(bool down);
void hakux_menu_video(void);
uint64_t hakux_menu_key_revision(void);
unsigned hakux_menu_frame_skip(void);
void hakux_menu_ramp(uint8_t dst[3][256], const uint8_t src[3][256]);
void hakux_menu_draw(VkCommandBuffer cb, const struct VolkDeviceTable *t, uint32_t w, uint32_t h);
#endif
#endif
