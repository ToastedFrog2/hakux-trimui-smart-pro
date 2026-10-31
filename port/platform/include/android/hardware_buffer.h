#ifndef HAKUX_LINUX_AHB_H
#define HAKUX_LINUX_AHB_H
/* Android memory import is never selected on Linux; the core's existing
 * memfd and Vulkan staging-buffer paths provide guest RAM instead. */
typedef struct AHardwareBuffer AHardwareBuffer;
#endif
