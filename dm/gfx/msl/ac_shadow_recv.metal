#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;
constant bool dm_border_off [[function_constant(216)]];
constant bool dm_border_live = !is_function_constant_defined(dm_border_off) || !dm_border_off;
#define DM_BORDER_LIVE dm_border_live

struct dm_border_t { uint mask; float4 k[32]; };
static inline __attribute__((always_inline)) float4 dm_bmix(float4 r, float4 w, float4 k) { return r + (w - r) * k; }
static inline __attribute__((always_inline)) float dm_bmix(float r, float w, float4 k) { return r + (w - r) * k.x; }
template<typename V, typename T, typename... A> static inline __attribute__((always_inline)) V dm_bs(V r, constant dm_border_t* b, uint i, T t, sampler w, A... a)
{
    if (DM_BORDER_LIVE && (b->mask >> i & 1u)) r = dm_bmix(r, t.sample(w, a...), b->k[i]);
    return r;
}

struct _10
{
    uint _m0;
    uint _m1[8];
    float4 _m2;
    float4 _m3;
    int _m4;
    float _m5[73];
    int4 _m6;
    int _m7;
};

struct _16
{
    float4 _m0[4096];
};

struct spvDescriptorSetBuffer0
{
    constant _16* fp_c13 [[id(0)]];
    constant _16* fp_c16 [[id(1)]];
    constant _16* fp_c3 [[id(2)]];
    constant _16* fp_c6 [[id(3)]];
    constant _16* fp_c1 [[id(4)]];
    texture2d<float> fp_t_tcb_14 [[id(5)]];
    sampler fp_t_tcb_14Smplr [[id(6)]];
    texture2d<float> fp_t_tcb_1E [[id(7)]];
    sampler fp_t_tcb_1ESmplr [[id(8)]];
    sampler fp_t_tcb_14Smplr_w [[id(9)]];
    sampler fp_t_tcb_1ESmplr_w [[id(10)]];
    constant dm_border_t* dm_border [[id(11)]];
};

struct main0_out
{
    float4 m_42 [[color(0)]];
    float4 m_44 [[color(1)]];
};

struct main0_in
{
    float4 m_37 [[user(locn0)]];
    float4 m_39 [[user(locn1)]];
    float4 dm_frag [[position]];
};

struct dm_blend_state { uint zero; };   // see dmsh_rewrite.py blend_zero
static inline __attribute__((always_inline)) float4 dm_bz(float4 c, uint m)
{
    m &= 3u;
    if (!((m == 1u && c.w == 0.0f) || (m == 2u && c.w == 1.0f))) return c;
    return float4(select(c.xyz, float3(0.0f), (as_type<uint3>(c.xyz) & uint3(0x7f800000u)) == uint3(0x7f800000u)), c.w);   // NaN or Inf by its bits: fast math may assume there is none
}
static inline __attribute__((always_inline)) void dm_blend0(thread main0_out& dm_o, constant dm_blend_state& dm_s)
{
    uint m = dm_s.zero;
    if (m == 0u) return;
    dm_o.m_42 = dm_bz(dm_o.m_42, m >> 0u);
    dm_o.m_44 = dm_bz(dm_o.m_44, m >> 2u);
}


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

static __attribute__((always_inline)) main0_out dm_body_main0(main0_in in, constant spvDescriptorSetBuffer0& spvDescriptorSet0, constant dm_blend_state& dm_blend)
{
    main0_out out = {};
    bool _799 = false;
    float _51 = in.m_37.x;
    float _53 = in.m_37.y;
    float2 _848 = float2(_51, _53);
    float _55 = dm_bs(spvDescriptorSet0.fp_t_tcb_14.sample(spvDescriptorSet0.fp_t_tcb_14Smplr, select(_848, float2(0.0), isnan(_848))), spvDescriptorSet0.dm_border, 0u, spvDescriptorSet0.fp_t_tcb_14, spvDescriptorSet0.fp_t_tcb_14Smplr_w, select(_848, float2(0.0), isnan(_848))).x;
    float _57 = in.m_39.x;
    float _59 = in.m_39.y;
    float _61 = in.m_39.z;
    float _63 = in.m_39.w;
    float _65 = (*spvDescriptorSet0.fp_c13)._m0[0].x * (*spvDescriptorSet0.fp_c13)._m0[1].x;
    float _67 = _65 * 0.100000001490116119384765625;
    uint _70 = uint(int(uint(0) >> uint(16)));
    int _73 = int(_70) << 16;
    float _75 = fma(_55, (*spvDescriptorSet0.fp_c16)._m0[0].y, (*spvDescriptorSet0.fp_c16)._m0[0].x);
    float _77 = _75 * _57;
    float _79 = _75 * _59;
    float _81 = _77 * _61;
    float _83 = _79 * _63;
    float _85 = _81 * (*spvDescriptorSet0.fp_c3)._m0[12].x;
    float _87 = _81 * (*spvDescriptorSet0.fp_c3)._m0[13].x;
    float _89 = fma(_83, (*spvDescriptorSet0.fp_c3)._m0[12].y, _85);
    float _91 = _81 * (*spvDescriptorSet0.fp_c3)._m0[14].x;
    float _93 = fma(_83, (*spvDescriptorSet0.fp_c3)._m0[13].y, _87);
    float _95 = -(*spvDescriptorSet0.fp_c3)._m0[12].z;
    float _97 = fma(_75, _95, _89);
    float _99 = fma(_83, (*spvDescriptorSet0.fp_c3)._m0[14].y, _91);
    float _101 = -(*spvDescriptorSet0.fp_c3)._m0[13].z;
    float _103 = fma(_75, _101, _93);
    float _105 = _97 + (*spvDescriptorSet0.fp_c3)._m0[12].w;
    float _107 = -(*spvDescriptorSet0.fp_c3)._m0[14].z;
    float _109 = fma(_75, _107, _99);
    float _111 = _103 + (*spvDescriptorSet0.fp_c3)._m0[13].w;
    float _113 = _105 * (*spvDescriptorSet0.fp_c13)._m0[10].x;
    float _115 = _109 + (*spvDescriptorSet0.fp_c3)._m0[14].w;
    float _117 = _105 * (*spvDescriptorSet0.fp_c13)._m0[8].x;
    float _119 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[10].y, _113);
    float _121 = _105 * (*spvDescriptorSet0.fp_c13)._m0[9].x;
    float _123 = _105 * (*spvDescriptorSet0.fp_c13)._m0[7].x;
    float _125 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[8].y, _117);
    float _127 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[10].z, _119);
    float _129 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[9].y, _121);
    float _131 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[7].y, _123);
    float _133 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[8].z, _125);
    float _135 = _127 + (*spvDescriptorSet0.fp_c13)._m0[10].w;
    float _137 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[9].z, _129);
    float _139 = 1.0 / _135;
    float _141 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[7].z, _131);
    float _143 = _133 + (*spvDescriptorSet0.fp_c13)._m0[8].w;
    float _145 = _137 + (*spvDescriptorSet0.fp_c13)._m0[9].w;
    float _147 = _141 + (*spvDescriptorSet0.fp_c13)._m0[7].w;
    float _149 = -_67;
    float _151 = fma(_145, _139, _149);
    float _153 = _143 * _139;
    float _155 = _147 * _139;
    float _157 = abs(_151);
    float _159 = abs(_153);
    float _161 = precise::max(_157, _159);
    float _163 = _105 * (*spvDescriptorSet0.fp_c13)._m0[14].x;
    float _165 = abs(_155);
    float _167 = precise::max(_165, _161);
    float _169 = _105 * (*spvDescriptorSet0.fp_c6)._m0[4].x;
    float _171 = _105 * (*spvDescriptorSet0.fp_c6)._m0[2].x;
    float _173 = abs(_167);
    bool _177 = _173 < 1.1754943508222875079687365372222e-38;
    float _179 = _177 ? 0.0 : _167;
    float _181 = abs((*spvDescriptorSet0.fp_c1)._m0[0].x);
    bool _183 = _181 < 1.1754943508222875079687365372222e-38;
    float _185 = _183 ? 0.0 : (*spvDescriptorSet0.fp_c1)._m0[0].x;
    bool _187 = _179 <= _185;
    float _189 = fma(_111, (*spvDescriptorSet0.fp_c6)._m0[4].y, _169);
    float _191 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[14].y, _163);
    float _193 = _105 * (*spvDescriptorSet0.fp_c6)._m0[1].x;
    float _195 = _105 * (*spvDescriptorSet0.fp_c13)._m0[13].x;
    float _197 = fma(_111, (*spvDescriptorSet0.fp_c6)._m0[2].y, _171);
    float _199 = fma(_115, (*spvDescriptorSet0.fp_c6)._m0[4].z, _189);
    float _201 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[14].z, _191);
    float _203 = fma(_111, (*spvDescriptorSet0.fp_c6)._m0[1].y, _193);
    float _205 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[13].y, _195);
    uint _207 = uint(_73);
    int _209 = 0;
    float _211 = _153;
    float _213 = _155;
    if (_187)
    {
        float _215 = float2(as_type<half2>(uint(_73))).y;
        uint _217 = as_type<uint>(half2(float2(-1.0, _215)));
        _207 = _217;
    }
    uint _219 = _207;
    float _221 = fma(_115, (*spvDescriptorSet0.fp_c6)._m0[2].z, _197);
    float _223 = _199 + (*spvDescriptorSet0.fp_c6)._m0[4].w;
    float _225 = _201 + (*spvDescriptorSet0.fp_c13)._m0[14].w;
    float _227 = 1.0 / _223;
    float _229 = _105 * (*spvDescriptorSet0.fp_c13)._m0[12].x;
    float _231 = 1.0 / _225;
    float _233 = _105 * (*spvDescriptorSet0.fp_c13)._m0[11].x;
    float _235 = float2(as_type<half2>(_219)).x;
    bool _237 = _235 == 0.0;
    float _239 = float2(as_type<half2>(_219)).x;
    bool _241 = _239 >= 0.0;
    float _243 = (*spvDescriptorSet0.fp_c13)._m0[0].y * (*spvDescriptorSet0.fp_c13)._m0[1].y;
    float _245 = fma(_115, (*spvDescriptorSet0.fp_c6)._m0[1].z, _203);
    float _247 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[13].z, _205);
    float _249 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[12].y, _229);
    float _251 = fma(_111, (*spvDescriptorSet0.fp_c13)._m0[11].y, _233);
    float _253 = _221 + (*spvDescriptorSet0.fp_c6)._m0[2].w;
    float _255 = _243 * 0.100000001490116119384765625;
    float _257 = _245 + (*spvDescriptorSet0.fp_c6)._m0[1].w;
    float _259 = _247 + (*spvDescriptorSet0.fp_c13)._m0[13].w;
    float _261 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[12].z, _249);
    float _263 = fma(_115, (*spvDescriptorSet0.fp_c13)._m0[11].z, _251);
    float _265 = _253 * _227;
    uint _267 = _219;
    if (_237)
    {
        _209 = 1;
    }
    int _269 = _209;
    float _271 = _257 * _227;
    float _273 = -_255;
    float _275 = fma(_259, _231, _273);
    uint _277 = uint(_269);
    uint _279 = uint(_269);
    if (_241)
    {
        float _281 = _261 + (*spvDescriptorSet0.fp_c13)._m0[12].w;
        float _283 = _263 + (*spvDescriptorSet0.fp_c13)._m0[11].w;
        float _285 = _231 * _281;
        float _287 = _231 * _283;
        float _289 = abs(_275);
        float _291 = abs(_285);
        float _293 = precise::max(_289, _291);
        float _295 = abs(_287);
        float _297 = precise::max(_295, _293);
        float _299 = abs(_297);
        bool _301 = _299 < 1.1754943508222875079687365372222e-38;
        float _303 = _301 ? 0.0 : _297;
        float _305 = abs((*spvDescriptorSet0.fp_c1)._m0[0].x);
        bool _307 = _305 < 1.1754943508222875079687365372222e-38;
        float _309 = _307 ? 0.0 : (*spvDescriptorSet0.fp_c1)._m0[0].x;
        bool _311 = _303 <= _309;
        _211 = _285;
        _213 = _287;
        if (_311)
        {
            float _313 = float2(as_type<half2>(_219)).y;
            uint _315 = as_type<uint>(half2(float2(-1.0, _313)));
            _267 = _315;
        }
        uint _317 = _267;
        float _319 = float2(as_type<half2>(_317)).x;
        bool _321 = _319 == 0.0;
        if (_321)
        {
            int _323 = _269 + 1;
            _277 = uint(_323);
        }
        uint _325 = _277;
        _279 = _325;
    }
    uint _327 = _279;
    float _329 = _211;
    float _331 = _213;
    bool _333 = _327 < 2u;
    float _335 = 1.0;
    int _337 = 1065353216;
    if (_333)
    {
        uint _339 = uint(int(uint(int(_327)) >> uint(1)));
        int _341 = int(_327) & 1;
        float _343 = float(_339);
        int _345 = int(_327) << 4;
        float _347 = float(uint(_341));
        bool _349 = int(_327) == 0;
        bool _351 = _345 == 0;
        bool _353 = _345 == 16;
        float _355 = _343 * 0.5;
        float _357 = _347 * 0.5;
        float _359 = fma(_329, -0.25, _355);
        float _361 = fma(_331, 0.25, _357);
        float _363 = _357;
        if (_351)
        {
            _335 = _151;
        }
        float _365 = _335;
        float _367 = _365;
        if (_353)
        {
            _367 = _275;
        }
        float _369 = _367;
        if (_349)
        {
            _363 = (*spvDescriptorSet0.fp_c13)._m0[2].x;
        }
        float _371 = _363;
        float _373 = _359 + 0.25;
        float _375 = _361 + 0.25;
        float _377 = _371;
        float _379 = _371;
        if (!_349)
        {
            bool _381 = int(_327) == 1;
            if (_381)
            {
                _377 = (*spvDescriptorSet0.fp_c13)._m0[2].y;
            }
            float _383 = _377;
            float _385 = _383;
            _379 = _383;
            if (!_381)
            {
                bool _387 = int(_327) == 2;
                if (_387)
                {
                    _385 = (*spvDescriptorSet0.fp_c13)._m0[2].z;
                }
                float _389 = _385;
                float _391 = _389;
                if (!_387)
                {
                    _391 = (*spvDescriptorSet0.fp_c13)._m0[2].w;
                }
                float _393 = _391;
                _379 = _393;
            }
        }
        float _395 = _379;
        float2 _ac_c = float2(_375, _373);
        bool _ac_c0 = int(_327) == 0;
        float _ac_ax = 0.25 * length(float3((*spvDescriptorSet0.fp_c13)._m0[_ac_c0 ? 7 : 11].xyz)), _ac_az = length(float3((*spvDescriptorSet0.fp_c13)._m0[_ac_c0 ? 9 : 13].xyz));
        float _807 = ac_shadow_pcss(spvDescriptorSet0.fp_t_tcb_1E, spvDescriptorSet0.fp_t_tcb_1ESmplr, _ac_c, float2(_357, _355), _369, _ac_ax, _ac_az, (*spvDescriptorSet0.fp_c13)._m0[1].y, (*spvDescriptorSet0.fp_c13)._m0[1].z, in.dm_frag.xy);
        _337 = as_type<int>(_807);
    }
    int _809 = _337;
    float _811 = _75 * 0.00999999977648258209228515625;
    float _813 = precise::clamp(_811, 0.0, 1.0);
    float _815 = -_271;
    float _817 = _57 + _815;
    float _819 = -_265;
    float _821 = _59 + _819;
    float _823 = _813 * _813;
    float _825 = _823 * _817;
    float _827 = _823 * _821;
    float _829 = _825 * (*spvDescriptorSet0.fp_c6)._m0[0].x;
    float _831 = _827 * (*spvDescriptorSet0.fp_c6)._m0[0].x;
    float _833 = fma(_829, 2.0, 0.5);
    float _835 = fma(_831, 2.0, 0.5);
    out.m_42.x = _833;
    out.m_42.y = _835;
    out.m_42.z = 0.0;
    out.m_42.w = 0.0;
    out.m_44.x = as_type<float>(_809);
    out.m_44.y = as_type<float>(_809);
    out.m_44.z = as_type<float>(_809);
    out.m_44.w = as_type<float>(_809);
    dm_blend0(out, dm_blend);
    return out;
}
fragment main0_out main0(main0_in in [[stage_in]], constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], constant dm_blend_state& dm_blend [[buffer(28)]])
{
    main0_out out = dm_body_main0(in, spvDescriptorSet0, dm_blend);
    return out;
}



constant bool dm_ui0 [[function_constant(208)]];
constant bool dm_uf0 = !dm_ui0;
constant bool dm_ui1 [[function_constant(209)]];
constant bool dm_uf1 = !dm_ui1;

struct main0_out_u
{
    float4 m_42 [[color(0), function_constant(dm_uf0)]];
    uint4 m_42_ui [[color(0), function_constant(dm_ui0)]];
    float4 m_44 [[color(1), function_constant(dm_uf1)]];
    uint4 m_44_ui [[color(1), function_constant(dm_ui1)]];
};

fragment main0_out_u main0_u(main0_in in [[stage_in]], constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], constant dm_blend_state& dm_blend [[buffer(28)]])
{
    main0_out out = dm_body_main0(in, spvDescriptorSet0, dm_blend);
    main0_out_u r = {};
    if (dm_ui0) r.m_42_ui = as_type<uint4>(out.m_42); else r.m_42 = out.m_42;
    if (dm_ui1) r.m_44_ui = as_type<uint4>(out.m_44); else r.m_44 = out.m_44;
    return r;
}
