// DM_NVN_ANISO=<2..16>: a floor on the anisotropy of the game's texture samplers (default off: the game's own value, as on the console). Only samplers that
// filter linearly in the texture and trilinearly across mips (min filter 5) take it, the ones that sample surface textures: not a nearest filter (lookup
// tables, pixel art), not a nearest-mip one (min filter 3: the engine's choice for data textures; anisotropy on them turned Astral Chain's surfaces into red
// speckle), not a sampler without mips or clamped to one LOD (a screen-space read, where the derivatives are isotropic anyway), not a depth comparison
// (shadow maps) or a min / max reduction (depth pyramids), whose results anisotropy would change. A game value above the floor stays. Metroid Prime 4 sets 1 on every sampler.
#pragma once
#include <stdlib.h>

// minf: NVN minification filter (0 nearest, 1 linear, 2 / 3 nearest / linear with the nearest mip, 4 / 5 with linear mips); magf: 0 nearest, 1 linear
static inline float nvn_aniso_floor(int minf, int magf, int cmp_mode, int reduction, float lod_min, float lod_max, float aniso, int floor_) {
    if (floor_ <= 1 || magf == 0 || minf != 5 || cmp_mode || reduction || lod_max <= lod_min) return aniso;
    return aniso > (float)floor_ ? aniso : (float)floor_;
}

// The switch's value: 0 (off) unless it is 2 to 16; read once
static inline int nvn_aniso_env(const char *e) {
    int v = e ? atoi(e) : 0;
    return v >= 2 && v <= 16 ? v : 0;
}

// DM_NVN_TEXTURE_BIAS: extra mip bias for surface detail, 0 to -1. Lookup,
// comparison, reduction, non-mipmapped and fixed-LOD reads keep their semantics.
static inline float nvn_texture_bias(int minf, int magf, int cmp_mode, int reduction,
                                     float lod_min, float lod_max, float bias, float extra) {
    if (!magf || minf != 5 || cmp_mode || reduction || lod_max <= lod_min) return bias;
    return bias + extra;
}
static inline float nvn_texture_bias_env(const char *e) {
    if (!e) return 0;
    char *end; float v = strtof(e, &end);
    return end != e && !*end && v >= -1.0f && v <= 0.0f ? v : 0.0f;
}
