#ifndef HAKUX_CAPTURE_H
#define HAKUX_CAPTURE_H
#include <stdbool.h>
/* Preserve framebuffer RGB while discarding its unused alpha and PNG metadata. */
bool hakux_png_opaque(const char *path);
#endif
