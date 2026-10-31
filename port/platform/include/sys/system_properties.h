#ifndef HAKUX_LINUX_PROPERTIES_H
#define HAKUX_LINUX_PROPERTIES_H
#include <stdlib.h>
#include <string.h>
#define PROP_VALUE_MAX 92
static inline int __system_property_get(const char *name, char *value) {
    const char *s = getenv(name);
    if (!s) { value[0] = 0; return 0; }
    size_t n = strlen(s); if (n >= PROP_VALUE_MAX) n = PROP_VALUE_MAX - 1;
    memcpy(value, s, n); value[n] = 0; return (int)n;
}
#endif
