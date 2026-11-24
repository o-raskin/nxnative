// The present: the frame drawn into the drawable, cropped (nvn_mtl.m present_pipeline)
#include <metal_stdlib>
using namespace metal;
struct V { float4 p [[position]]; float2 uv; };
vertex V vs(uint id [[vertex_id]]) { float2 uv = float2((id << 1) & 2, id & 2); V o; o.p = float4(uv * float2(2, -2) + float2(-1, 1), 0, 1); o.uv = uv; return o; }
// post: x = sharpening (0..1), y = mode (0 = the plain bilinear present, 1 = clean scaling, 2 = clean scaling with sharpening, 3 = Lanczos-3 scaling); every mode above 0 dithers the result, zw = the source texture's size in texels
struct Crop { float4 rect; float4 edge; float4 post; };
// Catmull-Rom through nine bilinear taps (a magnified or 1:1 picture), clamped to the valid source rectangle
static float3 catmull(texture2d<float> t, sampler s, float2 uv, float2 size, float4 edge) {
    float2 pos = uv * size, c1 = floor(pos - 0.5) + 0.5, f = pos - c1;
    float2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f)), w1 = 1.0 + f * f * (-2.5 + 1.5 * f), w2 = f * (0.5 + f * (2.0 - 1.5 * f)), w3 = f * f * (-0.5 + 0.5 * f);
    float2 w12 = w1 + w2, o12 = w2 / w12, t0 = (c1 - 1.0) / size, t3 = (c1 + 2.0) / size, t12 = (c1 + o12) / size;
    #define TAP(x, y) t.sample(s, clamp(float2(x, y), edge.xy, edge.zw)).rgb
    float3 r = TAP(t0.x, t0.y) * w0.x * w0.y + TAP(t12.x, t0.y) * w12.x * w0.y + TAP(t3.x, t0.y) * w3.x * w0.y
             + TAP(t0.x, t12.y) * w0.x * w12.y + TAP(t12.x, t12.y) * w12.x * w12.y + TAP(t3.x, t12.y) * w3.x * w12.y
             + TAP(t0.x, t3.y) * w0.x * w3.y + TAP(t12.x, t3.y) * w12.x * w3.y + TAP(t3.x, t3.y) * w3.x * w3.y;
    #undef TAP
    return max(r, 0.0);
}
// Lanczos-3 through 36 point-like bilinear taps (a magnified or 1:1 picture)
static float lanczos3(float x) { x = fabs(x); if (x < 1e-4) return 1.0; if (x >= 3.0) return 0.0; float px = 3.14159265 * x; return 3.0 * sin(px) * sin(px / 3.0) / (px * px); }
static float3 lanczos(texture2d<float> t, sampler s, float2 uv, float2 size, float4 edge) {
    float2 pos = uv * size, c = floor(pos - 0.5) + 0.5, f = pos - c;
    float3 sum = 0; float wsum = 0;
    for (int j = -2; j <= 3; j++) { float wy = lanczos3(float(j) - f.y);
        for (int i = -2; i <= 3; i++) { float w = lanczos3(float(i) - f.x) * wy;
            sum += w * t.sample(s, clamp((c + float2(i, j)) / size, edge.xy, edge.zw)).rgb; wsum += w; } }
    return max(sum / wsum, 0.0);
}
// A minified picture: the average of n x n bilinear taps over the output pixel's footprint (a box filter, no aliasing)
static float3 footprint(texture2d<float> t, sampler s, float2 uv, float2 dx, float2 dy, float n, float4 edge) {
    float3 sum = 0; int k = int(n);
    for (int j = 0; j < k; j++) for (int i = 0; i < k; i++) {
        float2 o = (float2(i, j) + 0.5) / n - 0.5;
        sum += t.sample(s, clamp(uv + dx * o.x + dy * o.y, edge.xy, edge.zw)).rgb;
    }
    return sum / float(k * k);
}
fragment float4 fs(V in [[stage_in]], texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], constant Crop& c [[buffer(0)]]) {
    float2 uv = in.uv * c.rect.zw + c.rect.xy;
    if (c.post.y < 0.5) return t.sample(s, clamp(uv, c.edge.xy, c.edge.zw));
    float2 size = c.post.zw, dx = dfdx(uv), dy = dfdy(uv);
    float foot = max(length(dx * size), length(dy * size));   // source texels per output pixel
    float3 col;
    if (foot > 1.25) col = footprint(t, s, uv, dx, dy, min(ceil(foot * 1.5), 6.0), c.edge);
    else col = c.post.y > 2.5 ? lanczos(t, s, uv, size, c.edge) : catmull(t, s, uv, size, c.edge);
    if (c.post.y > 1.5 && c.post.x > 0) {
        // Contrast adaptive sharpening (FidelityFX CAS, cross pattern) at one output pixel's distance
        float3 a = t.sample(s, clamp(uv - dy, c.edge.xy, c.edge.zw)).rgb, b = t.sample(s, clamp(uv - dx, c.edge.xy, c.edge.zw)).rgb;
        float3 d = t.sample(s, clamp(uv + dx, c.edge.xy, c.edge.zw)).rgb, e = t.sample(s, clamp(uv + dy, c.edge.xy, c.edge.zw)).rgb;
        float3 mn = min(min(min(a, b), min(d, e)), col), mx = max(max(max(a, b), max(d, e)), col);
        float3 amp = sqrt(saturate(min(mn, 1.0 - mx) / max(mx, 1e-4)));
        float peak = -1.0 / mix(8.0, 5.0, c.post.x);
        float3 w = amp * peak;
        col = saturate((col + w * (a + b + d + e)) / (1.0 + 4.0 * w));
    }
    // Triangular dithering of one output level (interleaved gradient noise): hides the banding of 8-bit gradients
    float2 pp = in.p.xy; float n1 = fract(52.9829189 * fract(dot(pp, float2(0.06711056, 0.00583715)))), n2 = fract(52.9829189 * fract(dot(pp + 17.0, float2(0.06711056, 0.00583715))));
    col = saturate(col + (n1 + n2 - 1.0) / 255.0);
    return float4(col, 1.0);
}
