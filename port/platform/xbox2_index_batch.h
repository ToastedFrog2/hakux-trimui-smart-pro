/* Contiguous indexed lists can share one Vulkan draw. All intervening Vulkan
 * commands flush the held draw through batch_before(), including queries and
 * barriers. No index data is copied and no draws are reordered.
 */
#ifndef HAKUX_XBOX2_INDEX_BATCH_H
#define HAKUX_XBOX2_INDEX_BATCH_H
typedef struct HakuxIndexBatch {
    VkCommandBuffer cb;
    VkPrimitiveTopology prim;
    uint32_t count, first;
    int32_t base;
    uint32_t draws;
    bool enabled;
} HakuxIndexBatch;
static HakuxIndexBatch g_xbox2_index;

static void xbox2_index_flush(void)
{
    if (!g_xbox2_index.cb) return;
    R.vkCmdDrawIndexed(g_xbox2_index.cb, g_xbox2_index.count, 1,
                      g_xbox2_index.first, g_xbox2_index.base, 0);
    if (g_xbox2_index.draws > 1) {
        g_b.batches++;
        g_b.merged += g_xbox2_index.draws;
    }
    g_xbox2_index.cb = VK_NULL_HANDLE;
}

/* Called before the draw path checks its index-buffer binding: a held strip
 * can replace that binding as it flushes. An indexed list uses that binding.
 */
void hle_batch_prepare_indexed(VkCommandBuffer cb)
{
    if (g_b.cb == cb && cb) flush();
}

bool hle_batch_draw_indexed(VkCommandBuffer cb, VkPrimitiveTopology prim,
                          uint32_t count, uint32_t first, int32_t base)
{
    unsigned width = prim == VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST ? 3 :
                     prim == VK_PRIMITIVE_TOPOLOGY_LINE_LIST ? 2 :
                     prim == VK_PRIMITIVE_TOPOLOGY_POINT_LIST ? 1 : 0;
    /* Incomplete primitives must remain separate. Joining two leftovers
     * could otherwise manufacture triangles that neither draw contained.
     */
    if (!g_xbox2_index.enabled || !cb || !width || !count || count % width ||
        first > UINT32_MAX - count) return false;
    if (g_xbox2_index.cb == cb && g_xbox2_index.prim == prim &&
        g_xbox2_index.base == base &&
        g_xbox2_index.first + g_xbox2_index.count == first) {
        g_xbox2_index.count += count;
        g_xbox2_index.draws++;
        return true;
    }
    xbox2_index_flush();
    hle_batch_prepare_indexed(cb);
    g_xbox2_index.cb = cb;
    g_xbox2_index.prim = prim;
    g_xbox2_index.count = count;
    g_xbox2_index.first = first;
    g_xbox2_index.base = base;
    g_xbox2_index.draws = 1;
    return true;
}
#endif
