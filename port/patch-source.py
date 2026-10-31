#!/usr/bin/env python3
"""Apply the Linux platform changes to a clean, pinned hakuX checkout."""
from pathlib import Path

root = Path(__file__).resolve().parent
src = root / 'source'
def replace(path, old, new):
    p = src / path
    text = p.read_text()
    if new in text: return
    # Later patches alter this injected block; recognize its stable marker
    # instead of adding a second unguarded Halo override on every rebuild.
    if path == 'native/core/xbe_load.c' and 'Halo 2: all campaign levels unlocked' in new and 'Halo 2: all campaign levels unlocked' in text:
        return
    if old not in text:
        raise SystemExit(f'Patch context missing: {path}: {old[:80]}')
    p.write_text(text.replace(old, new))

replace('native/CMakeLists.txt', 'project(hakux_native C CXX)', '''project(hakux_native C CXX)
set(PORT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." )
get_filename_component(PORT_ROOT "${PORT_ROOT}/.." ABSOLUTE)
add_compile_definitions(_GNU_SOURCE HAKUX_TRIMUI=1)
include_directories("${PORT_ROOT}/platform/include" "${PORT_ROOT}/deps/Vulkan-Headers/include"
                    "${PORT_ROOT}/deps/SDL2/include")
add_library(android INTERFACE)
add_library(log INTERFACE)
add_library(aaudio INTERFACE)
add_library(SDL2 SHARED IMPORTED)
set_target_properties(SDL2 PROPERTIES IMPORTED_LOCATION "${PORT_ROOT}/deps/lib/libSDL2.so")
add_subdirectory("${PORT_ROOT}/deps/zlib" zlib-build EXCLUDE_FROM_ALL)
add_library(z ALIAS zlibstatic)
include_directories("${PORT_ROOT}/deps/zlib" "${CMAKE_BINARY_DIR}/zlib-build")
''')
replace('native/CMakeLists.txt', 'add_executable(xboxrun run/xboxrun.c run/capture.c app/vkdriver.c app/vklayer.c)', '''add_executable(xboxrun run/xboxrun.c run/capture.c app/vkdriver.c
  app/present.c "${PORT_ROOT}/platform/frontend.c" "${PORT_ROOT}/platform/display.c")''')
replace('native/CMakeLists.txt', 'target_link_libraries(xboxrun PRIVATE hakux_native hakux_hle z log)',
        'target_link_libraries(xboxrun PRIVATE hakux_native hakux_hle z log SDL2 pthread dl m)')
replace('native/CMakeLists.txt', 'include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/app.cmake")',
        '# Linux frontend is linked directly into xboxrun.')
replace('native/cmake/hle.cmake', '${NC_APU}/out.c', '${PORT_ROOT}/platform/audio.c')
replace('native/cmake/hle.cmake', 'VK_NO_PROTOTYPES VK_USE_PLATFORM_ANDROID_KHR', 'VK_NO_PROTOTYPES')
replace('hw/xbox/hle/prop.h', '#ifdef __ANDROID__', '#if defined(__ANDROID__) || defined(HAKUX_TRIMUI)')
replace('hw/xbox/hle/vk/vkdev.c', 'VK_KHR_ANDROID_SURFACE_EXTENSION_NAME', 'VK_KHR_DISPLAY_EXTENSION_NAME')
replace('hw/xbox/hle/vk/guest_ram.c', 'static bool import(AHardwareBuffer *ahb, bool bda)\n{',
        'static bool import(AHardwareBuffer *ahb, bool bda)\n{\n#ifdef __ANDROID__')
replace('hw/xbox/hle/vk/guest_ram.c', '    return true;\n}\n\nint hle_vk_guest_ram_init',
        '    return true;\n#else\n    return false;\n#endif\n}\n\nint hle_vk_guest_ram_init')
replace('hw/xbox/hle/vk/swapchain.c', '#include <android/native_window.h>',
        '#include <android/native_window.h>\nVkResult hakux_display_surface(VkInstance, VkPhysicalDevice, VkSurfaceKHR *);')
replace('hw/xbox/hle/vk/swapchain.c', '''            VkAndroidSurfaceCreateInfoKHR sci = { .sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR,
                                                  .window = win };
            if (vkCreateAndroidSurfaceKHR(g_hvk.inst, &sci, NULL, &g_ps.surf) != VK_SUCCESS) {''',
        '''            if (hakux_display_surface(g_hvk.inst, g_hvk.phys, &g_ps.surf) != VK_SUCCESS) {''')
replace('native/run/xboxrun.c', 'static NcCore g_core;',
        'static NcCore g_core;\nvoid hakux_frontend_start(void);')
replace('native/run/xboxrun.c', '    nc_options_apply(&opt);',
        '    nc_options_apply(&opt);\n    hakux_frontend_start();')
replace('native/run/xboxrun.c', ': 30;\n    nc_log', ': 0;\n    nc_log')
replace('native/core/vm.c', '#include <stdlib.h>', '#include <stdlib.h>\n#include <stdio.h>')
replace('native/core/nc.h', '#include <stdarg.h>', '#include <stdarg.h>\n#include <stdio.h>')
replace('native/net/kai.c', '#include <stdlib.h>', '#include <stdlib.h>\n#include "linux_random.h"\n#define arc4random nc_linux_random')
replace('native/kernel/ex.c', '#include <stdlib.h>', '#include <stdlib.h>\n#include "linux_random.h"\n#define arc4random_buf nc_linux_random_buf')
replace('native/cpu/cpu.cpp', '#ifdef __ANDROID__', '#if defined(__ANDROID__) || defined(HAKUX_TRIMUI)')
replace('hw/xbox/hle/vk/vkdev.c', '''        .runtimeDescriptorArray = VK_TRUE, .descriptorBindingPartiallyBound = VK_TRUE,
        .descriptorBindingSampledImageUpdateAfterBind = VK_TRUE,
        .shaderSampledImageArrayNonUniformIndexing = VK_TRUE,
        .hostQueryReset = c->host_query_reset''', '''        .runtimeDescriptorArray = c->bindless, .descriptorBindingPartiallyBound = c->bindless,
        .descriptorBindingSampledImageUpdateAfterBind = c->bindless,
        .shaderSampledImageArrayNonUniformIndexing = c->bindless,
        .hostQueryReset = c->host_query_reset''')
replace('external/fex/Source/Common/HostFeatures.cpp', '#include "Common/CPUInfo.h"',
        '#include "Common/CPUInfo.h"\n#ifdef HAKUX_TRIMUI\n#include <sys/auxv.h>\n#include <asm/hwcap.h>\n#endif')
replace('external/fex/Source/Common/HostFeatures.cpp', '''  CPUFeaturesFromID() {
    ISAR0.SetReg''', '''  CPUFeaturesFromID() {
#ifdef HAKUX_TRIMUI
    /* The stock 4.9 kernel cannot emulate userspace CPU ID-register MRS.
     * Use Linux's advertised capabilities on this Cortex-A53 target. */
    const unsigned long hw = getauxval(AT_HWCAP);
    if (!(hw & HWCAP_CPUID)) {
      uint64_t isar = 0;
      if (hw & HWCAP_AES) isar |= 1ull << 4;
      if (hw & HWCAP_PMULL) isar = (isar & ~(15ull << 4)) | (2ull << 4);
      if (hw & HWCAP_SHA1) isar |= 1ull << 8;
      if (hw & HWCAP_SHA2) isar |= 1ull << 12;
      if (hw & HWCAP_CRC32) isar |= 1ull << 16;
      ISAR0.SetReg(isar);
      PFR0.SetReg(0x2222); /* A53: baseline FP/ASIMD, no FP16 or SVE. */
      MIDR.SetReg(0x410fd034); /* Smart Pro's Cortex-A53 r0p4. */
      DCZID.SetReg(Get_DCZID_EL0());
      FillFeatureFlags();
      return;
    }
#endif
    ISAR0.SetReg''')
replace('external/fex/Source/Common/HostFeatures.cpp',
        '  __asm volatile("mrs %[midr], midr_el1" : [midr] "=r"(MIDR));', '''#ifdef HAKUX_TRIMUI
  if (!(getauxval(AT_HWCAP) & HWCAP_CPUID)) MIDR = 0x410fd034;
  else
#endif
  __asm volatile("mrs %[midr], midr_el1" : [midr] "=r"(MIDR));''')
replace('native/kernel/kernel.c', '''    case NC_SYSOP_CPUID:
        cpuid(f);''', '''    case NC_SYSOP_RDMSR:
        /* nxdk startup reads the Xbox's CPU bus/multiplier straps.
         * MSR_IA32_EBL_CR_POWERON value matches xemu's Xbox CPU model. */
        if (nc_frame_gpr(f, NC_ECX) == 0x2a) {
            nc_frame_set_gpr(f, NC_EAX, 0xc5040000u);
            nc_frame_set_gpr(f, NC_EDX, 0);
            nc_frame_set_eip(f, eip + size);
        } else {
            nc_kernel_request_stop(k, f, "unsupported RDMSR %08x at %08x", nc_frame_gpr(f, NC_ECX), eip);
        }
        break;
    case NC_SYSOP_CPUID:
        cpuid(f);''')
replace('native/dev/nv2a.c', '    nc_wr32(g_regs + NV_PFB_CSTATUS, 64u << 20);', '''    nc_wr32(g_regs + NV_PFB_CSTATUS, 64u << 20);
    /* The HLE boot skips firmware: retain the post-boot PLL/RAM straps
     * that nxdk's pbkit checks before it initializes the GPU. */
    nc_wr32(g_regs + 0x680500, 0x00011c01); /* NVPLL: 233.333 MHz */
    nc_wr32(g_regs + 0x680508, 0x0003c20d); /* VPLL */
    nc_wr32(g_regs + 0x100200, 3);          /* PFB_CFG0: four RAM partitions */''')
replace('native/core/vm.c', '    nc_vm_claim_phys(vm, 0, 0x10000);', '''    nc_vm_claim_phys(vm, 0, 0x10000);
    /* Kernel-owned GPU instance RAM and its upper pad must be reserved
     * before titles start allocating contiguous buffers. */
    nc_vm_claim_phys(vm, ram_size - 0x20000, 0x20000);''')
replace('external/fex/External/rpmalloc/rpmalloc/rpmalloc.c', '''rpaligned_alloc(size_t alignment, size_t size) {
	heap_t* heap = get_thread_heap();
	return heap_allocate_block_aligned(heap, alignment, size, 0);
}''', '''rpaligned_alloc(size_t alignment, size_t size) {
	heap_t* heap = get_thread_heap();
	void* p = heap_allocate_block_aligned(heap, alignment, size, 0);
	if (!p) { fprintf(stderr, "hakuX: allocator failed: alignment=%zu size=%zu errno=%d\\n", alignment, size, errno); abort(); }
	return p;
}''')
replace('external/fex/External/rpmalloc/rpmalloc/rpmalloc.c',
        'int flags = MAP_PRIVATE | MAP_ANONYMOUS | MAP_UNINITIALIZED;',
        '''/* The allocator reserves 256 MiB aligned spans. On this low-RAM
     * Linux target commit pages on demand, as Android's overcommit does. */
	int flags = MAP_PRIVATE | MAP_ANONYMOUS | MAP_UNINITIALIZED | MAP_NORESERVE;''')
replace('hw/xbox/hle/pb/pbmode.h', 'bool hle_pb_active(void);',
        'bool hle_pb_active(void);\n/* Physical base of a bound DMA context (0 for the usual all-RAM context). */\nuint32_t hle_pb_dma_base(uint32_t handle);')
replace('hw/xbox/hle/pb/pbmode.c', '''static uint32_t ctx_base(uint32_t handle)
{
    uint32_t inst = handle ? ramht_find(handle) : 0;
    return inst ? dma_base(inst) : 0;
}''', '''static uint32_t ctx_base(uint32_t handle)
{
    uint32_t inst = handle ? ramht_find(handle) : 0;
    return inst ? dma_base(inst) : 0;
}

uint32_t hle_pb_dma_base(uint32_t handle)
{
    return ctx_base(handle);
}''')
replace('hw/xbox/hle/pb/pbdraw.c', '''    uint32_t cpa = R(NV097_SET_SURFACE_COLOR_OFFSET) & 0x0FFFFFFFu;
    uint32_t zpa = R(NV097_SET_SURFACE_ZETA_OFFSET) & 0x0FFFFFFFu;''', '''    /* nxdk uses surface-relative DMA contexts; XDK normally uses a
     * base-zero context. Both address the same physical Xbox RAM. */
    uint32_t cpa = (hle_pb_dma_base(R(0x0194u)) + R(NV097_SET_SURFACE_COLOR_OFFSET)) & 0x07FFFFFFu;
    uint32_t zpa = (hle_pb_dma_base(R(0x0198u)) + R(NV097_SET_SURFACE_ZETA_OFFSET)) & 0x07FFFFFFu;''')
replace('hw/xbox/hle/pb/pbdraw.c', '    [NV097_SET_SURFACE_CLIP_HORIZONTAL / 4 ... NV097_SET_SURFACE_ZETA_OFFSET / 4] = true,',
        '    [0x0194u / 4] = true,\n    [0x0198u / 4] = true,\n    [NV097_SET_SURFACE_CLIP_HORIZONTAL / 4 ... NV097_SET_SURFACE_ZETA_OFFSET / 4] = true,')
replace('hw/xbox/hle/pb/pbdraw.c', '''    switch (m) {
    case NV097_SET_SURFACE_CLIP_HORIZONTAL:''', '''    switch (m) {
    case 0x0194u: /* color DMA context; its instance can change in place */
    case 0x0198u: /* depth DMA context */
    case NV097_SET_SURFACE_CLIP_HORIZONTAL:''')

# The guest cancels USB transfers after waiting for a frame boundary. Publish
# that boundary only after all descriptor writes for the old frame are visible.
replace('native/dev/ohci.c', '''    o->frame_number = (uint16_t)(o->frame_number + 1);
    uint8_t *hcca = phys(o, o->hcca, 256);
    if (hcca) {
        nc_wr16(hcca + 0x80, o->frame_number);
        nc_wr16(hcca + 0x82, 0);
    }
    if (!(o->frame_number & 0x7fff)) {
        o->intr_status |= INT_FNO;
    }
    __atomic_thread_fence(__ATOMIC_ACQUIRE);''', '''    uint8_t *hcca = phys(o, o->hcca, 256);
    __atomic_thread_fence(__ATOMIC_ACQUIRE);''')
replace('native/dev/ohci.c', '''    /* The done queue goes out when its delay runs down and the last one was taken. */''', '''    /* Finish the old frame before exposing the new frame number. The USB
     * driver uses it to decide when skipped descriptors can be freed. */
    o->frame_number = (uint16_t)(o->frame_number + 1);
    if (hcca) {
        nc_wr16(hcca + 0x82, 0);
        __atomic_store_n((uint16_t *)(hcca + 0x80), o->frame_number, __ATOMIC_RELEASE);
    }
    if (!(o->frame_number & 0x7fff)) {
        o->intr_status |= INT_FNO;
    }

    /* The done queue goes out when its delay runs down and the last one was taken. */''')
replace('native/dev/ohci.c', '''        nc_wr32(hcca + 0x84, head);''',
        '''        __atomic_store_n((uint32_t *)(hcca + 0x84), head, __ATOMIC_RELEASE);''')
replace('native/dev/ohci.c', '''    wr_words(o, td_pa, td, 4);
    wr_words(o, ed_pa + 8, &ed[2], 1);''', '''    wr_words(o, td_pa, td, 4);
    __atomic_thread_fence(__ATOMIC_RELEASE);
    wr_words(o, ed_pa + 8, &ed[2], 1);''')
replace('native/dev/ohci.c', '''    if (!rd_words(o, td_pa, td, 4)) {
        ed[2] |= ED_H;''', '''    if (!rd_words(o, td_pa, td, 4)) {
        static unsigned bad_head;
        if (bad_head++ < 8) nc_log("hakuX-native-usb", "invalid TD: ED %08x flags %08x head %08x tail %08x frame %u",
                                  ed_pa, ed[0], ed[2], ed[1], o->frame_number);
        ed[2] |= ED_H;''')

# A desktop-sized command ring lets this small GPU fall seconds behind the
# title. Backpressure sooner while retaining all rendering commands.
replace('hw/xbox/hle/front/fe.c', '''    g_ring_mem = hle_memalign(64, HLE_RING_BYTES);
    return hle_ring_init(&g_ring, g_ring_mem, HLE_RING_BYTES);''', '''    uint32_t bytes = 1u << 20;
    const char *env = getenv("HAKUX_HLE_RING_MIB");
    unsigned mib = env ? (unsigned)atoi(env) : 1;
    if (mib >= 1 && mib <= 16 && !(mib & (mib - 1))) bytes = mib << 20;
    fprintf(stderr, "hakuX TrimUI: render command queue: %u MiB\\n", bytes >> 20);
    g_ring_mem = hle_memalign(64, bytes);
    return hle_ring_init(&g_ring, g_ring_mem, bytes);''')

# Copied vertices need offsets divisible by their stride to keep the binding
# stable between short strips. Arbitrary 256-byte alignment changes its residue
# for strides such as 36/48 bytes, preventing the existing strip batcher.
replace('hw/xbox/hle/pb/pbres.h',
        'uint32_t hle_draw_arena_alloc16(uint32_t len, uint8_t **ptr);',
        '''uint32_t hle_draw_arena_alloc16(uint32_t len, uint8_t **ptr);
uint32_t hle_draw_arena_vertex(uint32_t len, uint32_t stride, uint8_t **ptr);''')
replace('hw/xbox/hle/pb/pbres.c', '''uint32_t hle_draw_arena_alloc16(uint32_t len, uint8_t **ptr)
{
    return arena_alloc(len, 16, ptr);
}''', '''uint32_t hle_draw_arena_alloc16(uint32_t len, uint8_t **ptr)
{
    return arena_alloc(len, 16, ptr);
}

uint32_t hle_draw_arena_vertex(uint32_t len, uint32_t stride, uint8_t **ptr)
{
    static int enabled = -1;
    if (enabled < 0) {
        const char *e = getenv("HAKUX_HLE_VB_ALIGN");
        enabled = !e || atoi(e) != 0;
    }
    if (!enabled || !stride || stride > 4096) return arena_alloc(len, 256, ptr);
    uint32_t a = stride, b = 16;
    while (b) { uint32_t rem = a % b; a = b; b = rem; }
    return arena_alloc(len, stride / a * 16, ptr);
}''')
replace('hw/xbox/hle/pb/pbdraw.c',
        'uint32_t off = src ? arena(len, &dst) : HLE_ARENA_FULL;',
        '''g_phase = 1;
        uint32_t off = src ? hle_draw_arena_vertex(len, st, &dst) : HLE_ARENA_FULL;
        g_phase = 0;''')

# The PowerVR fallback reuses texture sets but hashes a large key on every
# draw. Consecutive identical keys can return the last set directly. Reset
# this shortcut whenever the command buffer's descriptor pools are reset.
replace('hw/xbox/hle/vk/draw.c',
        '        GHashTable *sets;               /* FixedKey -> VkDescriptorSet */',
        '''        GHashTable *sets;               /* FixedKey -> VkDescriptorSet */
        FixedKey last_key;
        VkDescriptorSet last_set;''')
replace('hw/xbox/hle/vk/draw.c', '''    VkDescriptorSet set = (VkDescriptorSet)g_hash_table_lookup(f->sets, k);
    if (set) {
        return set;
    }''', '''    if (f->last_set && !memcmp(&f->last_key, k, sizeof(*k))) return f->last_set;
    VkDescriptorSet set = (VkDescriptorSet)g_hash_table_lookup(f->sets, k);
    if (set) {
        f->last_key = *k;
        f->last_set = set;
        return set;
    }''')
replace('hw/xbox/hle/vk/draw.c', '''    g_dr.fx_sets++;
    return set;''', '''    g_dr.fx_sets++;
    f->last_key = *k;
    f->last_set = set;
    return set;''')
replace('hw/xbox/hle/vk/draw.c', '''        g_hash_table_remove_all(f->sets);''',
        '''        f->last_set = VK_NULL_HANDLE;
        g_hash_table_remove_all(f->sets);''')

# Each allocation consumes at least one Xbox page. Cover every page of the
# largest supported (128 MiB) guest instead of an arbitrary 4096 resources.
# Road Rage creates more than 4096 small graphics allocations during loading.
replace('native/kernel/mm.c', '#define MAX_CONTIG  4096',
        '#define MAX_CONTIG  ((128u << 20) / NC_PAGE)')
replace('native/kernel/mm.c', '''    if (nc_vm_free_bytes(k->vm) >= size) {
        pa = nc_vm_alloc_phys_top(k->vm, size, lo, hi, align, &moved);''',
        '''    if (g_ncontig < MAX_CONTIG && nc_vm_free_bytes(k->vm) >= size) {
        pa = nc_vm_alloc_phys_top(k->vm, size, lo, hi, align, &moved);''')

# Guest DMA descriptors are published by translated x86 code on another ARM
# core. A tail update can be observed while the old dummy TD's link still
# contains XAPI's 0xffffffff sentinel. Retrying leaves the request intact;
# retiring it would permanently poison ED.HeadP with 0xfffffff0.
replace('native/dev/ohci.c', '        w[i] = nc_rd32(p + 4 * i);',
        '        w[i] = __atomic_load_n((const uint32_t *)(p + 4 * i), __ATOMIC_ACQUIRE);')
replace('native/dev/ohci.c', '''    int pid;
    switch (ED_D(ed[0]))''', '''    uint32_t current[3];
    if (!rd_words(o, ed_pa, current, 3) || current[0] != ed[0] ||
        (current[0] & ED_K) || current[2] != ed[2] ||
        (current[2] & PTR_MASK) == (current[1] & PTR_MASK)) return false;
    const uint32_t next = td[2] & PTR_MASK;
    if (!phys(o, next, 16) || next == td_pa ||
        (!next && (current[1] & PTR_MASK)) || (td[0] >> TD_CC_SHIFT) < 14) {
        static unsigned deferred;
        unsigned n = ++deferred;
        if (n <= 8 || !(n & (n - 1))) nc_log("hakuX-native-usb",
            "defer unpublished TD #%u: ED %08x TD %08x [%08x %08x %08x %08x] frame %u",
            n, ed_pa, td_pa, td[0], td[1], td[2], td[3], o->frame_number);
        return false;
    }
    int pid;
    switch (ED_D(ed[0]))''')
replace('native/dev/ohci.c', '''    if (r == NC_USB_NAK) {
        return false;
    }
    o->tds++;''', '''    if (r == NC_USB_NAK) {
        return false;
    }
    /* A cancellation can skip/relink the endpoint while the device runs. */
    if (!rd_words(o, ed_pa, current, 3) || current[0] != ed[0] ||
        (current[0] & ED_K) || current[2] != ed[2]) return false;
    o->tds++;''')

# Optional tracing for thread-handle lifetime investigations.
replace('native/kernel/ob.c', '#include "native/kernel/kernel.h"',
        '#include "native/kernel/kernel.h"\n#include <stdlib.h>')
replace('native/kernel/ob.c', '''            return i * 4;''', '''            if (type == NC_OB_THREAD && getenv("NC_TRACE_THREADS"))
                nc_log("hakuX-thread-trace", "create handle %08x object %08x", i * 4, object);
            return i * 4;''')
replace('native/kernel/ob.c', '''    k->handle_table[i].object = 0;''', '''    if (type == NC_OB_THREAD && getenv("NC_TRACE_THREADS"))
        nc_log("hakuX-thread-trace", "close handle %08x object %08x by t%u", handle, object,
               k->current ? k->current->id : 0);
    k->handle_table[i].object = 0;''')
replace('native/kernel/ob.c', '''    return nc_ob_close(k, a[0]) ? NC_STATUS_SUCCESS : NC_STATUS_INVALID_HANDLE;''',
        '''    enum NcObType trace_type;
    if (getenv("NC_TRACE_THREADS") && nc_ob_lookup(k, a[0], &trace_type) && trace_type == NC_OB_THREAD)
        nc_log("hakuX-thread-trace", "NtClose %08x from %08x outer %08x", a[0], nc_vm_rd32(k->vm, nc_frame_gpr(f, NC_ESP)), nc_vm_rd32(k->vm, nc_frame_gpr(f, NC_ESP) + 8));
    return nc_ob_close(k, a[0]) ? NC_STATUS_SUCCESS : NC_STATUS_INVALID_HANDLE;''')
replace('native/kernel/ps.c', '#include <stdio.h>', '#include <stdio.h>\n#include <stdlib.h>')
replace('native/kernel/ps.c', '''    uint32_t prev = resume(k, t);
    if (a[1])''', '''    uint32_t prev = resume(k, t);
    if (getenv("NC_TRACE_THREADS")) {
        static unsigned count;
        if (count++ < 24 || prev) nc_log("hakuX-thread-trace", "resume handle %08x -> t%u suspend %u -> %u", a[0], t->id, prev, t->suspend);
    }
    if (a[1])''')

# Submit batching. A fence boundary waits at most HLE_PEND_NS (1 ms) or 16
# boundaries before it is submitted, and every submit ends the open render
# pass. When the render thread is the bottleneck (Terminator: Dawn of Fate,
# ~10k draws a frame) that is ~100 submits a second, each frame split into
# ~25 passes, each reloading and storing the 1280x480 target through tile
# memory (~3.5 ms of GPU each). A guest that blocks on a fence still gets an
# immediate submit (hle_back_urgent), and a ring that runs dry submits at once,
# so only a saturated render thread holds them: 33 ms / 4096 took Terminator
# from 6.6 to 14.7 fps. The live debug properties are read from
# the environment on TrimUI (prop.h); debug.hakux.pendmax sets the count.
replace('hw/xbox/hle/vk/back.c', '#define HLE_PEND_NS 1000000\n',
        '#ifdef HAKUX_TRIMUI\n#define HLE_PEND_NS 33000000\n#define HLE_PEND_MAX 4096\n#else\n'
        '#define HLE_PEND_NS 1000000\n#define HLE_PEND_MAX 16\n#endif\n')
replace('hw/xbox/hle/vk/back.c', 'static int64_t g_pend_ns = HLE_PEND_NS;',
        'static int64_t g_pend_ns = HLE_PEND_NS;\nstatic unsigned g_pend_max = HLE_PEND_MAX;')
replace('hw/xbox/hle/vk/back.c', 'if (++g_pend.n >= 16 || now - g_pend.since >= g_pend_ns ||',
        'if (++g_pend.n >= g_pend_max || now - g_pend.since >= g_pend_ns ||')
replace('hw/xbox/hle/vk/back.c', '''static void back_props_poll(uint64_t swap)
{
#ifdef __ANDROID__''', '''static void back_props_poll(uint64_t swap)
{
#if defined(__ANDROID__) || defined(HAKUX_TRIMUI)''')
replace('hw/xbox/hle/vk/back.c', '''        hle_log("hakuX-hle-back", "boundaries wait at most %lld us", (long long)(pend / 1000));
    }''', '''        hle_log("hakuX-hle-back", "boundaries wait at most %lld us", (long long)(pend / 1000));
    }
    v[0] = 0;
    hle_prop_get("debug.hakux.pendmax", v);
    unsigned pmax = atoi(v) > 0 ? (unsigned)atoi(v) : HLE_PEND_MAX;
    if (pmax != g_pend_max) {
        g_pend_max = pmax;
        hle_log("hakuX-hle-back", "at most %u boundaries a submit", pmax);
    }''')

# Zig's compiler_rt memset/memcmp/bcmp are byte loops (platform/fastmem.c).
replace('native/CMakeLists.txt', 'target_link_libraries(xboxrun PRIVATE hakux_native hakux_hle z log SDL2 pthread dl m)',
        'target_link_libraries(xboxrun PRIVATE hakux_native hakux_hle z log SDL2 pthread dl m)\n'
        'target_sources(xboxrun PRIVATE "${PORT_ROOT}/platform/fastmem.c")')

# A pending boundary's age is checked every 64 commands, not after each: with
# boundaries held for longer one is nearly always pending, and the kernel's
# clock read is a system call on this SoC (the A133's timer erratum turns the
# vDSO off), 11% of the render thread. Urgent ones still go at once.
replace('hw/xbox/hle/vk/back.c', '''static inline void pend_age_check(void)
{
    if (unlikely(g_pend.n) && (hle_now_ns() - g_pend.since >= g_pend_ns ||
                               hle_atomic_read(&g_pend.urgent))) {''', '''static inline void pend_age_check(void)
{
    static unsigned checks;
    if (unlikely(g_pend.n) && (hle_atomic_read(&g_pend.urgent) ||
                               (!(++checks & 63) && hle_now_ns() - g_pend.since >= g_pend_ns))) {''')

# The pipeline cache write serializes a merged copy; when the merge or the
# serialization fails (Unreal Championship: nothing written over a session of
# ~1600 new pipelines, so each start compiled them all again) it said nothing.
# Now it says why, and serializes the live cache instead.
replace('hw/xbox/hle/vk/pcache.c', '''    const bool merged = T.vkMergePipelineCaches(g_hvk.dev, copy, 1, &g_pc.cache) == VK_SUCCESS;
    const int64_t t1 = g_get_monotonic_time();
    size_t n = 0;
    void *buf = NULL;
    if (merged && T.vkGetPipelineCacheData(g_hvk.dev, copy, &n, NULL) == VK_SUCCESS && n) {
        buf = g_malloc(n);
        if (T.vkGetPipelineCacheData(g_hvk.dev, copy, &n, buf) != VK_SUCCESS) {
            g_free(buf);
            buf = NULL;
        }
    }''', '''    const VkResult mr = T.vkMergePipelineCaches(g_hvk.dev, copy, 1, &g_pc.cache);
    const int64_t t1 = g_get_monotonic_time();
    size_t n = 0;
    void *buf = NULL;
    /* the copy, else (the merge failed) the live cache */
    VkPipelineCache src = mr == VK_SUCCESS ? copy : g_pc.cache;
    VkResult gr = T.vkGetPipelineCacheData(g_hvk.dev, src, &n, NULL);
    if (gr == VK_SUCCESS && n) {
        buf = g_malloc(n);
        gr = T.vkGetPipelineCacheData(g_hvk.dev, src, &n, buf);
        if (gr != VK_SUCCESS) {
            g_free(buf);
            buf = NULL;
        }
    }
    if (mr != VK_SUCCESS || !buf) {
        hle_log("hakuX-hle-pipe", "pipeline cache write: merge %d, data %d (%zu bytes)%s", mr, gr, n,
                buf ? ": the live cache written" : ": nothing written");
    }''')

# Handles are reused as the Xbox kernel reuses them: the last one closed is
# the next one handed out (ObpCreateObjectHandle pops a free list that
# ObpDestroyObjectHandle pushes), fresh ones in ascending order after that.
# The lowest free one is not the same: Test Drive closes a file handle
# twice, and the second close then hit its loader thread's handle, which it
# could never resume (it hung after the loading movie). handle_table[0], never
# a handle, keeps the head of the list in .type; a free entry keeps the next.
replace('native/kernel/ob.c', '''uint32_t nc_ob_handle(NcKernel *k, uint32_t object, enum NcObType type)
{
    for (unsigned i = 1; i < NC_MAX_HANDLES; i++) {
        if (!k->handle_table[i].object) {''', '''uint32_t nc_ob_handle(NcKernel *k, uint32_t object, enum NcObType type)
{
    unsigned head = (unsigned)k->handle_table[0].type;
    if (head && head < NC_MAX_HANDLES && !k->handle_table[head].object) {
        k->handle_table[0].type = k->handle_table[head].type;
    } else {
        k->handle_table[0].type = 0;
        head = 0;
    }
    for (unsigned i = head ? head : 1; i < NC_MAX_HANDLES; i++) {
        if (!k->handle_table[i].object) {
            if (getenv("NC_TRACE_HANDLES"))
                nc_log("hakuX-handle-trace", "create %08x type %u object %08x by t%u", i * 4, type, object,
                       k->current ? k->current->id : 0);''')
replace('native/kernel/ob.c', '''    k->handle_table[i].object = 0;
    if (!count && (type == NC_OB_FILE''', '''    k->handle_table[i].object = 0;
    k->handle_table[i].type = k->handle_table[0].type;
    k->handle_table[0].type = (enum NcObType)i;
    if (getenv("NC_TRACE_HANDLES"))
        nc_log("hakuX-handle-trace", "close %08x type %u object %08x by t%u", handle, type, object,
               k->current ? k->current->id : 0);
    if (!count && (type == NC_OB_FILE''')

# A thread's ID is a handle of its own, as on the Xbox: PsCreateSystemThreadEx
# inserts the thread (UniqueThread, the ID) before it opens the handle it
# returns, and the ID handle goes when the thread ends. With one handle the
# numbering was off by one for everything after the first thread. Test Drive
# closes a file handle twice; on the Xbox the second close hits its loader
# thread's ID handle, harmless, but here it hit the thread's only handle,
# which the game then could never resume (it hung after the loading movie).
replace('native/kernel/ps.c', '''    uint32_t h = nc_ob_handle(k, t->ethread, NC_OB_THREAD);
    if (a[0]) {
        nc_vm_wr32(k->vm, a[0], h);
    }
    if (a[4]) {
        nc_vm_wr32(k->vm, a[4], t->id);
    }''', '''    const uint32_t id = nc_ob_handle(k, t->ethread, NC_OB_THREAD);
    if (id) {
        nc_vm_wr32(k->vm, t->ethread + ET_UNIQUE_THREAD, id);
    }
    uint32_t h = nc_ob_handle(k, t->ethread, NC_OB_THREAD);
    if (a[0]) {
        nc_vm_wr32(k->vm, a[0], h);
    }
    if (a[4]) {
        nc_vm_wr32(k->vm, a[4], id ? id : t->id);
    }''')
replace('native/kernel/ps.c', '''    t->state = NC_T_TERMINATED;
    nc_vm_wr32(k->vm, t->ethread + ET_EXIT_STATUS, status);''', '''    t->state = NC_T_TERMINATED;
    /* the ID handle (PsCreateSystemThreadEx), unless the title closed it */
    const uint32_t id = nc_vm_rd32(k->vm, t->ethread + ET_UNIQUE_THREAD);
    enum NcObType type;
    if (id != t->id && nc_ob_lookup(k, id, &type) == t->ethread && type == NC_OB_THREAD) {
        nc_ob_close(k, id);
    }
    nc_vm_wr32(k->vm, t->ethread + ET_EXIT_STATUS, status);''')

# The pipeline workers' priority, for A/B runs: debug.hakux.pipeprio = "idle"
# (SCHED_IDLE: only cores nothing else wants) or a nice value; else nice 10.
replace('hw/xbox/hle/vk/pipeasync.c', '''#ifdef __ANDROID__
#include <sys/system_properties.h>
#include "hw/xbox/hle/prop.h"
#endif
#ifdef __linux__
#include <sys/resource.h>''', '''#if defined(__ANDROID__) || defined(HAKUX_TRIMUI)
#include <sys/system_properties.h>
#include "hw/xbox/hle/prop.h"
#endif
#ifdef __linux__
#include <sched.h>
#include <sys/resource.h>''')
replace('hw/xbox/hle/vk/pipeasync.c', '''static void lower_priority(void)
{
#ifdef __linux__
    setpriority(PRIO_PROCESS, (id_t)syscall(SYS_gettid), 10);
#endif
}''', '''static void lower_priority(void)
{
#ifdef __linux__
    int nice = 10;
#ifdef HAKUX_TRIMUI
    char v[PROP_VALUE_MAX];
    hle_prop_get("debug.hakux.pipeprio", v);
    if (!strcmp(v, "idle")) {
        struct sched_param sp = { 0 };
        if (sched_setscheduler(0, SCHED_IDLE, &sp) == 0) {
            static bool said;
            if (!said) {
                said = true;
                hle_log("hakuX-hle-pipe", "pipeline workers: SCHED_IDLE");
            }
            return;
        }
    } else if (v[0]) {
        nice = atoi(v);
    }
#endif
    setpriority(PRIO_PROCESS, (id_t)syscall(SYS_gettid), nice);
#endif
}''')

# Render passes (debug.hakux.caps=-dynrender) build other pipelines than
# dynamic rendering: their driver cache is a file of its own, so switching
# doesn't load both sets (~85 MB each for Unreal Championship) into 1 GB.
replace('hw/xbox/hle/vk/pcache.c', '''        g_pc.blob = g_strdup_printf("%s/%08x.bin", pdir, g_hle.title.xbe.title_id);''',
        '''        g_pc.blob = g_strdup_printf("%s/%08x%s.bin", pdir, g_hle.title.xbe.title_id,
                                    g_hvk.caps.dyn_render ? "" : "-rp");''')

# TrimUI: render pass objects rather than dynamic rendering by default. The
# PowerVR driver rebuilds its load/store programs at every vkCmdBeginRendering
# (1.3-2.7 ms of CPU a pass; Halo 2's heavy scenes open ~10 passes a frame,
# and the render thread spent 60% of its time in that compile), where a
# VkRenderPass begin costs 0.005 ms (compat.c caches them). HAKUX_DYNRENDER=1
# keeps dynamic rendering; HAKUX_HLE_CAPS still adds its own switches.
replace('hw/xbox/hle/vk/vkdev.c', '''    if (!g_caps_v[0] && getenv("HAKUX_HLE_CAPS")) {
        snprintf(g_caps_v, sizeof(g_caps_v), "%s", getenv("HAKUX_HLE_CAPS"));
    }
}''', '''    if (!g_caps_v[0] && getenv("HAKUX_HLE_CAPS")) {
        snprintf(g_caps_v, sizeof(g_caps_v), "%s", getenv("HAKUX_HLE_CAPS"));
    }
#ifdef HAKUX_TRIMUI
    const char *dr = getenv("HAKUX_DYNRENDER");
    if (!(dr && dr[0] == '1') && !strstr(g_caps_v, "dynrender")) {
        size_t n = strlen(g_caps_v);
        snprintf(g_caps_v + n, sizeof(g_caps_v) - n, "%s-dynrender", n ? "," : "");
    }
#endif
}''')

# Title patches apply only to the matching title and original instruction bytes.
# Keep the complete table in one idempotent replacement; the ISO and saves
# remain untouched. HAKUX_NO_TITLE_PATCHES=1 disables the in-memory edits.
replace('native/core/xbe_load.c', '#include <stdlib.h>', '#include <stdlib.h>\n#include <string.h>')
replace('native/core/xbe_load.c', '    nc_log("hakuX-native-frontier",\n           "stage S0 xbe loaded: title %08x base %08x image', '    {\n        static const struct { uint32_t title, va; unsigned n; uint8_t from[16], to[16]; const char *what; } k_patches[] = {\n            { 0x4d530064u, 0x190565u, 6,\n              { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x0c }, { 0xb8, 0x68, 0x00, 0x00, 0x00, 0xc3 },\n              "Halo 2: all campaign levels unlocked" },\n            { 0x4d530064u, 0x19052cu, 13,\n              { 0x55, 0x8b, 0xec, 0x81, 0xec, 0xe4, 0x01, 0x00, 0x00, 0x53, 0x8d, 0x5d, 0xfc },\n              { 0xc7, 0x07, 0x68, 0x00, 0x00, 0x00, 0xc7, 0x06, 0x01, 0x00, 0x00, 0x00, 0xc3 },\n              "Halo 2: every profile has campaign progress" },\n        };\n        const char *off = getenv("HAKUX_NO_TITLE_PATCHES");\n        for (unsigned i = 0; i < sizeof(k_patches) / sizeof(k_patches[0]) && !(off && off[0] == \'1\'); i++) {\n            if (k_patches[i].title != x->title_id) {\n                continue;\n            }\n            uint8_t *p = nc_vm_host(vm, k_patches[i].va);\n            if (p && !memcmp(p, k_patches[i].from, k_patches[i].n)) {\n                memcpy(p, k_patches[i].to, k_patches[i].n);\n                nc_log("hakuX-native-frontier", "title patch: %s (%08x)", k_patches[i].what, k_patches[i].va);\n            } else {\n                nc_log("hakuX-native-frontier", "title patch: %s: the bytes at %08x differ, not applied",\n                       k_patches[i].what, k_patches[i].va);\n            }\n        }\n    }\n    nc_log("hakuX-native-frontier",\n           "stage S0 xbe loaded: title %08x base %08x image')
