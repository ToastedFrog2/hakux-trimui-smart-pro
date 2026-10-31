/* Host-only evdev definitions for exercising the real menu on macOS. */
#include <sys/time.h>
#include <stdint.h>
struct input_event { struct timeval time; uint16_t type,code; int32_t value; };
#define EV_KEY 1
#define BTN_MODE 316
#define KEY_MENU 139
