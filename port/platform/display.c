/* Direct display: no desktop, compositor, or Android window required. */
#include <volk.h>
#include <stdio.h>
#include <stdlib.h>

VkResult hakux_display_surface(VkInstance instance, VkPhysicalDevice physical, VkSurfaceKHR *out) {
    uint32_t nd = 0, np = 0;
    VkResult r = vkGetPhysicalDeviceDisplayPropertiesKHR(physical, &nd, NULL);
    if (r || !nd) return r ? r : VK_ERROR_INITIALIZATION_FAILED;
    VkDisplayPropertiesKHR *ds = calloc(nd, sizeof(*ds));
    if (!ds) return VK_ERROR_OUT_OF_HOST_MEMORY;
    vkGetPhysicalDeviceDisplayPropertiesKHR(physical, &nd, ds);
    vkGetPhysicalDeviceDisplayPlanePropertiesKHR(physical, &np, NULL);
    VkDisplayPlanePropertiesKHR *planes = calloc(np, sizeof(*planes));
    if (!planes) { free(ds); return VK_ERROR_OUT_OF_HOST_MEMORY; }
    vkGetPhysicalDeviceDisplayPlanePropertiesKHR(physical, &np, planes);
    r = VK_ERROR_INITIALIZATION_FAILED;
    for (uint32_t d = 0; d < nd && r != VK_SUCCESS; d++) {
        uint32_t nm = 0;
        vkGetDisplayModePropertiesKHR(physical, ds[d].display, &nm, NULL);
        VkDisplayModePropertiesKHR *ms = calloc(nm, sizeof(*ms));
        if (!ms) continue;
        vkGetDisplayModePropertiesKHR(physical, ds[d].display, &nm, ms);
        for (uint32_t p = 0; p < np && r != VK_SUCCESS; p++) {
            uint32_t ns = 0;
            vkGetDisplayPlaneSupportedDisplaysKHR(physical, p, &ns, NULL);
            VkDisplayKHR *supported = calloc(ns, sizeof(*supported));
            if (!supported) continue;
            vkGetDisplayPlaneSupportedDisplaysKHR(physical, p, &ns, supported);
            int ok = 0;
            for (uint32_t i = 0; i < ns; i++) if (supported[i] == ds[d].display) ok = 1;
            free(supported);
            if (!ok) continue;
            for (uint32_t m = 0; m < nm && r != VK_SUCCESS; m++) {
                if (ms[m].parameters.visibleRegion.width != 1280 || ms[m].parameters.visibleRegion.height != 720) continue;
                VkDisplayPlaneCapabilitiesKHR caps;
                if (vkGetDisplayPlaneCapabilitiesKHR(physical, ms[m].displayMode, p, &caps)) continue;
                VkDisplayPlaneAlphaFlagBitsKHR alpha = VK_DISPLAY_PLANE_ALPHA_OPAQUE_BIT_KHR;
                if (!(caps.supportedAlpha & alpha)) continue;
                VkDisplaySurfaceCreateInfoKHR ci = {
                    .sType = VK_STRUCTURE_TYPE_DISPLAY_SURFACE_CREATE_INFO_KHR,
                    .displayMode = ms[m].displayMode, .planeIndex = p,
                    .planeStackIndex = planes[p].currentStackIndex,
                    .transform = VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
                    .globalAlpha = 1.0f, .alphaMode = alpha,
                    .imageExtent = ms[m].parameters.visibleRegion
                };
                r = vkCreateDisplayPlaneSurfaceKHR(instance, &ci, NULL, out);
            }
        }
        free(ms);
    }
    free(planes); free(ds);
    fprintf(stderr, "hakuX TrimUI: direct display surface result=%d\n", r);
    return r;
}
