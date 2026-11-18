// Astral Chain optional ambient occlusion (dm/games/01007300020FA000/graphics_runtime.inc): native Metal kernels, compiled offline with the host (host_msl.py).
// Inverse-projection depth reconstruction layout follows captainj-sparrow/astral-chain-pc-recomp (MIT, Copyright (c) 2026 Valiantsin Dzerakh); the shaders themselves are native.
#include <metal_stdlib>
using namespace metal;
struct Params { float4 iz, iw, ndc, size, radius, world[3], fog, glow, sun, prev[3], inv_t, tmp, ssr; };   // prev: the previous frame's view rows (with translation); inv_t.xyz: the camera's world position; tmp.x: this frame's sample rotation, tmp.y: history blend (0 = no history), tmp.z: debug, tmp.w: reflection strength (0 off), ssr.x: reflection ray steps, ssr.y: 1 when the sun shadow mask is bound, ssr.z: 1 when the motion buffer is bound, ssr.w: unused   // radius.w: contact shadow steps (0 off); sun.xyz: view-space direction to the light, sun.w: contact shadow strength
float3 point_at(float2 uv, float d, constant Params &p) {
    float4 n = float4(uv.x*2-1,1-uv.y*2,p.size.z > 0.5 ? d*2-1 : d,1);
    float z = dot(p.iz,n)/dot(p.iw,n);
    return float3(z*(n.x*p.ndc.x+p.ndc.y),z*(n.y*p.ndc.z+p.ndc.w),z);
}
// Screen-space reflection of the lit scene on horizontal surfaces seen at a grazing angle (Fresnel), where even rough asphalt shows a sheen: a ray from the surface along the mirror
// direction marched against the depth buffer, the hit's scene light weighted by Fresnel and screen-edge fade. The game has no material target, so nothing else is known about
// the surface; the strength is deliberately modest (p.tmp.w)
static float4 ssr_color(uint2 q, float3 pos, float3 N, depth2d<float,access::read> depth, texture2d<float,access::read> light, constant Params &p, float steps) {
    float3 wN=float3(dot(p.world[0].xyz,N),dot(p.world[1].xyz,N),dot(p.world[2].xyz,N));
    if(wN.y<0.85) return float4(0);   // horizontal, facing up (the world has Y up)
    float3 V=-normalize(pos); float cosv=saturate(dot(N,V));
    float F=0.04+0.96*pow(1-cosv,5.0); if(F<0.08) return float4(0);
    float3 R=reflect(-V,N);
    float jitter=fract(sin(dot(float2(q&3),float2(12.9898,78.233)))*43758.5453);   // a fixed pattern: a jitter that changed every frame flickered
    for(float i=0;i<steps;i+=1) {
        float tt=0.15*pow(260.0,(i+jitter)/steps);   // 0.15 to 40 view units, exponential
        float3 qv=pos+R*tt; if(abs(qv.z)<0.05) return float4(0,0,0,1);
        float nx=(qv.x/qv.z-p.ndc.y)/p.ndc.x, ny=(qv.y/qv.z-p.ndc.w)/p.ndc.z; float2 suv=float2(nx*0.5+0.5,0.5-ny*0.5);
        if(any(suv<0)||any(suv>=1)) return float4(0,0,0,1);   // w: 1 = the ray left the screen
        uint2 at=uint2(suv*p.size.xy); float zd=depth.read(at); if(zd>=.999999) continue;
        float diff=abs(qv.z)-abs(point_at(suv,zd,p).z);
        if(diff>0.02+0.01*tt && diff<0.4+0.08*tt) {
            float2 e=min(suv,1-suv); float fade=saturate(min(e.x,e.y)*8);
            // The surface's roughness is unknown: a small blur around the hit, wider with the ray's length, keeps a sharp mirror from striping rough asphalt
            int rad=int(clamp(float(p.size.y)/1080.0*(2.0+0.12*tt),2.0,10.0)); float3 c=0; int2 hi=int2(at); int2 mx=int2(p.size.xy)-1;
            const int2 o[5]={int2(0,0),int2(1,0),int2(-1,0),int2(0,1),int2(0,-1)};
            for(int k=0;k<5;k++) c+=min(light.read(uint2(clamp(hi+o[k]*rad,int2(0),mx))).rgb,float3(6.0));
            return float4(c*0.2*F*fade*p.tmp.w,3);   // w: 3 = a hit on screen
        }
    }
    return float4(0,0,0,2);   // w: 2 = no hit in the steps (the sky, or a surface that never crossed the ray)
}
kernel void ao(depth2d<float,access::read> depth [[texture(0)]], texture2d<float,access::write> out [[texture(1)]], texture2d<float,access::read> light [[texture(2)]], texture2d<float,access::write> bounce_out [[texture(3)]], texture2d<float,access::read> hist [[texture(4)]], texture2d<float,access::read> hist_b [[texture(5)]], texture2d<float,access::read> motion [[texture(6)]], texture2d<float,access::read> sunmask [[texture(7)]], texture2d<float,access::read> hist_s [[texture(8)]], texture2d<float,access::write> ssr_out [[texture(9)]], constant Params &p [[buffer(0)]], uint2 q [[thread_position_in_grid]]) {
    if (q.x>=out.get_width() || q.y>=out.get_height()) return;
    uint2 full=uint2(p.size.xy), xy=min(q*2,full-1); float d=depth.read(xy);
    if(d>=0.999999) { out.write(float4(1,1,1,0),q); bounce_out.write(float4(0),q); ssr_out.write(float4(0),q); return; }
    float2 uv=(float2(xy)+0.5)/p.size.xy; float3 pos=point_at(uv,d,p);
    uint2 lx=uint2(max(int(xy.x)-1,0),xy.y),rx=min(xy+uint2(1,0),full-1);
    uint2 ty=uint2(xy.x,max(int(xy.y)-1,0)),by=min(xy+uint2(0,1),full-1);
    float3 l=point_at((float2(lx)+.5)/p.size.xy,depth.read(lx),p),r=point_at((float2(rx)+.5)/p.size.xy,depth.read(rx),p);
    float3 t=point_at((float2(ty)+.5)/p.size.xy,depth.read(ty),p),b=point_at((float2(by)+.5)/p.size.xy,depth.read(by),p);
    float3 dx=abs(l.z-pos.z)<abs(r.z-pos.z)?pos-l:r-pos,dy=abs(t.z-pos.z)<abs(b.z-pos.z)?t-pos:pos-b;
    float3 cn=cross(dx,dy); float3 N=dot(cn,cn)>1e-12?normalize(cn):normalize(-pos); if(dot(N,pos)>0) N=-N;
    float projected=min(p.radius.y/max(abs(pos.z),.01),p.size.y*.25), sum=0; float3 bsum=0;
    float rotate=fract(sin(dot(float2(q&3),float2(12.9898,78.233)))*43758.5453)*6.2831853+p.tmp.x;
    uint count=uint(p.size.w);
    for(uint i=0;i<count;i++) {
        float a=rotate+float(i)*2.39996323, f=sqrt((float(i)+.5)/count);
        float2 delta=float2(cos(a)*p.radius.z,sin(a))*projected*f;
        int2 at=int2(round(float2(xy)+delta)); if(any(at<0)||any(at>=int2(full))) continue;
        float zd=depth.read(uint2(at)); if(zd>=.999999) continue;
        float3 v=point_at((float2(at)+.5)/p.size.xy,zd,p)-pos;
        float dist2=dot(v,v), penalized=dist2+4*v.z*v.z;
        float horizon=max(dot(N,v)*rsqrt(max(dist2,1e-6))-.08,0.0);
        float occ=horizon*max(1-penalized/(p.radius.x*p.radius.x),0.0); sum+=occ;
        // Screen-space bounce (DM_AC_GI): the lit radiance of the surfaces that occlude this point, capped so a flame does not blow out its neighbours.
        if(p.glow.z>0) bsum+=min(light.read(uint2(at)).rgb,float3(2.5))*occ;
    }
    float visibility=pow(saturate(1-2*sum/count),1.5);
    // Multibounce approximation, albedo .3, softens closed contacts.
    float a=2.0404*.3-.3324,bm=-4.7951*.3+.6417,c=2.7552*.3+.6903;
    visibility=max(visibility,((visibility*a+bm)*visibility+c)*visibility);
    visibility=mix(1.0,visibility,saturate((120-length(pos))/60));
    // The game's sun shadow mask (white = not in a dynamic shadow; it is white under bridges too, so it says nothing about ambient-only areas and does not touch the occlusion)
    float lit=p.ssr.y>.5?sunmask.read(xy).r:1.0;
    if(p.tmp.z>1.5) visibility=p.ssr.y>.5?lit:0.5;   // DM_AC_AODBG=2: the sun shadow mask itself
    if(p.tmp.z>2.5) visibility=p.ssr.z>.5?saturate(0.5+motion.read(xy).r-0.5+0.0):0.5;   // DM_AC_AODBG=3: the motion buffer's red channel
    // Contact shadows: a short screen-space ray from the surface toward the sun, against the depth buffer; the per-pixel jitter is averaged by the apply pass's filter.
    float contact=1;
    if(p.radius.w>0 && p.sun.w>0) {
        float facing=dot(N,p.sun.xyz);
        if(facing>0.05) {
            float steps=p.radius.w, jitter=(rotate-p.tmp.x)*0.15915494, hit=0;   // a fixed per-pixel pattern: a jitter that changed every frame flickered
            for(float i=0;i<steps;i+=1) {
                float t=(i+jitter)/steps; float3 qv=pos+N*(0.01+0.002*abs(pos.z))+p.sun.xyz*(0.04+t*t*0.7);
                if(abs(qv.z)<0.05) break;
                float nx=(qv.x/qv.z-p.ndc.y)/p.ndc.x, ny=(qv.y/qv.z-p.ndc.w)/p.ndc.z;
                float2 suv=float2(nx*0.5+0.5,0.5-ny*0.5); if(any(suv<0)||any(suv>=1)) break;
                uint2 at=uint2(suv*p.size.xy); float zd=depth.read(at); if(zd>=.999999) continue;
                float diff=abs(qv.z)-abs(point_at(suv,zd,p).z);
                if(diff>0.01+0.004*abs(qv.z) && diff<0.6) { hit=1; break; }
            }
            contact=1-hit*smoothstep(0.05,0.3,facing)*lit;   // already in a dynamic shadow: nothing to add
        }
    }
    float4 sr=p.tmp.w>0?ssr_color(xy,pos,N,depth,light,p,p.ssr.x>0?p.ssr.x:16.0):float4(0); float3 ssrc=sr.rgb;
    if(p.tmp.z>5.5&&p.tmp.z<6.5) visibility=sr.w/3.0;   // DM_AC_AODBG=6: the reflection ray's outcome (0 not eligible, 1/3 left the screen, 2/3 no hit, 1 hit)
    float3 bounce=bsum*(2*p.glow.z/float(count))*mix(1.0,0.0,saturate((length(pos)-60)/60));
    // Temporal accumulation: the previous frame's result at this surface point (camera reprojection, bilinear, rejected where the depth differs), blended in.
    if(p.tmp.y>0) {
        float3 world=float3(dot(p.world[0].xyz,pos),dot(p.world[1].xyz,pos),dot(p.world[2].xyz,pos))+p.inv_t.xyz;
        float3 pv=float3(dot(p.prev[0].xyz,world)+p.prev[0].w,dot(p.prev[1].xyz,world)+p.prev[1].w,dot(p.prev[2].xyz,world)+p.prev[2].w);
        // The game's motion buffer (0.5, 0.5 = none): history is trusted less where something moves
        float mvdev=0; if(p.ssr.z>.5) { float2 m=motion.read(xy).rg-0.5; mvdev=max(abs(m.x),abs(m.y))*255.0; }
        float blend=p.tmp.y*(1.0-saturate((mvdev-1.5)/6.0));
        if(abs(pv.z)>0.05) {
            float nx=(pv.x/pv.z-p.ndc.y)/p.ndc.x, ny=(pv.y/pv.z-p.ndc.w)/p.ndc.z; float2 huv=float2(nx*0.5+0.5,0.5-ny*0.5);
            if(all(huv>=0)&&all(huv<1)) {
                int2 hs=int2(hist.get_width(),hist.get_height()); float2 hp=huv*float2(hs)-0.5; int2 h0=int2(floor(hp)); float2 fr=hp-float2(h0);
                float4 acc=0; float3 bacc=0,sacc=0; float ws=0;
                for(int j=0;j<2;j++) for(int i=0;i<2;i++) {
                    int2 at=clamp(h0+int2(i,j),int2(0),hs-1); float4 hv=hist.read(uint2(at));
                    float w=(i?fr.x:1-fr.x)*(j?fr.y:1-fr.y)*(abs(abs(hv.w)-abs(pv.z))<0.03*abs(pv.z)+0.04?1.0:0.0);
                    acc+=hv*w; bacc+=hist_b.read(uint2(at)).rgb*w; sacc+=hist_s.read(uint2(at)).rgb*w; ws+=w;
                }
                if(ws>0.5) { float4 hv=acc/ws; visibility=mix(visibility,hv.x,blend); contact=mix(contact,hv.y,blend); bounce=mix(bounce,bacc/ws,1.0-(1.0-blend)*0.5); ssrc=mix(ssrc,sacc/ws,1.0-(1.0-blend)*0.5); }   // reflections accumulate longer: the flames they show flicker
            }
        }
    }
    out.write(float4(visibility,contact,visibility,pos.z),q);
    bounce_out.write(float4(bounce,1),q);
    ssr_out.write(float4(ssrc,1),q);
}
struct V { float4 position [[position]]; float2 uv; };
vertex V ao_vs(uint id [[vertex_id]]) { float2 uv=float2((id<<1)&2,id&2); return {float4(uv*float2(2,-2)+float2(-1,1),0,1),uv}; }
struct Resolved { float k; float3 share; float3 bounce; float3 ssr; float3 c; float alpha; bool sky; };
Resolved resolve(V v, texture2d<float,access::read> ao_tex, depth2d<float,access::read> depth, texture2d<float,access::read> light, texturecube<float> fog_tex, texture2d<float,access::read> bounce_tex, texture2d<float,access::read> ssr_tex, constant Params &p) {
    Resolved r; r.ssr=0; r.k=1; r.share=0; r.bounce=0; r.sky=false;
    uint2 full=uint2(p.size.xy), q=min(uint2(v.uv*p.size.xy),full-1); float d=depth.read(q);
    float4 lc=light.read(q); r.c=lc.rgb; r.alpha=lc.a;
    if(d>=.999999) { r.sky=true; return r; }
    float3 pos=point_at((float2(q)+.5)/p.size.xy,d,p); float sum=0,weights=0,csum=0; float3 bsum=0,ssum=0;
    int2 size=int2(ao_tex.get_width(),ao_tex.get_height()), base=int2(q/2);
    for(int y=-1;y<=1;y++) for(int x=-1;x<=1;x++) {
        int2 at=clamp(base+int2(x,y),int2(0),size-1); float4 s=ao_tex.read(uint2(at));
        float weight=exp(-abs(s.w-pos.z)*8)*exp(-float(x*x+y*y)*.5); sum+=s.x*weight; csum+=s.y*weight; weights+=weight;
        if(p.glow.z>0) bsum+=bounce_tex.read(uint2(at)).rgb*weight;
        if(p.tmp.w>0) ssum+=ssr_tex.read(uint2(at)).rgb*weight;
    }
    r.k=weights>1e-5?sum/weights:1; if(p.sun.w>0&&weights>1e-5) r.k*=mix(1.0,csum/weights,p.sun.w); float f=0; float3 fog_color=0, c=r.c;
    if(p.glow.w>.5) {
        float3 world=float3(dot(p.world[0].xyz,pos),dot(p.world[1].xyz,pos),dot(p.world[2].xyz,pos));
        constexpr sampler linear(coord::normalized,filter::linear,mip_filter::linear,address::clamp_to_edge);
        float4 cube=fog_tex.sample(linear,world,level(0)); fog_color=cube.rgb*p.fog.w;
        f=saturate(pow(saturate((length(pos)-p.fog.x)*p.fog.y),p.fog.z)*cube.a);
        float3 surface=max(c-f*fog_color,0.0)/max(1-f,1e-6); float bright=saturate(dot(surface,float3(.2989,.587,.114))-p.glow.x);
        f=saturate(f*(1+bright*(p.glow.y-1)));
    }
    r.share=saturate(max(c-f*fog_color,0.0)/max(c,1e-6));
    // Emissive light should retain its glow even without a fog block.
    r.share*=1-saturate((max(c.r,max(c.g,c.b))-6)/18);
    r.bounce=weights>1e-5?bsum/weights:float3(0); r.ssr=weights>1e-5?ssum/weights:float3(0);
    return r;
}
// Occlusion only: multiplied into the scene light by the blend unit.
fragment float4 ao_apply(V v [[stage_in]], texture2d<float,access::read> ao_tex [[texture(0)]], depth2d<float,access::read> depth [[texture(1)]], texture2d<float,access::read> light [[texture(2)]], texturecube<float> fog_tex [[texture(3)]], texture2d<float,access::read> bounce_tex [[texture(4)]], texture2d<float,access::read> ssr_tex [[texture(5)]], constant Params &p [[buffer(0)]]) {
    Resolved r=resolve(v,ao_tex,depth,light,fog_tex,bounce_tex,ssr_tex,p);
    if(r.sky) return 1;
    if(p.tmp.z>5.5&&p.tmp.z<6.5) { float c=r.k*3; return float4(abs(c-1)<.5?1:0,abs(c-3)<.5?1:0,abs(c-2)<.5?1:0,1); }   // DM_AC_AODBG=6: red = left the screen, green = hit, blue = no hit, black = not eligible
    if(p.tmp.z>.5) return float4(r.k,r.k,r.k,1);   // DM_AC_AODBG: the occlusion factor itself
    return float4(1-(1-r.k)*r.share,1);
}
// Occlusion plus bounce light: writes the whole colour (no blending), reading the copy of the scene light.
fragment float4 ao_apply_gi(V v [[stage_in]], texture2d<float,access::read> ao_tex [[texture(0)]], depth2d<float,access::read> depth [[texture(1)]], texture2d<float,access::read> light [[texture(2)]], texturecube<float> fog_tex [[texture(3)]], texture2d<float,access::read> bounce_tex [[texture(4)]], texture2d<float,access::read> ssr_tex [[texture(5)]], constant Params &p [[buffer(0)]]) {
    Resolved r=resolve(v,ao_tex,depth,light,fog_tex,bounce_tex,ssr_tex,p);
    if(r.sky) return float4(r.c,r.alpha);
    if(p.tmp.z>5.5&&p.tmp.z<6.5) { float c=r.k*3; return float4(abs(c-1)<.5?1:0,abs(c-3)<.5?1:0,abs(c-2)<.5?1:0,1); }   // DM_AC_AODBG=6: red = left the screen, green = hit, blue = no hit, black = not eligible
    if(p.tmp.z>.5) return float4(r.k,r.k,r.k,1);
    float3 col=r.c*(1-(1-r.k)*r.share)+r.bounce*r.share*0.35;
    col+=r.ssr;
    return float4(col,r.alpha);
}
