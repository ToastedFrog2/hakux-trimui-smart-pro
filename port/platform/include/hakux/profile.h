#ifndef HAKUX_PROFILE_H
#define HAKUX_PROFILE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include "native/core/xdvdfs.h"
bool hakux_disc_game_key(const NcDisc *disc, char *key, size_t size);
void hakux_profile_bootstrap(int disc_fd);
void hakux_profile_network(void);
const char *hakux_profile_key(void);
bool hakux_profile_path(const char *name, char *path, size_t size);
FILE *hakux_profile_open(const char *name);
#endif
