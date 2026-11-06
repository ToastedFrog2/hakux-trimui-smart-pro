#ifndef HAKUX_EXTRAS_H
#define HAKUX_EXTRAS_H
#include <stdbool.h>
#include <stddef.h>
#include "native/core/xdvdfs.h"
void hakux_extras_prepare(NcDisc *disc);
unsigned hakux_extras_rows(void);
void hakux_extras_line(unsigned row,char *out,size_t n);
bool hakux_extras_choose(unsigned row,char *status,size_t n);
bool hakux_extras_screenshot(void);
const char *hakux_extras_game_key(void);
#endif
