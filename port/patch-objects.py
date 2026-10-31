#!/usr/bin/env python3
"""Implement Xbox 2 temporary named dispatcher objects and typed opens."""
from pathlib import Path
root=Path(__file__).resolve().parent
def edit(file, old, new):
    p=root/'source/native/kernel'/file
    s=p.read_text()
    if new in s: return
    assert old in s, (file, old)
    p.write_text(s.replace(old,new,1))
edit('ob.c','void nc_ob_register(NcKernel *k)', '#ifdef HAKUX_XBOX2\n#include "hakux/named_objects.inc"\n#endif\n\nvoid nc_ob_register(NcKernel *k)')
edit('ob.c','    nc_kernel_impl(k, "NtClose", NtClose);', '#ifdef HAKUX_XBOX2\n    nc_kernel_impl(k, "ObOpenObjectByName", ObOpenObjectByName);\n#endif\n    nc_kernel_impl(k, "NtClose", NtClose);')
edit('kernel.h','void nc_ob_register(NcKernel *k);', 'void nc_ob_register(NcKernel *k);\n#ifdef HAKUX_XBOX2\nuint32_t nc_ob_named_create(NcKernel *k, uint32_t attrs, enum NcObType type,\n                             uint32_t size, uint32_t *object, bool *created);\n#endif')
for file,kind,var,size,init in [
 ('ke.c','EVENT','ev','0x10','    init_header(k, ev, (uint8_t)a[2], 4, (int32_t)(a[3] & 0xff));'),
 ('ke.c','SEMAPHORE','sem','0x14','    init_header(k, sem, OBJ_SEMAPHORE, 5, (int32_t)a[2]);\n    nc_vm_wr32(k->vm, sem + SEMAPHORE_LIMIT, a[3]);'),
 ('ke.c','MUTANT','m','0x20','    init_mutant(k, m, a[2] & 0xff);'),
 ('timer.c','TIMER','timer','KTIMER_SIZE','    timer_init(k, timer, a[2]);')]:
    old=f'    uint32_t {var} = nc_ob_create(k, NC_OB_{kind}, {size});'
    new=f'''#ifdef HAKUX_XBOX2
    uint32_t {var}; bool created;
    uint32_t status = nc_ob_named_create(k, a[1], NC_OB_{kind}, {size}, &{var}, &created);
    if (status & 0x80000000u) return status;
#else
{old}
#endif'''
    edit(file,old,new)
    edit(file,init, '#ifdef HAKUX_XBOX2\n    if (created) {\n'+init+'\n    }\n#else\n'+init+'\n#endif')
    old=f'    nc_vm_wr32(k->vm, a[0], nc_ob_handle(k, {var}, NC_OB_{kind}));\n    return NC_STATUS_SUCCESS;'
    new=f'''    uint32_t handle = nc_ob_handle(k, {var}, NC_OB_{kind});
    if (!handle) return NC_STATUS_INSUFFICIENT_RESOURCES;
    nc_vm_wr32(k->vm, a[0], handle);
#ifdef HAKUX_XBOX2
    return status;
#else
    return NC_STATUS_SUCCESS;
#endif'''
    edit(file,old,new)
