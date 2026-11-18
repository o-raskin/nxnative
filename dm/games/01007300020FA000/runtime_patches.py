#!/usr/bin/env python3
"""Build-gated fixed render sizes for ASTRAL CHAIN 1.0.1 on the Mac.

The display, backing targets and all three scene levels change together.
Site discovery reference: Puddz/AstralChain-PC resolution-1.0.1.pchtxt at
6b2d624dd6451f9481013fc3a6ccbcd3ba5f1a7a (MIT); instructions checked
against this game's NSO. No foreign runtime or SVC patches are imported.
"""
from pathlib import Path
import importlib.util
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import nso
from nso_asm import B
from runtime_patch import layout, manifest

BUILD = '4b159f0f7a360669738390ee8657b4f0' + '0' * 32
SIZES = (('native', 1600, 900), ('1080p', 1920, 1080),
         ('1440p', 2560, 1440), ('2160p', 3840, 2160), ('2880p', 5120, 2880))


def mov(reg, value, shift=0):
    if not 0 <= value <= 65535 or shift not in (0, 16):
        raise ValueError('MOVZ immediate does not fit')
    return struct.pack('<I', 0x52800000 | ((shift // 16) << 21) | (value << 5) | reg)


def generate(module, image, fixups):
    writes = []
    for choice, width, height in SIZES:
        # Explicit resolution overrides console mode. Both display getters and
        # both resource constructors receive the same canvas in either mode.
        for off, before, reg, value in (
            (0x4328c0, '08c88052', 8, width), (0x4328c8, '88708052', 8, height),
            (0x4328e0, '08a08052', 8, width), (0x4328e8, '085a8052', 8, height),
            (0x40d5e8, '3301881a', 19, width), (0x40d5f4, '3401881a', 20, height),
            (0x40fb0c, '3301881a', 19, width), (0x40fb18, '3401881a', 20, height),
        ):
            writes.append((choice, off, bytes.fromhex(before), mov(reg, value)))
        # The fixed 310 MiB render-target arena is sized for 1600x900. Reserve
        # its pixel-proportional capacity, rounded up to 64 KiB (MOVZ encoding).
        # The parent heap is independent: high modes need DM_APP_POOL=10G.
        pool = ((310 * 2**20 * width * height + 1600 * 900 * 65536 - 1)
                // (1600 * 900 * 65536)) * 65536
        writes.append((choice, 0x40e0b0, bytes.fromhex('086ca252'), mov(8, pool >> 16, 16)))
        # The GRAPHIC BUFFER heap (143 MiB, inside the 173.375 MiB BUFFER ROOT) holds the constant buffers and one storage
        # buffer of 6.97 bytes per pixel of the render size (research: astral-chain-pc-recomp patches-v101.txt, 575a30 /
        # 575c94). At 5K that buffer alone needs 103 MiB, so the heap fills and the load of Highway Rescue never completes.
        # Both sizes grow 8 bytes per pixel above 1080p, in whole MiB (MOVZ keeps them 64 KiB aligned).
        extra = max(0, ((width * height - 1920 * 1080) * 8 + 0xfffff) & ~0xfffff)
        if extra:
            writes.append((choice, 0x575a30, bytes.fromhex('c15aa152'), mov(1, (0xad60000 + extra) >> 16, 16)))
            writes.append((choice, 0x575c94, bytes.fromhex('011ea152'), mov(1, (0x8f00000 + extra) >> 16, 16)))
        # A 256-float exposure scratch buffer and its single 256-thread final
        # reduction cannot accept more than 256 partial sums. Preserve the
        # original path when it fits; otherwise use the next existing image
        # in the downsample chain, with matching uniforms and dispatch sizes.
        if ((width >> 4) + 7) // 8 * (((height >> 4) + 7) // 8) > 256:
            profile = load_stubs()
            stub = checked_stub(image, fixups, 'AC_LUMA_REDUCE', profile.luma_reduce_words)
            if ((width >> 5) + 7) // 8 * (((height >> 5) + 7) // 8) > 256:
                raise ValueError('exposure reduction exceeds the existing 256-value algorithm')
            writes.append((choice, 0x3ffbf8, bytes.fromhex('e00313aa'), struct.pack('<I', B(0x3ffbf8, stub))))
            writes.append((choice, 0x4066a0, bytes.fromhex('16010291'), bytes.fromhex('16810291')))
        # These blocks only select sizes for SetResolutionLevel(index,w,h).
        # Every level uses the chosen size; no dormant smaller family can later
        # reinterpret its backing storage at another resolution (pause/reload).
        for off, before in (
            (0x40f184, '1f001971887080520100931a0201941a'),
            (0x40f1a4, 'e803163209b480521f001971d44e8052566580522101881ac202941a'),
            (0x40f1d0, '1f001971086480526102881ac202941a'),
        ):
            original = bytes.fromhex(before)
            after = mov(1, width) + mov(2, height) + bytes.fromhex('1f2003d5') * (len(original) // 4 - 2)
            writes.append((choice, off, original, after))
    # Off fixes all three levels at the maximum. On gives the native selector
    # three real target families, at 100/90/80 percent per axis. The backing
    # arena remains sized for the maximum, and every level fits its own targets.
    fixed = list(writes)
    for choice, width, height in SIZES:
        for value, off, before, after in fixed:
            if value != choice:
                continue
            if off in (0x40f184, 0x40f1a4, 0x40f1d0):
                scale = {0x40f184: 10, 0x40f1a4: 9, 0x40f1d0: 8}[off]
                # Retain the game's exact 16:9 32x18-pixel allocation grid.
                units = width * scale // 320
                after = mov(1, units * 32) + mov(2, units * 18) + after[8:]
            writes.append((choice + '_1', off, before, after))
    return manifest(module, image, fixups, BUILD, 'DM_AC_RESOLUTION', writes,
                    variant='DM_DYNAMIC_RESOLUTION')


def load_stubs():
    spec = importlib.util.spec_from_file_location('astral_stubs', Path(__file__).with_name('patches.py'))
    assert spec is not None and spec.loader is not None
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    return profile


def checked_stub(image, fixups, name, words):
    stub = int(fixups['RUNTIME_' + name], 0)
    patch_off = int(fixups['PATCH_OFF'], 0)
    file_off = (int(fixups['FILE_IMAGE_LEN'], 0) + stub - patch_off) if patch_off < 0 else stub
    expected = b''.join(struct.pack('<I', w) for w in words(stub))
    if file_off < 0 or image[file_off:file_off + len(expected)] != expected:
        raise ValueError('quality helper does not match the rewritten image')
    return stub


def generate_shadow(module, image, fixups):
    profile = load_stubs()
    writes = []
    for choice, name, atlas, shift in (('high', 'AC_SHADOW_HIGH', 4096, 11),
                                        ('ultra', 'AC_SHADOW_ULTRA', 8192, 12)):
        stub = checked_stub(image, fixups, name, lambda start, atlas=atlas: profile.shadow_pool_words(
            start, (atlas * atlas - 2048 * 2048) * 4))
        tile = atlas // 2
        edits = (
            (0x40e0b4, 'e84700f9', struct.pack('<I', B(0x40e0b4, stub))),
            (0x40e1ec, 'e8031532', mov(8, atlas)),
            (0x401fa8, 'e3031632', mov(3, tile)),
            (0x401fac, 'e4031632', mov(4, tile)),
            (0x401fb0, '01011653', struct.pack('<I', 0x53000000 | ((32 - shift) << 16) | (8 << 5) | 1)),
            (0x401fb4, '08591753', struct.pack('<I', 0x53000000 | ((33 - shift) << 16) | ((32 - shift) << 10) | (8 << 5) | 8)),
            (0x401fb8, '02011612', struct.pack('<I', 0x12000000 | ((32 - shift) << 16) | (8 << 5) | 2)),
        )
        writes.extend((choice, off, bytes.fromhex(before), after) for off, before, after in edits)
    return manifest(module, image, fixups, BUILD, 'DM_AC_SHADOW', writes)


def generate_detail(module, image, fixups, variable):
    profile = load_stubs()
    writes = []
    for choice, factor in (('x2', 0.5), ('x4', 0.25), ('high', 0.0)):
        for site, original, source, slot in profile.DETAIL_SITES:
            if (slot == 3) != (variable == 'DM_AC_DRAW_DISTANCE'):
                continue
            stub = checked_stub(image, fixups, f'AC_DETAIL_{site:X}_{choice.upper()}',
                                lambda start, site=site, source=source, slot=slot, factor=factor:
                                profile.detail_words(start, site, source, slot, factor))
            writes.append((choice, site, bytes.fromhex(original), struct.pack('<I', B(site, stub))))
    return manifest(module, image, fixups, BUILD, variable, writes)


def generate_range(module, image, fixups):
    """Shadow range: the cascade split distances (view distance in metres; here 11, 30, 150, 200, the area's data) are copied into the array main+0xd6faf0 that the
    cascade fit (main+0x420a00) reads, by the 14 instructions from main+0x420a34. A stub (patches.py range_words) does the copy scaled by 1.5, 2, 3 or 4, and the
    manifest branches to it. Each cascade's orthographic box fits the camera frustum slice between two splits, so every cascade grows by the factor."""
    profile = load_stubs()
    writes = []
    for choice, imm8 in profile.RANGE_CHOICES:
        stub = checked_stub(image, fixups, f'AC_RANGE_{choice.upper()}', lambda start, imm8=imm8: profile.range_words(start, imm8))
        writes.append((choice, profile.RANGE_SITE, bytes.fromhex(profile.RANGE_ORIGINAL), struct.pack('<I', B(profile.RANGE_SITE, stub))))
    return manifest(module, image, fixups, BUILD, 'DM_AC_SHADOW_RANGE', writes)


UI_SITES = (0x3a2390, 0x40e25c, 0x40e884, 0x40eec4, 0x40eee8, 0x40ef0c, 0x40ef30, 0x9045c8)   # mov w1,#0x500 (+4: mov w2,#0x2d0): the 1280x720 UI targets and the two UI lens sizes


# The interface is drawn into 1280x720 targets and stretched to the scene. Sites: `mov w1,#0x500` followed by `mov w2,#0x2d0` for the two UI lens sizes (callers
# main+0x3a2398 and main+0x9045d4 of the lens setup 0x9a30a0) and for four of the six 1280x720 colour/depth targets created in the render-target setup (main+0x40e2e0..).
# The first two targets of that function (main+0x40e25c and 0x40e884) must stay 1280x720: the minimap is drawn into them (scaling them blanks it). The three targets
# at main+0x40f038, 0x40f070 and 0x40f098 (another creator, main+0x9d89b0) were not touched.
UI_SITES = (0x3a2390, 0x9045c8, 0x40eec4, 0x40eee8, 0x40ef0c, 0x40ef30)


def generate_ui(module, image, fixups):
    """Interface resolution (roadmap item 12, found while looking at menu art): the UI is rendered at the chosen scene size instead of 1280x720. Verified
    at 4K: the HUD keeps its layout, text and icons are sharp, the minimap works (the first two UI targets stay as they are)."""
    writes = []
    for choice, w, h in (('native', 1600, 900), ('1080p', 1920, 1080), ('1440p', 2560, 1440), ('2160p', 3840, 2160), ('2880p', 5120, 2880)):
        for site in UI_SITES:
            for off, old, new in ((site, 0x500, w), (site + 4, 0x2d0, h)):
                before = bytes(module.image[off:off + 4]); word = struct.unpack('<I', before)[0]
                if (word & 0xffe00000) != 0x52800000 or (word >> 5) & 0xffff != old:
                    raise ValueError(f'UI site {off:#x} is not a MOV of {old:#x}')
                writes.append((choice, off, before, struct.pack('<I', 0x52800000 | (new << 5) | (word & 31))))
    return manifest(module, image, fixups, BUILD, 'DM_AC_UI_RES', writes)


def generate_aspect(module, image, fixups):
    profile = load_stubs()
    writes = []
    for site, original, event, before in profile.ASPECT_SITES:
        stub = checked_stub(image, fixups, f'AC_ASPECT_{site:X}',
                            lambda start, site=site, original=original, event=event, before=before:
                            profile.aspect_words(start, site, original, event, before))
        writes.append(('1610', site, bytes.fromhex(original), struct.pack('<I', B(site, stub))))
    for site in (0x403670, 0x403424, 0x403644, 0x403704):
        writes.append(('1610', site, bytes.fromhex('e2031f2a'), mov(2, 1)))
    return manifest(module, image, fixups, BUILD, 'DM_AC_SCREEN_RATIO', writes)


def main(args):
    original, rewritten, out = map(Path, args)
    out.write_text(generate(nso.load(original.read_bytes(), original.name),
                            rewritten.read_bytes(), layout(rewritten.with_name('main.fixups.tsv'))))
    out.with_name('main.shadow.runtime.tsv').write_text(generate_shadow(
        nso.load(original.read_bytes(), original.name), rewritten.read_bytes(),
        layout(rewritten.with_name('main.fixups.tsv'))))
    for suffix, variable in (('lod', 'DM_AC_MODEL_QUALITY'), ('distance', 'DM_AC_DRAW_DISTANCE')):
        out.with_name(f'main.{suffix}.runtime.tsv').write_text(generate_detail(
            nso.load(original.read_bytes(), original.name), rewritten.read_bytes(),
            layout(rewritten.with_name('main.fixups.tsv')), variable))
    out.with_name('main.range.runtime.tsv').write_text(generate_range(
        nso.load(original.read_bytes(), original.name), rewritten.read_bytes(),
        layout(rewritten.with_name('main.fixups.tsv'))))
    out.with_name('main.ui.runtime.tsv').write_text(generate_ui(
        nso.load(original.read_bytes(), original.name), rewritten.read_bytes(),
        layout(rewritten.with_name('main.fixups.tsv'))))
    out.with_name('main.aspect.runtime.tsv').write_text(generate_aspect(
        nso.load(original.read_bytes(), original.name), rewritten.read_bytes(),
        layout(rewritten.with_name('main.fixups.tsv'))))
    print('ASTRAL CHAIN fixed render sizes: native, 1080p, 1440p, 2160p, 2880p; default has zero writes')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (ValueError, KeyError, OSError) as error:
        sys.exit(f'[RED] runtime patches: {error}')
