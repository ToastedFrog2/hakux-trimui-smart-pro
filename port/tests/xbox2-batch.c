#define HAKUX_XBOX2 1
#include "hw/xbox/hle/vk/batch.c"

HleVk g_hvk;
void hle_log(const char *tag, const char *fmt, ...) {}
void hle_draw_ibuf_lost(void) {}
int hle_vk_memtype(uint32_t bits, VkMemoryPropertyFlags want, VkMemoryPropertyFlags avoid) { return -1; }

typedef struct Recorded { char op; uint32_t count, first; int32_t base; } Recorded;
static Recorded events[32768];
static unsigned nevents;
static VkCommandBuffer cb = (VkCommandBuffer)(uintptr_t)1;
static void VKAPI_CALL record_index(VkCommandBuffer b, uint32_t n, uint32_t instances,
                                   uint32_t first, int32_t base, uint32_t fi)
{
    assert(b == cb && instances == 1 && fi == 0);
    events[nevents++] = (Recorded){'i', n, first, base};
}
static void VKAPI_CALL record_draw(VkCommandBuffer b, uint32_t n, uint32_t instances,
                                  uint32_t first, uint32_t fi)
{
    assert(b == cb && instances == 1 && fi == 0);
    events[nevents++] = (Recorded){'v', n, first, 0};
}
static void VKAPI_CALL record_pipeline(VkCommandBuffer b, VkPipelineBindPoint bp, VkPipeline p)
{ events[nevents++] = (Recorded){'s'}; }
static void VKAPI_CALL record_query(VkCommandBuffer b, VkQueryPool p, uint32_t q, VkQueryControlFlags f)
{ events[nevents++] = (Recorded){'q'}; }
static void VKAPI_CALL record_end_query(VkCommandBuffer b, VkQueryPool p, uint32_t q)
{ events[nevents++] = (Recorded){'e'}; }
static void VKAPI_CALL record_barrier(VkCommandBuffer b, const VkDependencyInfo *d)
{ events[nevents++] = (Recorded){'b'}; }
static void VKAPI_CALL record_end(VkCommandBuffer b)
{ events[nevents++] = (Recorded){'f'}; }

static void submit(VkPrimitiveTopology p, uint32_t n, uint32_t first, int32_t base)
{
    hle_batch_prepare_indexed(cb);
    if (!hle_batch_draw_indexed(cb, p, n, first, base))
        g_hvk.t.vkCmdDrawIndexed(cb, n, 1, first, base, 0);
}
static void reset(void)
{
    hle_batch_flush(cb);
    nevents = 0;
    memset(&g_b, 0, sizeof(g_b));
    memset(&g_xbox2_index, 0, sizeof(g_xbox2_index));
    g_xbox2_index.enabled = true;
}

int main(void)
{
    g_hvk.t.vkCmdDrawIndexed = record_index;
    g_hvk.t.vkCmdDraw = record_draw;
    g_hvk.t.vkCmdBindPipeline = record_pipeline;
    g_hvk.t.vkCmdBeginQuery = record_query;
    g_hvk.t.vkCmdEndQuery = record_end_query;
    g_hvk.t.vkCmdPipelineBarrier2 = record_barrier;
    g_hvk.t.vkCmdEndRendering = record_end;
    hle_batch_install(&g_hvk.t);
    reset();
    for (unsigned i = 0; i < 1000; i++) submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, i*3, 7);
    assert(nevents == 0);
    g_hvk.t.vkCmdEndRendering(cb);
    assert(nevents == 2 && events[0].op == 'i' && events[0].count == 3000 &&
           events[0].first == 0 && events[0].base == 7 && events[1].op == 'f');
    assert(g_b.batches == 1 && g_b.merged == 1000);
    puts("PASS indexed batching: 1000 compatible draws -> 1, same indices and vertex base");

    reset();
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 0, 0);
    g_hvk.t.vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, VK_NULL_HANDLE);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 3, 0);
    g_hvk.t.vkCmdBeginQuery(cb, VK_NULL_HANDLE, 0, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 6, 0);
    g_hvk.t.vkCmdEndQuery(cb, VK_NULL_HANDLE, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 9, 0);
    g_hvk.t.vkCmdPipelineBarrier2(cb, NULL);
    assert(nevents == 8);
    assert(!memcmp((char[]){events[0].op, events[1].op, events[2].op, events[3].op,
                           events[4].op, events[5].op, events[6].op, events[7].op}, "isiqieib", 8));

    reset();
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 4, 0, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 2, 4, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP, 3, 6, 0);
    hle_batch_flush(cb);
    assert(nevents == 3 && events[0].count == 4 && events[1].count == 2);

    reset();
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 0, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 4, 0); /* gap */
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 7, -5); /* base change */
    submit(VK_PRIMITIVE_TOPOLOGY_LINE_LIST, 2, 10, -5); /* topology change */
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, UINT32_MAX-1, -5); /* overflow */
    hle_batch_flush(cb);
    assert(nevents == 5 && events[0].first == 0 && events[1].first == 4 && events[2].base == -5);

    reset();
    g_xbox2_index.enabled = false;
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 0, 0);
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 3, 0);
    assert(nevents == 2);

    reset();
    /* A held plain strip must precede the indexed list. */
    g_b.on = true;
    assert(hle_batch_draw(cb, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP, 5, 3));
    submit(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 3, 0, 0);
    assert(hle_batch_draw(cb, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP, 8, 3));
    hle_batch_flush(cb);
    assert(nevents == 3 && events[0].op == 'v' && events[0].first == 5 &&
           events[1].op == 'i' && events[2].op == 'v' && events[2].first == 8);
    puts("PASS indexed batching: state/query/barrier ordering, gaps, bases, topology, leftovers, overflow, strip interoperation and off switch");
    return 0;
}
