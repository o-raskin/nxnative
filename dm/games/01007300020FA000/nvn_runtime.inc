// Aspect/UI algorithm adapted from captainj-sparrow/astral-chain-pc-recomp.
/*
MIT License

Copyright (c) 2026 Valiantsin Dzerakh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

#include <math.h>
typedef struct { uint64_t x[31], nzcv; __uint128_t v[32]; } AcContext;
_Static_assert(sizeof(AcContext) == 0x300, "Astral aspect register ABI");
static uintptr_t ac_main(void) {
    for (int i = 0; i < g_nmod; i++) if (!strcmp(g_mod[i].name, "main")) return (uintptr_t)g_mod[i].base;
    return 0;
}
#define WIDE_16X9 (16.0f / 9.0f)
static float ac_ratio(void) { return dm_movie_playing() ? WIDE_16X9 : 1.6f; }
static int ac_lens(const uint8_t *lens) {
    int32_t w, h; memcpy(&w, lens + 0x268, 4); memcpy(&h, lens + 0x26c, 4);
    return w > 0 && (int64_t)w * 9 == (int64_t)h * 16;
}
static float ac_scalar(AcContext *c, unsigned n) { float f; memcpy(&f, &c->v[n], 4); return f; }
static void ac_scalar_set(AcContext *c, unsigned n, float f) { c->v[n] = 0; memcpy(&c->v[n], &f, 4); }
static void ac_tall(AcContext *c, const uint8_t *lens) {
    float r; memcpy(&r, lens + 0x278, 4);
    if (ac_lens(lens) && r > 0 && r < WIDE_16X9 / 1.001f)
        ac_scalar_set(c, 0, 2 * atanf(tanf(ac_scalar(c, 0) * 0.5f) * WIDE_16X9 / r));
}
#define PART_OWNER 0x08
#define PART_PLACE 0x1d8
#define PART_SCALE 0x1f0
#define PART_SCALE2 0x238
#define PART_DRAWN 0x400
#define PART_CHILD 0x428
#define PART_NEXT 0x430
#define PART_SIZE 0x470
#define INST_TRANSFORM 0x10   // position x, y, z at +8 of it
#define INST_ARCHIVE 0xb4
#define INST_UID 0xb8
#define INST_PARTS 0x150      // the parts' array, their count at +0x160
#define INST_PART_COUNT 0x160
#define UI_ARCHIVES 0xdc18f0ull   // main: the pointer to the table of interface archives
#define ANCHOR_SLOTS 1024
#define ANCHOR_PARTS 4096

static struct { const uint8_t *inst; uint32_t arc, uid; int8_t side[2]; } g_anchor[ANCHOR_SLOTS];
static unsigned g_anchor_n;

static float part_f(const uint8_t *p, unsigned off) {
    float f;
    memcpy(&f, p + off, sizeof f);
    return f;
}

// The columns (a = 0) or rows (a = 1), in the layout's own units from its origin, of the drawn parts under p (p's place
// at x on that axis, its scale sx).
static void anchor_span(const uint8_t *p, int a, float x, float sx, float *lo, float *hi, unsigned *n, int depth) {
    if (*(const uint64_t *)(p + PART_DRAWN)) {
        if (x < *lo) *lo = x;
        if (x > *hi) *hi = x;
    }
    if (++*n > ANCHOR_PARTS || depth > 24) return;
    unsigned o = 4u * (unsigned)a;
    for (const uint8_t *k = *(const uint8_t *const *)(p + PART_CHILD); k; k = *(const uint8_t *const *)(k + PART_NEXT))
        anchor_span(k, a, x + sx * part_f(k, PART_PLACE + o), sx * part_f(k, PART_SCALE + o) * part_f(k, PART_SCALE2 + o),
                    lo, hi, n, depth + 1);
}

// The name of the interface archive ("hud2", "menu", "core", ...) a layout instance's +0xb4 stands for, from the
// game's table of them (*(main+0xdc18f0): entries of 0x24 bytes at +8, {the number, the name}, their count at +0x18).
static const char *anchor_archive(uint32_t arc) {
    const uint8_t *tab = *(const uint8_t *const *)((uintptr_t)ac_main() + UI_ARCHIVES);
    const uint8_t *ents = tab ? *(const uint8_t *const *)(tab + 8) : NULL;
    uint64_t count = tab ? *(const uint64_t *)(tab + 0x18) : 0;
    for (uint64_t i = 0; ents && i < count && i < 256; i++)
        if (!memcmp(ents + i * 0x24, &arc, sizeof arc)) return (const char *)ents + i * 0x24 + 4;
    return "";
}

// The side a layout instance's block sits on along axis a: for columns (a = 0) -1 left, 1 right, for rows (a = 1) -1
// top, 1 bottom (the plane's y grows downwards), 0 neither, from where the layout puts what it draws: the middle of
// the columns or rows its drawn parts start at, in the outer thirds of the 1280 columns or 720 rows or not. Decided
// once per instance and layout, when it is first updated, over all its top parts (the parts no other part has as a
// child), so a row across the screen stays whole; the places are the ones the layout's animation holds then, which a
// block that slides in from its own side does not change the answer of. Only the gameplay HUD's archive has blocks to
// move: a menu is one composition over the middle 16:9, and its parts are clipped to it.
static int anchor_side(const uint8_t *inst, int a) {
    uint32_t arc, uid;
    memcpy(&arc, inst + INST_ARCHIVE, sizeof arc);
    memcpy(&uid, inst + INST_UID, sizeof uid);
    unsigned h = (unsigned)(((uintptr_t)inst >> 4) * 2654435761u) % ANCHOR_SLOTS;
    for (unsigned i = 0; i < ANCHOR_SLOTS; i++, h = (h + 1) % ANCHOR_SLOTS) {
        if (g_anchor[h].inst == inst && g_anchor[h].uid == uid && g_anchor[h].arc == arc) return g_anchor[h].side[a];
        if (!g_anchor[h].inst || g_anchor[h].inst == inst) break;
    }
    if (g_anchor_n >= ANCHOR_SLOTS * 3 / 4) {
        memset(g_anchor, 0, sizeof g_anchor);
        g_anchor_n = 0;
        h = (unsigned)(((uintptr_t)inst >> 4) * 2654435761u) % ANCHOR_SLOTS;
    }
    const uint8_t *parts = *(const uint8_t *const *)(inst + INST_PARTS);
    uint64_t count = *(const uint64_t *)(inst + INST_PART_COUNT);
    float lo[2] = {1e9f, 1e9f}, hi[2] = {-1e9f, -1e9f};
    unsigned n = 0;
    if (parts && count && count <= ANCHOR_PARTS && !strcmp(anchor_archive(arc), "hud2")) {
        uint8_t child[ANCHOR_PARTS / 8] = {0};
        for (uint64_t i = 0; i < count; i++)
            for (const uint8_t *k = *(const uint8_t *const *)(parts + i * PART_SIZE + PART_CHILD); k;
                 k = *(const uint8_t *const *)(k + PART_NEXT)) {
                uint64_t j = (uint64_t)(k - parts) / PART_SIZE;
                if (k < parts || j >= count || child[j >> 3] >> (j & 7) & 1) break;   // not this array's, or a loop
                child[j >> 3] |= (uint8_t)(1u << (j & 7));
            }
        for (uint64_t i = 0; i < count; i++)
            if (!(child[i >> 3] >> (i & 7) & 1)) {
                const uint8_t *p = parts + i * PART_SIZE;
                for (int k = 0; k < 2; k++) {
                    unsigned o = 4u * (unsigned)k, m = 0;
                    anchor_span(p, k, part_f(p, PART_PLACE + o), part_f(p, PART_SCALE + o) * part_f(p, PART_SCALE2 + o),
                                &lo[k], &hi[k], &m, 0);
                    if (!k) n += m;
                }
            }
    }
    int8_t side[2];
    for (int k = 0; k < 2; k++) {
        float mid = (lo[k] + hi[k]) * 0.5f, third = (k ? 360.0f : 640.0f) / 3;
        side[k] = (int8_t)(lo[k] > hi[k] ? 0 : mid < -third ? -1 : mid > third ? 1 : 0);
    }
    if (!g_anchor[h].inst) g_anchor_n++;
    g_anchor[h].side[0] = side[0], g_anchor[h].side[1] = side[1];
    g_anchor[h].arc = arc, g_anchor[h].uid = uid, g_anchor[h].inst = inst;
    if (0)
        LOG("resolution: wide: layout %s %04x at %p: columns %.0f..%.0f rows %.0f..%.0f of %u parts, side %d / %d",
               anchor_archive(arc), uid, (void *)inst, lo[0], hi[0], lo[1], hi[1], n, side[0], side[1]);
    return side[a];
}

// main+0x9111d8 (add x0,x19,#0x170), in the update of a layout part: x19 = the part, x21 = its parent's world
// transform, sp+0x10 = the part's world matrix, just made, which the part keeps and its children multiply by. A top
// part (its parent is its instance's transform) of a block that sits on one side moves to that side's edge of the
// picture: in a wider frame the 1280x720 plane shows 720 x ratio columns, so by half the difference along x; in a
// taller one 1280 / ratio rows, so by half the difference along y, for the blocks at the top and the bottom. Only an
// instance placed at the plane's middle is a screen layout; one placed elsewhere is put there by the game, on a place
// in the world or on a part of another layout, which has moved with its own block already.
void rt_wide_anchor(AcContext *c) {
    float r = ac_ratio();
    if (r == WIDE_16X9) return;
    const uint8_t *p = (const uint8_t *)(uintptr_t)c->x[19];
    const uint8_t *own = *(const uint8_t *const *)(p + PART_OWNER);
    if (!own || c->x[21] != (uint64_t)(uintptr_t)(own + INST_TRANSFORM)) return;
    int a = r < WIDE_16X9;   // the axis: 0 columns (wider), 1 rows (taller)
    float move = a ? 640.0f / r - 360.0f : 360.0f * r - 640.0f;
    if (fabsf(part_f(own, INST_TRANSFORM + 8 + 4 * a) - (a ? 360.0f : 640.0f)) >= move * 0.5f) return;
    if (a && fabsf(part_f(own, INST_TRANSFORM + 8) - 640.0f) >= move * 0.5f) return;   // and at the middle column
    int side = anchor_side(own, a);
    if (!side) return;
    float *m = (float *)(uintptr_t)((uintptr_t)(c + 1) + 0x10);
    m[12 + a] += (float)side * move;
}


static void ac_aspect_v1(AcContext *c, unsigned event) {
    if (strcmp(dm_main_build(), "4b159f0f7a360669738390ee8657b4f0")) return;
    uintptr_t base = ac_main(); float want = ac_ratio();
    if (event == 0) {
        uint8_t *lens = (uint8_t *)(uintptr_t)c->x[24];
        if (!ac_lens(lens)) return;
        uint64_t handle = *(uint64_t *)(base + 0xdc1910);
        if (handle && c->x[23] != handle) {
            const uint8_t *ui = *(uint8_t **)(uintptr_t)handle; float have;
            if (ui && ac_lens(ui)) {
                memcpy(&have, ui + 0x278, 4);
                if (have != want) {
                    const _Alignas(16) float eye[4] = {640,360,-2040,1}, target[4] = {640,360,-2039,1}, up[4] = {0,-1,0,1};
                    ((void (*)(uint64_t,const float *,const float *,const float *,uint64_t,uint64_t))(base + 0x9a2fa0))(handle,eye,target,up,0,1);
                }
            }
        }
        float have; memcpy(&have, lens + 0x278, 4);
        if (have != want) { memcpy(lens + 0x278, &want, 4); c->x[8] = 1; }
    } else if (event == 1) {
        if (want < WIDE_16X9) ac_scalar_set(c, 0, 2 * atanf(tanf(ac_scalar(c,0) * 0.5f) * WIDE_16X9 / want));
    } else if (event == 2 || event == 3) {
        ac_tall(c, (const uint8_t *)(uintptr_t)c->x[event == 2 ? 24 : 8]);
    } else if (event == 4) {
        static _Thread_local int32_t view[4]; const uint8_t *lens = (const uint8_t *)(uintptr_t)c->x[4];
        float ratio; memcpy(&ratio, lens + 0x278, 4);
        if (ac_lens(lens) && ratio > 0 && ratio < WIDE_16X9 / 1.001f) {
            memcpy(view, lens + 0x260, sizeof view);
            int32_t height = (int32_t)lroundf((float)view[2] / ratio);
            view[1] += (view[3] - height) / 2; view[3] = height;
            c->x[8] = (uintptr_t)view;
        }
    } else if (event == 5) {
        uint8_t *cam = (uint8_t *)(uintptr_t)c->x[19];
        const uint8_t *array = *(const uint8_t **)(base + 0xdc2d50);
        const uint8_t *first = array ? *(const uint8_t *const *)array : NULL;
        if (first && cam == first + 0x40) {
            float bounds[6], have[6]; memcpy(bounds, first + 0x18, sizeof bounds); memcpy(have, cam + 0x18, sizeof have);
            float mid = (bounds[2] + bounds[3]) * 0.5f, half = (bounds[3] - bounds[2]) * 0.5f * WIDE_16X9 / want;
            bounds[2] = mid - half; bounds[3] = mid + half;
            if (memcmp(bounds, have, sizeof bounds)) { memcpy(cam + 0x18, bounds, sizeof bounds); c->x[8] = 1; }
        }
    } else if (event == 6) rt_wide_anchor(c);
}
static void *nvn_profile_runtime_lookup(const char *name) {
    return !strcmp(name,"nxnativeAcAspectV1") ? (void *)ac_aspect_v1 : NULL;
}
static void nvn_profile_set_rt(const NVNcommandBuffer *c, int n, const NVNtexture *const *ct, uint64_t caller) {
    (void)c; (void)n; (void)ct; (void)caller;
    static int mode = -1;
    if (mode < 0) { const char *v = getenv("DM_AC_SCREEN_RATIO"); mode = v && !strcmp(v,"1610") && !strcmp(dm_main_build(),"4b159f0f7a360669738390ee8657b4f0"); if (mode) LOG("ASTRAL CHAIN 16:10: taller camera, proportional interface, world markers and HUD anchors"); }
    if (mode) mtl_present_layer(16, dm_movie_playing() ? 9 : 10);
}
