#!/usr/bin/env python3
"""ASTRAL CHAIN 1.0.1 experiment: a boolean field (default ShadowCast) 0 -> 1 in the ObjectParam.bxm of chosen DATs, inside a CLONE of the RomFS image (never the original).

The RomFS image is a DMROMFS1 file (dm/tools/romfs.py); its PKZ archives hold ZStandard-compressed PlatinumGames DAT containers, whose ObjectParam.bxm (binary XML) names a
ShadowCast per object. The BXM string pool is shared, so the value text is not flipped: the data entry's value offset is pointed at a pool string "1". The DAT is recompressed
(level 3 to 22, the smallest that fits) into its slot, and the entry table's stored length is updated; a larger result than the slot is skipped.
Make the clone with `cp -c` (APFS clone, no space until written), then run: astral_romfs_shadowcast.py <clone> '/bg/bg.pkz:*,/ba/ba.pkz:*' [field] and start the game with DM_ROMFS=<clone>.
Result (2026-11-18): the game loads the patched image; the shadow pass of a Highway Rescue frame grew from 49 to 76 draws, with no visible gain in the scene. Not wired into the build.
"""
import sys,struct,zstandard
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import romfs
img=sys.argv[1]; targets=sys.argv[2].split(','); FIELD=sys.argv[3] if len(sys.argv)>3 else 'ShadowCast'   # any boolean field of ObjectParam.bxm, e.g. DynamicCubeMapMember
I=romfs.Image(img); dctx=zstandard.ZstdDecompressor()
def members_rng(d):
    n,ot,et,nt,st=struct.unpack_from('<5I',d,4)
    offs=struct.unpack_from(f'<{n}I',d,ot); sizes=struct.unpack_from(f'<{n}I',d,st); w=struct.unpack_from('<I',d,nt)[0]
    names=[d[nt+4+w*i:nt+4+w*(i+1)].split(b'\0')[0].decode(errors='replace') for i in range(n)]
    return list(zip(names,offs,sizes))
def patch_bxm(d,o,sz):
    b=memoryview(d)[o:o+sz]
    assert bytes(b[:4]) in (b'XML\0',b'BXM\0')
    nc,dc,ds=struct.unpack_from('>HHI',b,8); to=16+8*nc; pool=to+4*dc
    def s(off):
        if off==0xffff: return ''
        return bytes(b[pool+off:pool+off+64]).split(b'\0')[0].decode(errors='replace')
    ents=[struct.unpack_from('>2H',b,to+4*i) for i in range(dc)]
    one=[v for n,v in ents if v!=0xffff and s(v)=='1']
    if not one: return 0,'no "1" string'
    cnt=0
    for i,(n,v) in enumerate(ents):
        if s(n)==FIELD and s(v)=='0':
            struct.pack_into('>2H',b,to+4*i,n,one[0]); cnt+=1
    return cnt,''
log=[]
with open(img,'r+b') as f:
    for t in targets:
        pk,dat=t.split(':')
        k=I.find(pk); base=I.entry(k)[0]
        f.seek(base); h=f.read(0x20); ver,_,n,eo,nl=struct.unpack_from('<IQIII',h,4)
        f.seek(base+eo); tab=f.read(0x20*n+nl)
        names=lambda o:tab[0x20*n+o:tab.index(b'\0',0x20*n+o)].decode()
        recs=[struct.unpack_from('<IIQQQ',tab,0x20*i) for i in range(n)]
        order=sorted(range(n),key=lambda i:recs[i][3])
        pos={i:j for j,i in enumerate(order)}
        for i,(a,c,usz,off,csz) in enumerate(recs):
            nm=names(a)
            if not nm.endswith('.dat'): continue
            if dat!='*' and nm!=dat: continue
            comp=names(c)
            if comp!='ZStandard': continue
            f.seek(base+off); raw=f.read(csz)
            try: d=bytearray(dctx.decompress(raw,max_output_size=usz))
            except Exception as e: continue
            if d[:4]!=b'DAT\0': continue
            m=[x for x in members_rng(bytes(d)) if x[0]=='ObjectParam.bxm']
            if not m: continue
            cnt,why=patch_bxm(d,m[0][1],m[0][2])
            if not cnt: log.append((pk,nm,'skip',why or 'no %s 0' % FIELD)); continue
            j=pos[i]; nxt=recs[order[j+1]][3] if j+1<n else (struct.unpack_from('<Q',h,8)[0])
            cap=nxt-off
            best=None
            for lvl in (3,9,15,19,22):
                out=zstandard.ZstdCompressor(level=lvl,write_content_size=True).compress(bytes(d))
                if best is None or len(out)<len(best): best=out
                if len(best)<=csz: break
            if len(best)>cap: log.append((pk,nm,'skip',f'recompressed {len(best)} > slot {cap}')); continue
            f.seek(base+off); f.write(best+b'\0'*(csz-len(best)) if len(best)<csz else best)
            # keep the tail of the old stored bytes zero when shorter; update stored length
            f.seek(base+eo+0x20*i+24); f.write(struct.pack('<Q',len(best)))
            log.append((pk,nm,'patched',f'{cnt} value(s), stored {csz} -> {len(best)} (slot {cap})'))
for l in log: print(*l)
print('patched',sum(1 for l in log if l[2]=='patched'),'skipped',sum(1 for l in log if l[2]=='skip'))
