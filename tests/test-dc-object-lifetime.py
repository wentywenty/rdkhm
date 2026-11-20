#!/usr/bin/env python3
"""Exercise real DC destructors across deferred cleanup and rebinding."""
from pathlib import Path
import resource
import subprocess
import sys
import tempfile

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace / "scripts"))
from workspace import environment

kernel = Path(environment(workspace)["RDKHM_KERNEL_TREE"])
source = Path(sys.argv[1]) if len(sys.argv) > 1 else kernel / "drivers/gpu/drm/verisilicon/dc/dc_proc/dc_proc.c"
text = source.read_text()
functions = []
for kind in ("plane", "crtc", "wb"):
    start = text.index(f"void dc_{kind}_destroy(")
    end = text.index("\n}", start) + 2
    functions.append(text[start:end])

fixture = r'''
#include <assert.h>
#include <stdlib.h>
#include <linux/list.h>
#define NUM_MODIFIERS 2
static const unsigned long format_modifiers[] = {0, 1};
struct plane_info { const unsigned long *modifiers; unsigned num_modifiers; };
struct vs_plane { struct plane_info *info; };
struct vs_crtc { int unused; };
struct vs_wb { int unused; };
#define DECLARE_OBJECT(kind) \
    struct dc_##kind { struct list_head list, head; struct vs_##kind vs; }; \
    static struct dc_##kind *to_dc_##kind(struct vs_##kind *vs) \
    { return container_of(vs, struct dc_##kind, vs); }
DECLARE_OBJECT(plane)
DECLARE_OBJECT(crtc)
DECLARE_OBJECT(wb)
#define kfree(ptr) free((void *)(ptr))
static void __dc_proc_destroy(struct list_head *head) { assert(list_empty(head)); }
'''
cases = r'''
#define CHECK_OBJECT(kind) do { \
    LIST_HEAD(owner); \
    for (unsigned cycle = 0; cycle < 3; ++cycle) { \
        struct dc_##kind *a = calloc(1, sizeof(*a)); \
        struct dc_##kind *b = calloc(1, sizeof(*b)); \
        assert(a && b); \
        INIT_LIST_HEAD(&a->list); INIT_LIST_HEAD(&b->list); \
        INIT_LIST_HEAD(&a->head); INIT_LIST_HEAD(&b->head); \
        list_add_tail(&a->head, &owner); list_add_tail(&b->head, &owner); \
        dc_##kind##_destroy(&a->vs); \
        assert(owner.next == &b->head && b->head.prev == &owner); \
        dc_##kind##_destroy(&b->vs); \
        assert(list_empty(&owner) && owner.prev == &owner); \
    } \
    struct dc_##kind *unlinked = calloc(1, sizeof(*unlinked)); \
    assert(unlinked); \
    INIT_LIST_HEAD(&unlinked->list); INIT_LIST_HEAD(&unlinked->head); \
    dc_##kind##_destroy(&unlinked->vs); \
} while (0)
int main(void) {
    CHECK_OBJECT(plane);
    CHECK_OBJECT(crtc);
    CHECK_OBJECT(wb);
    return 0;
}
'''
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
with tempfile.TemporaryDirectory(prefix="rdkhm-dc-lifetime-") as directory:
    path = Path(directory)
    (path / "test.c").write_text(fixture + "\n".join(functions) + cases)
    subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(kernel / "tools/include"), str(path / "test.c"),
                    "-o", str(path / "test")], check=True)
    subprocess.run([str(path / "test")], check=True)
print("PASS: real plane/CRTC/writeback destructors, 3 bind-cleanup cycles and unlinked cleanup")
