// DM_NVN_ANISO's choice of samplers (nvn_aniso.h): surface samplers get the floor, the rest keep the game's value
#include <stdio.h>
#include <stdlib.h>
#include "../nvn/nvn_aniso.h"

static int fails;
#define CHECK(c, what) do { if (!(c)) { printf("FAIL %s\n", what); fails++; } } while (0)

int main(void) {
    CHECK(nvn_aniso_floor(5, 1, 0, 0, 0, 16, 1, 8) == 8, "trilinear surface sampler takes the floor");
    CHECK(nvn_aniso_floor(3, 1, 0, 0, 0, 16, 1, 16) == 1, "linear with the nearest mip keeps the game's value (data textures: Astral Chain speckle)");
    CHECK(nvn_aniso_floor(5, 1, 0, 0, 0, 16, 1, 0) == 1, "off: the game's value");
    CHECK(nvn_aniso_floor(5, 1, 0, 0, 0, 16, 16, 8) == 16, "a game value above the floor stays");
    CHECK(nvn_aniso_floor(1, 1, 0, 0, 0, 16, 1, 8) == 1, "no mips: unchanged");
    CHECK(nvn_aniso_floor(4, 1, 0, 0, 0, 16, 1, 8) == 1, "nearest minification: unchanged");
    CHECK(nvn_aniso_floor(5, 0, 0, 0, 0, 16, 1, 8) == 1, "nearest magnification (a lookup): unchanged");
    CHECK(nvn_aniso_floor(5, 1, 1, 0, 0, 16, 1, 8) == 1, "depth comparison (shadow map): unchanged");
    CHECK(nvn_aniso_floor(5, 1, 0, 1, 0, 16, 1, 8) == 1, "min reduction (depth pyramid): unchanged");
    CHECK(nvn_aniso_floor(5, 1, 0, 0, 2, 2, 1, 8) == 1, "clamped to one LOD: unchanged");
    CHECK(nvn_aniso_env(NULL) == 0 && nvn_aniso_env("1") == 0 && nvn_aniso_env("8") == 8 && nvn_aniso_env("16") == 16 && nvn_aniso_env("32") == 0 && nvn_aniso_env("x") == 0,
          "the switch takes 2 to 16, anything else is off");
    printf("aniso: %s\n", fails ? "FAILED" : "passed");
    CHECK(nvn_texture_bias(5,1,0,0,0,16,0,-.5f)==-.5f, "surface mip bias sharpens existing textures");
    CHECK(nvn_texture_bias(5,1,1,0,0,16,0,-1)==0, "shadow compare unaffected by sharpness");
    CHECK(nvn_texture_bias(5,1,0,1,0,16,0,-1)==0, "depth reduction unaffected by sharpness");
    CHECK(nvn_texture_bias(5,1,0,0,2,2,0,-1)==0, "fixed mip unaffected by sharpness");
    CHECK(nvn_texture_bias(1,1,0,0,0,16,0,-1)==0, "screen-space non-mip sampler unaffected");
    CHECK(nvn_texture_bias(3,1,0,0,0,16,0,-1)==0, "nearest-mip data samplers unaffected by sharpness");
    CHECK(nvn_texture_bias_env("-.5")==-.5f && nvn_texture_bias_env("nan")==0 && nvn_texture_bias_env("-2")==0 && nvn_texture_bias_env("-1junk")==0, "mip bias parsing rejects non-finite and invalid settings");
    return fails != 0;
}
