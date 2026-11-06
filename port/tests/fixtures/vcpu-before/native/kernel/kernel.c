/* Regression fixture: previous implementation, retained to demonstrate the failure. */
bool nc_kernel_sysop(void *opaque, NcFrame *f, enum NcSysOp op, unsigned size)
{
    g_nc_in_sysop = 1;
    if (op == NC_SYSOP_HOOK && g_slow_sysops <= 0) {
        NcKernel *k = opaque;
        const uint32_t eip = nc_frame_eip(f);
        if (nc_x86mmio_hook(k, f, eip)) {
            g_sysop_kind[(unsigned)op & 31]++;
            if (((++g_sysops) & 0xFFF) == 0) {
                nc_ke_time_enter();
                stats_tick(k);
                nc_ke_time_leave();
            }
            if (!nc_irq_lines() && !k->resched && !k->stop) {
                g_nc_in_sysop = 0;
                return true;
            }
            nc_ke_time_enter();
            const bool running = k->current && k->current->state == NC_T_RUNNING;
            if (!k->stop) {
                nc_intr_dispatch(k, !running || nc_frame_if(f));
            }
            const uint8_t irql = *pcr_irql(k);
            if (k->resched && !k->stop && (k->force_switch || !(running && irql >= 2))) {
                nc_ps_schedule(k, f);
            }
            if (k->stop) {
                nc_frame_set_eip(f, k->stop_va);
            }
            nc_ke_time_leave();
            g_nc_in_sysop = 0;
            return true;
        }
    }
    nc_kernel_pause_point(opaque, f, false);
    nc_ke_time_enter();
    if (g_slow_sysops < 0) {
        const char *e = getenv("NC_IRQ_SCHED");
        g_slow_sysops = e && atoi(e) != 0;
    }
    uint64_t t0 = 0, idles = 0, ints = 0;
    uint32_t eip = 0;
    uint16_t ordinal = 0;
    if (g_slow_sysops) {
        NcKernel *k = opaque;
        t0 = slow_now_ns();
        idles = g_nc_sched.idles;
        ints = k->interrupts;
        eip = nc_frame_eip(f);
        const uint8_t *insn = nc_vm_host(k->vm, eip);
        if (op == NC_SYSOP_INT && insn && insn[1] == NC_KCALL_VECTOR) {
            ordinal = nc_rd16(insn + 2);
        }
    }
    const bool r = sysop(opaque, f, op, size);
    if (t0) {
        NcKernel *k = opaque;
        slow_sysop(k, op, eip, ordinal, slow_now_ns() - t0, g_nc_sched.idles - idles,
                   k->interrupts - ints);
    }
    nc_ke_time_leave();
    g_nc_in_sysop = 0;
    return r;
}
