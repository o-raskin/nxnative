// ASTRAL CHAIN graphics presets: DM_AC_PRESET names a set of the graphics switches (the launcher shows the individual rows only for "custom"). Compiled into the host for this
// profile only; a named preset overwrites the switches it lists, whatever the environment held, and leaves every other switch (frame rate, screen ratio, dynamic
// resolution, anisotropy, memory pool) as the player chose it.
#include <stdlib.h>
#include <string.h>
typedef struct { const char *name; const char *vars[16][2]; } ac_preset_t;
static const ac_preset_t k_ac_presets[] = {
    {"original", {{"DM_AC_RESOLUTION", "default"}, {"DM_AC_AA", "default"}, {"DM_NVN_TEXTURE_BIAS", "0"}, {"DM_PRESENT_QUALITY", "off"}, {"DM_AC_SHADOW", "default"}, {"DM_AC_SHADOW_FILTER", "default"}, {"DM_AC_CONTACT", "off"},
        {"DM_AC_AO", "off"}, {"DM_AC_GI", "off"}, {"DM_AC_SSR", "off"}, {"DM_AC_FOG", "default"}, {"DM_AC_MODEL_QUALITY", "default"}, {"DM_AC_DRAW_DISTANCE", "default"}, {"DM_AC_UI", "default"}}},
    {"balanced", {{"DM_AC_RESOLUTION", "1440p"}, {"DM_AC_AA", "high"}, {"DM_NVN_TEXTURE_BIAS", "0"}, {"DM_PRESENT_QUALITY", "off"}, {"DM_AC_SHADOW", "high"}, {"DM_AC_SHADOW_FILTER", "default"}, {"DM_AC_CONTACT", "off"},
        {"DM_AC_AO", "low"}, {"DM_AC_GI", "off"}, {"DM_AC_SSR", "off"}, {"DM_AC_FOG", "default"}, {"DM_AC_MODEL_QUALITY", "x2"}, {"DM_AC_DRAW_DISTANCE", "x2"}, {"DM_APP_POOL", "10G"}, {"DM_AC_UI", "match"}}},
    {"high", {{"DM_AC_RESOLUTION", "2160p"}, {"DM_AC_AA", "high"}, {"DM_NVN_TEXTURE_BIAS", "0"}, {"DM_PRESENT_QUALITY", "scale"}, {"DM_AC_SHADOW", "high"}, {"DM_AC_SHADOW_FILTER", "default"}, {"DM_AC_CONTACT", "low"},
        {"DM_AC_AO", "high"}, {"DM_AC_GI", "off"}, {"DM_AC_SSR", "off"}, {"DM_AC_FOG", "default"}, {"DM_AC_MODEL_QUALITY", "x4"}, {"DM_AC_DRAW_DISTANCE", "x4"}, {"DM_APP_POOL", "10G"}, {"DM_AC_UI", "match"}}},
    {"maximum", {{"DM_AC_RESOLUTION", "2880p"}, {"DM_AC_AA", "high"}, {"DM_NVN_TEXTURE_BIAS", "-0.5"}, {"DM_PRESENT_QUALITY", "sharp"}, {"DM_AC_SHADOW", "ultra"}, {"DM_AC_SHADOW_FILTER", "pcss"}, {"DM_AC_CONTACT", "high"},
        {"DM_AC_AO", "ultra"}, {"DM_AC_GI", "high"}, {"DM_AC_SSR", "high"}, {"DM_AC_FOG", "default"}, {"DM_AC_MODEL_QUALITY", "high"}, {"DM_AC_DRAW_DISTANCE", "high"}, {"DM_APP_POOL", "10G"}, {"DM_AC_UI", "match"}}},
    {"performance_120", {{"DM_AC_RESOLUTION", "1440p"}, {"DM_AC_AA", "high"}, {"DM_NVN_TEXTURE_BIAS", "0"}, {"DM_PRESENT_QUALITY", "off"}, {"DM_AC_SHADOW", "high"}, {"DM_AC_SHADOW_FILTER", "default"}, {"DM_AC_CONTACT", "off"},
        {"DM_AC_AO", "off"}, {"DM_AC_GI", "off"}, {"DM_AC_SSR", "off"}, {"DM_AC_FOG", "default"}, {"DM_AC_MODEL_QUALITY", "x2"}, {"DM_AC_DRAW_DISTANCE", "x2"}, {"DM_APP_POOL", "10G"}, {"DM_FPS_TARGET", "120"}, {"DM_AC_UI", "match"}}},
};
static void ac_presets_apply(void) {
    const char *want = getenv("DM_AC_PRESET");
    if (!want || !*want || !strcmp(want, "custom")) return;
    for (size_t i = 0; i < sizeof k_ac_presets / sizeof k_ac_presets[0]; i++) {
        if (strcmp(want, k_ac_presets[i].name)) continue;
        for (int k = 0; k < 16 && k_ac_presets[i].vars[k][0]; k++) setenv(k_ac_presets[i].vars[k][0], k_ac_presets[i].vars[k][1], 1);
        LOG("ASTRAL CHAIN graphics preset %s (DM_AC_PRESET): its switches replace the individual ones", want);
        return;
    }
    LOG("[RED] DM_AC_PRESET=%s is not a preset of this game (original, balanced, high, maximum, performance_120, custom); the individual switches stand", want);
}
// DM_AC_UI=match draws the interface at the render resolution: the manifest's variable DM_AC_UI_RES takes the resolution's name (native, 1080p, 1440p, 2160p, 2880p)
static void dm_profile_presets(void) {
    ac_presets_apply();
    const char *ui = getenv("DM_AC_UI"), *res = getenv("DM_AC_RESOLUTION");
    if (ui && !strcmp(ui, "match") && res && (!strcmp(res, "native") || !strcmp(res, "1080p") || !strcmp(res, "1440p") || !strcmp(res, "2160p") || !strcmp(res, "2880p"))) {
        setenv("DM_AC_UI_RES", res, 1); LOG("ASTRAL CHAIN interface: drawn at %s (DM_AC_UI=match)", res); }
}
