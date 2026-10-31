#ifndef HAKUX_LINUX_WINDOW_H
#define HAKUX_LINUX_WINDOW_H
struct ANativeWindow { int width, height; };
static inline int ANativeWindow_getWidth(struct ANativeWindow *w) { return w->width; }
static inline int ANativeWindow_getHeight(struct ANativeWindow *w) { return w->height; }
#endif
