/* Named temporary dispatcher objects. Names live in guest pool memory alongside
 * the body, so no host-only registry can survive an XBE reset or lose a snapshot.
 * The existing object allocator retains dispatcher bodies for scheduler users;
 * only objects with a live handle participate in this temporary namespace. */
#define OB_NAME_NOT_FOUND 0xC0000034u
#define OB_NAME_COLLISION 0xC0000035u
#define OB_NAME_INVALID 0xC0000033u
#define OB_NAME_EXISTS 0x40000000u

static bool ob_named_type(enum NcObType type)
{
    return type == NC_OB_EVENT || type == NC_OB_SEMAPHORE ||
           type == NC_OB_MUTANT || type == NC_OB_TIMER;
}

static bool ob_range(NcKernel *k, uint32_t va, uint32_t len)
{
    if (!va || !len || (uint64_t)va + len > UINT32_MAX) return false;
    uint32_t last = (va + len - 1) / NC_PAGE;
    for (uint32_t page = va / NC_PAGE; page <= last; page++)
        if (nc_vm_phys(k->vm, page * NC_PAGE) == UINT32_MAX) return false;
    return true;
}

static uint32_t ob_name(NcKernel *k, uint32_t attrs, char *name, uint32_t *flags)
{
    name[0] = 0;
    *flags = 0;
    if (!attrs) return NC_STATUS_SUCCESS;
    if (!ob_range(k, attrs, 12)) return NC_STATUS_INVALID_PARAMETER;
    /* XAPI CreateMutex/CreateSemaphore/CreateEvent use the Xbox kernel's
     * ObWin32NamedObjectsDirectory() pseudo-handle, not a real open handle.
     * Keep its names separate from the root namespace and make absolute
     * \Win32NamedObjects\ names refer to the same objects. Other directory
     * handles still need a full directory implementation. */
    uint32_t root = nc_vm_rd32(k->vm, attrs);
    if (root && root != 0xFFFFFFFCu) return 0xC000003Au;
    *flags = nc_vm_rd32(k->vm, attrs + 8);
    uint32_t str = nc_vm_rd32(k->vm, attrs + 4);
    if (!str) return NC_STATUS_SUCCESS;
    if (!ob_range(k, str, 8)) return NC_STATUS_INVALID_PARAMETER;
    uint32_t lengths = nc_vm_rd32(k->vm, str);
    unsigned len = lengths & 0xffff;
    if (!len || len > 1023 || len > (lengths >> 16)) return OB_NAME_INVALID;
    uint32_t data = nc_vm_rd32(k->vm, str + 4);
    if (!ob_range(k, data, len)) return NC_STATUS_INVALID_PARAMETER;
    memcpy(name, nc_vm_host(k->vm, data), len);
    if (memchr(name, 0, len)) return OB_NAME_INVALID;
    name[len] = 0;
    if (root == 0xFFFFFFFCu) {
        static const char prefix[] = "\\Win32NamedObjects\\";
        size_t n = sizeof(prefix) - 1;
        if (name[0] == '\\' || n + len >= 1024) return OB_NAME_INVALID;
        memmove(name + n, name, len + 1);
        memcpy(name, prefix, n);
    }
    return NC_STATUS_SUCCESS;
}

static uint32_t ob_find_name(NcKernel *k, const char *name, uint32_t flags,
                             enum NcObType *type)
{
    size_t len = strlen(name);
    for (unsigned i = 1; i < NC_MAX_HANDLES; i++) {
        NcHandle *h = &k->handle_table[i];
        if (!h->object || !ob_named_type(h->type)) continue;
        uint32_t p = nc_vm_rd32(k->vm, h->object - 4);
        if (!p || nc_vm_rd32(k->vm, p) != len) continue;
        const unsigned char *stored = nc_vm_host(k->vm, p + 4);
        size_t j;
        for (j = 0; j < len; j++) {
            unsigned a = (unsigned char)name[j], b = stored[j];
            if (flags & 0x40) {
                if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
                if (b >= 'A' && b <= 'Z') b += 'a' - 'A';
            }
            if (a != b) break;
        }
        if (j == len) { *type = h->type; return h->object; }
    }
    return 0;
}

uint32_t nc_ob_named_create(NcKernel *k, uint32_t attrs, enum NcObType type,
                             uint32_t size, uint32_t *object, bool *created)
{
    char name[1024]; uint32_t flags;
    *object = 0; *created = false;
    uint32_t status = ob_name(k, attrs, name, &flags);
    if (status) return status;
    if (name[0]) {
        enum NcObType found_type;
        uint32_t found = ob_find_name(k, name, flags, &found_type);
        if (found) {
            if (found_type != type) return NC_STATUS_OBJECT_TYPE_MISMATCH;
            if (!(flags & 0x80)) return OB_NAME_COLLISION;
            *object = found;
            return OB_NAME_EXISTS;
        }
    }
    uint32_t len = (uint32_t)strlen(name);
    *object = nc_ob_create(k, type, size + (len ? 4 + len + 1 : 0));
    if (!*object) return NC_STATUS_INSUFFICIENT_RESOURCES;
    nc_vm_wr32(k->vm, *object - 4, 0);
    if (len) {
        uint32_t p = *object + size;
        nc_vm_wr32(k->vm, p, len);
        memcpy(nc_vm_host(k->vm, p + 4), name, len + 1);
        nc_vm_wr32(k->vm, *object - 4, p);
    }
    *created = true;
    return NC_STATUS_SUCCESS;
}

static uint64_t ObOpenObjectByName(NcKernel *k, NcFrame *f, const uint32_t *a)
{
    (void)f;
    if (!ob_range(k, a[3], 4)) return NC_STATUS_INVALID_PARAMETER;
    char name[1024]; uint32_t flags;
    uint32_t status = ob_name(k, a[0], name, &flags);
    if (status) return status;
    if (!name[0]) return OB_NAME_INVALID;
    enum NcObType type;
    uint32_t object = ob_find_name(k, name, flags, &type);
    nc_log("hakuX-native-ob", "open %s type %08x: %s", name, a[1], object ? "found" : "not found");
    if (!object) return OB_NAME_NOT_FOUND;
    if (a[1] && a[1] != k->type_va[type]) return NC_STATUS_OBJECT_TYPE_MISMATCH;
    uint32_t handle = nc_ob_handle(k, object, type);
    if (!handle) return NC_STATUS_INSUFFICIENT_RESOURCES;
    nc_vm_wr32(k->vm, a[3], handle);
    return NC_STATUS_SUCCESS;
}
