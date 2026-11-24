#!/usr/bin/env python3
"""ASTRAL CHAIN 1.0.1: the sun shadow receiver (shadowreceiver_lv2_velocity, fragment key 7046415660d93f94_b) with a better filter, for the host MSL library.

The translated shader (the chain's `<key>_b.metal`) takes 17 hard compares of a nearest-filtered atlas at a fixed spacing. This script copies it and replaces the tap
block (from `float _397 = fma(_395, 0.5, _375);` to `_337 = as_type<int>(_807);`) with a call of ac_shadow_pcss: a blocker search, the penumbra width from the blocker
distance and the sun's angular size, and a percentage-closer filter of bilinear compares (gathers) over a rotated disc, with a receiver-plane depth bias. Everything else
(the cascade choice, the matrices, the motion output, the entry points and function constants) stays as translated.
Usage: astral_shadow_receiver.py <the chain's 7046415660d93f94_b.metal> <output .metal>   (get the source with: shader_lib.py cat <b-<chain> folder> 7046415660d93f94_b.metal)"""
import sys, re

START = '        float _397 = fma(_395, 0.5, _375);\n'
END = '        _337 = as_type<int>(_807);\n'
HELPER = r'''
// ---- ASTRAL CHAIN shadow filter (dm/tools/astral_shadow_receiver.py) ----
// c13 row 1 holds the filter's parameters (the host writes them): y = the sun's angular half-size in radians, z = the largest penumbra in metres, w = quality (1).
static inline float2 ac_vogel(int i, int n, float rot) { float r = sqrt((float(i) + 0.5) / float(n)), a = float(i) * 2.39996323 + rot; return r * float2(cos(a), sin(a)); }
static float ac_shadow_pcss(texture2d<float> atlas, sampler s, float2 uc, float2 tmin, float zr, float ax, float az, float theta, float maxpen, float2 pix)
{
    float2 dim = float2(atlas.get_width(), atlas.get_height()), lo = tmin + 2.5 / dim, hi = tmin + 0.5 - 2.5 / dim;
    // the receiver plane's depth slope per atlas unit, from the screen derivatives, limited to a slope of 3 so a silhouette's derivative cannot run away
    float2 dux = dfdx(uc), duy = dfdy(uc); float det = dux.x * duy.y - dux.y * duy.x, zx = dfdx(zr), zy = dfdy(zr);
    float2 g = fabs(det) > 1e-14 ? float2((duy.y * zx - dux.y * zy) / det, (-duy.x * zx + dux.x * zy) / det) : float2(0.0);
    float gmax = 3.0 * az / max(ax, 1e-9); g = clamp(g, -gmax, gmax);
    float tol = 0.7 * az / max(ax, 1e-9);   // a sample d away may lie up to 0.7 d closer to the light (curved or sloped surfaces) without being a blocker
    float rot = 6.2831853 * fract(52.9829189 * fract(dot(pix, float2(0.06711056, 0.00583715))));
    float rs = maxpen * ax, zsum = 0.0; int nb = 0;
    for (int i = 0; i < 12; i++) {
        float2 o = ac_vogel(i, 12, rot) * rs; float4 d = atlas.gather(s, clamp(uc + o, lo, hi)); float ze = zr + dot(g, o) - tol * length(o);
        for (int k = 0; k < 4; k++) if (d[k] < ze) { zsum += d[k]; nb++; }
    }
    if (nb == 0) return 1.0;
    float zb = zsum / float(nb), pen = clamp((zr - zb) / az * theta, 0.002, maxpen), rf = pen * ax, occ = 0.0;
    for (int i = 0; i < 24; i++) {
        float2 o = ac_vogel(i, 24, rot + 1.0) * rf, uv = clamp(uc + o, lo, hi); float4 d = atlas.gather(s, uv); float ze = zr + dot(g, o) - tol * length(o);
        float2 f = fract(uv * dim - 0.5); float4 c = float4(ze >= d.x, ze >= d.y, ze >= d.z, ze >= d.w);   // gather order: (i0,j1) (i1,j1) (i1,j0) (i0,j0)
        occ += mix(mix(c.w, c.z, f.x), mix(c.x, c.y, f.x), f.y);
    }
    return 1.0 - occ / 24.0;
}
'''
REPLACEMENT = '''        float2 _ac_c = float2(_375, _373);
        bool _ac_c0 = int(_327) == 0;
        float _ac_ax = 0.25 * length(float3((*spvDescriptorSet0.fp_c13)._m0[_ac_c0 ? 7 : 11].xyz)), _ac_az = length(float3((*spvDescriptorSet0.fp_c13)._m0[_ac_c0 ? 9 : 13].xyz));
        float _807 = ac_shadow_pcss(spvDescriptorSet0.fp_t_tcb_1E, spvDescriptorSet0.fp_t_tcb_1ESmplr, _ac_c, float2(_357, _355), _369, _ac_ax, _ac_az, (*spvDescriptorSet0.fp_c13)._m0[1].y, (*spvDescriptorSet0.fp_c13)._m0[1].z, in.dm_frag.xy);
        _337 = as_type<int>(_807);
'''
def main(src, dst):
    s = open(src).read()
    a = s.index(START); b = s.index(END) + len(END)
    assert s.count(START) == 1 and s.count(END) == 1
    s = s[:a] + REPLACEMENT + s[b:]
    # the helper goes before the shared body, and the stage input gets the fragment position
    k = s.index('static __attribute__((always_inline)) main0_out dm_body_main0(')
    s = s[:k] + HELPER + '\n' + s[k:]
    s = s.replace('    float4 m_39 [[user(locn1)]];\n};', '    float4 m_39 [[user(locn1)]];\n    float4 dm_frag [[position]];\n};', 1)
    assert 'dm_frag [[position]]' in s
    open(dst, 'w').write(s)
if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(*sys.argv[1:])
