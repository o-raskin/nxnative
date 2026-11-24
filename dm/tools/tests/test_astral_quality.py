"""Execute the resolution writes against the verified 1.0.1 instruction ABI."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import types
import unittest

try:
    import unicorn as uc
    from unicorn import arm64_const as arm
    from unicorn.unicorn import Uc as Emulator
except ImportError:
    uc = arm = Emulator = None

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('astral_quality', ROOT / 'dm/games/01007300020FA000/runtime_patches.py')
assert spec is not None and spec.loader is not None
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

# Captured original instructions, independent of the generator's tables.
ABI = {
    0x4328c0: '08c88052', 0x4328c8: '88708052',
    0x4328e0: '08a08052', 0x4328e8: '085a8052',
    0x40d5e8: '3301881a', 0x40d5f4: '3401881a',
    0x40fb0c: '3301881a', 0x40fb18: '3401881a',
    0x40e0b0: '086ca252',
    0x575a30: 'c15aa152', 0x575c94: '011ea152',
    0x3ffbf8: 'e00313aa', 0x4066a0: '16010291',
    0x40f184: '1f001971887080520100931a0201941a',
    0x40f1a4: 'e803163209b480521f001971d44e8052566580522101881ac202941a',
    0x40f1d0: '1f001971086480526102881ac202941a',
}


class Manifest(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(0xa0e7d0)
        for off, code in ABI.items():
            self.image[off:off + len(code) // 2] = bytes.fromhex(code)
        self.module = types.SimpleNamespace(build_id=bytes.fromhex(patch.BUILD),
                                            text_end=len(self.image), image=self.image)
        self.fixups = {'BUILD_ID': patch.BUILD[:32], 'TEXT_END': hex(len(self.image)),
                       'PATCH_OFF': '0x800000', 'RUNTIME_AC_LUMA_REDUCE': '0x800000'}
        code = b''.join(struct.pack('<I', w) for w in patch.load_stubs().luma_reduce_words(0x800000))
        self.image[0x800000:0x800000 + len(code)] = code

    def test_build_and_every_instruction_are_checked(self):
        self.module.build_id = bytes(32)
        with self.assertRaises(ValueError):
            patch.generate(self.module, self.image, self.fixups)
        self.module.build_id = bytes.fromhex(patch.BUILD)
        for off in ABI:
            changed = bytearray(self.image)
            changed[off] ^= 1
            with self.subTest(off=hex(off)), self.assertRaisesRegex(ValueError, 'rewritten'):
                patch.generate(self.module, changed, self.fixups)

    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_display_backing_and_three_scene_levels_agree(self):
        assert uc is not None and arm is not None and Emulator is not None
        rows = [r.split('\t') for r in patch.generate(self.module, self.image, self.fixups).splitlines()]
        self.assertFalse(any(r[:2] == ['write', 'default'] for r in rows))
        for choice, width, height in patch.SIZES:
            u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
            u.mem_map(0x400000, 0x40000)
            u.mem_map(0x575000, 0x1000)   # GRAPHIC BUFFER heap constructors (575a30, 575c94)
            for row in rows:
                if row[:2] != ['write', choice]:
                    continue
                off, code = int(row[2], 16), bytes.fromhex(row[4])
                if off in (0x3ffbf8, 0x4066a0):
                    continue  # exercised with the full exposure helper below
                u.mem_write(off, code)
                u.emu_start(off, off + len(code))
                if off in (0x40f184, 0x40f1a4, 0x40f1d0):
                    self.assertEqual((u.reg_read(arm.UC_ARM64_REG_W1), u.reg_read(arm.UC_ARM64_REG_W2)), (width, height))
                elif off in (0x575a30, 0x575c94):
                    # GRAPHIC BUFFER heap and its BUFFER ROOT grow 8 bytes per pixel above 1080p, whole MiB
                    extra = ((width * height - 1920 * 1080) * 8 + 0xfffff) & ~0xfffff
                    self.assertEqual(u.reg_read(arm.UC_ARM64_REG_W1), (0xad60000 if off == 0x575a30 else 0x8f00000) + extra)
                elif off == 0x40e0b0:
                    pool = u.reg_read(arm.UC_ARM64_REG_W8)
                    required = 310 * 2**20 * width * height / (1600 * 900)
                    self.assertGreaterEqual(pool, required)
                    self.assertLess(pool - required, 65536)
                else:
                    word = struct.unpack('<I', code)[0]
                    reg = (arm.UC_ARM64_REG_W19 if off in (0x40d5e8, 0x40fb0c)
                           else arm.UC_ARM64_REG_W20 if off in (0x40d5f4, 0x40fb18)
                           else arm.UC_ARM64_REG_W8)
                    self.assertEqual(word & 31, 19 if reg == arm.UC_ARM64_REG_W19 else 20 if reg == arm.UC_ARM64_REG_W20 else 8)
                    self.assertEqual(u.reg_read(reg), width if off in (0x4328c0, 0x4328e0, 0x40d5e8, 0x40fb0c) else height)


class RhiTaskLifetime(unittest.TestCase):
    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_pending_second_node_survives_the_native_collector_loop(self):
        assert uc is not None and arm is not None and Emulator is not None
        stubs = patch.load_stubs()
        class Context:
            def __init__(self):
                self.code = []; self.writes = {}; self.runtime_exports = {}
            def here(self): return 0x100000 + 4 * len(self.code)
            def emit(self, word): self.code.append(word)
            def site(self, address, original): pass
            def put(self, address, words, reason): self.writes[address] = words
        ctx = Context(); stubs.quality_stubs(ctx)
        # Captured native collector: its inner back edge enters +0x9db704.
        loop = bytes.fromhex('f6031faa480180526912168b209141f9000200b437810c91'
                             '181840f9f80200f9f903082a080040f9080540f900013fd6'
                             '280700513f0b00716b000054e00318aad8feffb5e90240f9'
                             '490000b43f1500f9')
        u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
        for addr in (0x100000, 0x200000, 0x300000, 0x400000, 0x9db000):
            u.mem_map(addr, 0x10000)
        u.mem_write(0x100000, b''.join(struct.pack('<I', word) for word in ctx.code))
        u.mem_write(0x100500, bytes.fromhex('c0035fd6'))
        u.mem_write(0x9db6ec, loop)
        u.mem_write(0x9db704, b''.join(struct.pack('<I', word) for word in ctx.writes[0x9db704]))
        u.mem_write(0x200808, struct.pack('<Q', 0x100500))
        nodes = (0x200000, 0x200100, 0x200200)
        for i, node in enumerate(nodes):
            u.mem_write(node, struct.pack('<Q', 0x200800))
            u.mem_write(node + 0x18, struct.pack('<I', int(i == 1)))
            u.mem_write(node + 0x28, struct.pack('<Q', nodes[i - 1] if i else 0))
            u.mem_write(node + 0x30, struct.pack('<Q', nodes[i + 1] if i < 2 else 0))
        u.mem_write(0x300320, struct.pack('<Q', nodes[0]))
        u.reg_write(arm.UC_ARM64_REG_X19, 0x300000)
        u.reg_write(arm.UC_ARM64_REG_SP, 0x400800)
        released = []; object_register = arm.UC_ARM64_REG_X0
        def destroy(engine, address, size, data):
            if address == 0x100500: released.append(engine.reg_read(object_register))
        u.hook_add(uc.UC_HOOK_CODE, destroy)
        u.emu_start(0x9db6ec, 0x9db73c)
        self.assertEqual(released, [nodes[0]])
        self.assertEqual(struct.unpack('<Q', u.mem_read(0x300320, 8))[0], nodes[1])
        self.assertEqual(struct.unpack('<Q', u.mem_read(nodes[1] + 0x28, 8))[0], 0)
        u.mem_write(nodes[1] + 0x18, struct.pack('<I', 0))
        u.emu_start(0x9db6ec, 0x9db73c)
        self.assertEqual(released, list(nodes))
        self.assertEqual(struct.unpack('<Q', u.mem_read(0x300320, 8))[0], 0)

    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_retirement_keeps_pending_head_and_preserves_the_callers_registers(self):
        assert uc is not None and arm is not None and Emulator is not None
        stubs = patch.load_stubs()
        for pending, dest in ((1, 0x9db730), (0, 0x9db708)):
            u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
            for addr in (0x100000, 0x200000, 0x400000, 0x9db000):
                u.mem_map(addr, 0x1000)
            u.mem_write(0x100000, b''.join(struct.pack('<I', w) for w in stubs.retire_ready_words(0x100000)))
            u.mem_write(0x200018, struct.pack('<I', pending))
            u.mem_write(0x200030, struct.pack('<Q', 0xfeed))
            u.reg_write(arm.UC_ARM64_REG_X0, 0x200000)
            u.reg_write(arm.UC_ARM64_REG_X9, 0x300000)
            u.reg_write(arm.UC_ARM64_REG_X23, 1234)
            u.reg_write(arm.UC_ARM64_REG_X24, 5678)
            u.reg_write(arm.UC_ARM64_REG_X16, 456)
            u.reg_write(arm.UC_ARM64_REG_X17, 789)
            u.reg_write(arm.UC_ARM64_REG_SP, 0x400800)
            u.reg_write(arm.UC_ARM64_REG_NZCV, 0xa0000000)
            u.emu_start(0x100000, dest)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X23), 1234)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X24), 5678 if pending else 0xfeed)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X0), 0x200000)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X9), 0x300000)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X16), 456)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X17), 789)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_SP), 0x400800)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_NZCV), 0xa0000000)

    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_completion_is_the_last_object_access(self):
        assert uc is not None and arm is not None and Emulator is not None
        u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
        for addr in (0x100000, 0x200000):
            u.mem_map(addr, 0x1000)
        code = b''.join(struct.pack('<I', w) for w in patch.load_stubs().task_complete_words())
        u.mem_write(0x100000, code)
        u.mem_write(0x200018, struct.pack('<I', 1))
        u.mem_write(0x200048, struct.pack('<Q', 99))
        u.reg_write(arm.UC_ARM64_REG_X20, 0x200000)
        writes = []
        u.hook_add(uc.UC_HOOK_MEM_WRITE, lambda engine, access, address, size, value, data: writes.append((address, size, value)))
        u.emu_start(0x100000, 0x100000 + len(code))
        self.assertEqual(writes, [(0x200048, 8, 0), (0x200018, 4, 0)])
        self.assertEqual(struct.unpack('<I', u.mem_read(0x200018, 4))[0], 0)


class Exposure(unittest.TestCase):
    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_downsample_call_and_uniform_source_agree(self):
        assert uc is not None and arm is not None and Emulator is not None
        # Real ABI: source is pyramid+0x80, the next allocated image is +0xa0.
        # The native downsample function must be called before exposure uses it.
        u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
        for addr in (0x100000, 0x3f0000, 0x99b000):
            u.mem_map(addr, 0x20000)
        code = b''.join(struct.pack('<I', w) for w in patch.load_stubs().luma_reduce_words(0x100000))
        u.mem_write(0x100000, code)
        u.mem_write(0x99b190, bytes.fromhex('c0035fd6'))  # ordinary callee returns
        u.reg_write(arm.UC_ARM64_REG_X19, 0x200000)
        u.reg_write(arm.UC_ARM64_REG_X21, 0x300000)
        u.reg_write(arm.UC_ARM64_REG_X23, 0x300080)
        calls = []
        registers = (arm.UC_ARM64_REG_X0, arm.UC_ARM64_REG_X1,
                     arm.UC_ARM64_REG_X2, arm.UC_ARM64_REG_W3)
        def called(engine, address, size, data):
            if address == 0x99b190:
                calls.append([engine.reg_read(r) for r in registers])
        u.hook_add(uc.UC_HOOK_CODE, called)
        u.emu_start(0x100000, 0x3ffbfc)
        self.assertEqual(calls, [[0x200000, 0x300080, 0x3000a0, 1]])
        self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X23), 0x3000a0)
        u.reg_write(arm.UC_ARM64_REG_X8, 0x300000)
        u.mem_write(0x4066a0, bytes.fromhex('16810291'))
        u.emu_start(0x4066a0, 0x4066a4)
        self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X22), 0x3000a0)

    def test_capacity_and_helper_validation(self):
        fixture = Manifest(); fixture.setUp()
        rows = [r.split('\t') for r in patch.generate(fixture.module, fixture.image, fixture.fixups).splitlines()]
        expected = {'native': (91, False), '1080p': (135, False), '1440p': (240, False),
                    '2160p': (135, True), '2880p': (240, True)}
        for choice, width, height in patch.SIZES:
            count, selected = expected[choice]
            writes = [r for r in rows if r[:2] == ['write', choice] and r[2] in ('3ffbf8', '4066a0')]
            self.assertEqual(len(writes), 2 if selected else 0)
            shift = 5 if selected else 4
            self.assertEqual((((width >> shift) + 7) // 8) * (((height >> shift) + 7) // 8), count)
            self.assertLessEqual(count, 256)
        broken = bytearray(fixture.image); broken[0x800000] ^= 1
        with self.assertRaisesRegex(ValueError, 'helper'):
            patch.generate(fixture.module, broken, fixture.fixups)


class ShadowArena(unittest.TestCase):
    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_four_tiles_cover_the_selected_atlas(self):
        assert uc is not None and arm is not None and Emulator is not None
        abi = {0x40e0b4: 'e84700f9', 0x40e1ec: 'e8031532',
               0x401fa8: 'e3031632', 0x401fac: 'e4031632',
               0x401fb0: '01011653', 0x401fb4: '08591753', 0x401fb8: '02011612'}
        original = bytearray(0xa0e7d0)
        for off, code in abi.items():
            original[off:off + 4] = bytes.fromhex(code)
        module = types.SimpleNamespace(build_id=bytes.fromhex(patch.BUILD), text_end=len(original), image=original)
        image = bytearray(original)
        fix = {'BUILD_ID': patch.BUILD[:32], 'TEXT_END': hex(len(original)), 'PATCH_OFF': '0x800000'}
        stubspec = importlib.util.spec_from_file_location('astral_tile_stubs', ROOT / 'dm/games/01007300020FA000/patches.py')
        assert stubspec is not None and stubspec.loader is not None
        stubs = importlib.util.module_from_spec(stubspec); stubspec.loader.exec_module(stubs)
        for index, (name, atlas) in enumerate((('HIGH', 4096), ('ULTRA', 8192))):
            off = 0x800000 + index * 0x100
            fix['RUNTIME_AC_SHADOW_' + name] = hex(off)
            code = b''.join(struct.pack('<I', w) for w in stubs.shadow_pool_words(off, (atlas * atlas - 2048 * 2048) * 4))
            image[off:off + len(code)] = code
        rows = [r.split('\t') for r in patch.generate_shadow(module, image, fix).splitlines()]
        for choice, atlas in (('high', 4096), ('ultra', 8192)):
            for index in range(4):
                u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
                u.mem_map(0x400000, 0x10000)
                for row in rows:
                    if row[:2] == ['write', choice] and 0x401fa8 <= int(row[2], 16) <= 0x401fb8:
                        u.mem_write(int(row[2], 16), bytes.fromhex(row[4]))
                u.reg_write(arm.UC_ARM64_REG_W8, index)
                u.emu_start(0x401fa8, 0x401fbc)
                tile = atlas // 2
                self.assertEqual([u.reg_read(r) for r in (arm.UC_ARM64_REG_W1, arm.UC_ARM64_REG_W2,
                                                         arm.UC_ARM64_REG_W3, arm.UC_ARM64_REG_W4)],
                                 [(index & 1) * tile, (index >> 1) * tile, tile, tile])

    @unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
    def test_arena_helper_preserves_registers_and_returns(self):
        assert uc is not None and arm is not None and Emulator is not None
        stubspec = importlib.util.spec_from_file_location('astral_shadow_stubs', ROOT / 'dm/games/01007300020FA000/patches.py')
        assert stubspec is not None and stubspec.loader is not None
        stubs = importlib.util.module_from_spec(stubspec)
        stubspec.loader.exec_module(stubs)
        for atlas in (4096, 8192):
            u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
            for addr in (0x100000, 0x200000, 0x40e000):
                u.mem_map(addr, 0x1000)
            u.reg_write(arm.UC_ARM64_REG_SP, 0x200800)
            u.reg_write(arm.UC_ARM64_REG_X8, 310 * 2**20)
            u.reg_write(arm.UC_ARM64_REG_X16, 123)
            u.reg_write(arm.UC_ARM64_REG_X17, 456)
            extra = (atlas * atlas - 2048 * 2048) * 4
            code = b''.join(struct.pack('<I', w) for w in stubs.shadow_pool_words(0x100000, extra))
            u.mem_write(0x100000, code)
            u.emu_start(0x100000, 0x40e0b8)
            self.assertEqual(struct.unpack('<Q', u.mem_read(0x200888, 8))[0], 310 * 2**20 + extra)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_SP), 0x200800)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X16), 123)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_X17), 456)


class ShaderConstants(unittest.TestCase):
    def test_verified_smaa_tuning_and_unrelated_shaders(self):
        source = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define MLOG(...) do { if (0) printf(__VA_ARGS__); } while (0)
#include "SHADER_PATH"
int main(void) {
 uint32_t edge[8]={0x3dcccccd}, search[8]={0xc1fe6666,0x41fe6666};
 setenv("DM_AC_AA","high",1);
 nvn_profile_shader_constants("unrelated_shader",edge,sizeof edge);
 assert(edge[0]==0x3dcccccd);
 nvn_profile_shader_constants("8d7c664bb174a05f_b",edge,sizeof edge);
 assert(edge[0]==0x3d4ccccd);
 nvn_profile_shader_constants("b56e3fc19366bac9_b",search,sizeof search);
 assert(search[0]==0xc27f3333 && search[1]==0x427f3333);
 edge[0]=0x3dcccccd; setenv("DM_AC_AA","off",1);
 nvn_profile_shader_constants("8d7c664bb174a05f_b",edge,sizeof edge);
 assert(edge[0]==0x7f7fffff);
 edge[0]=123;
 nvn_profile_shader_constants("8d7c664bb174a05f_b",edge,sizeof edge);
 assert(edge[0]==123);
 return 0;
}
'''.replace('SHADER_PATH', str(ROOT / 'dm/games/01007300020FA000/shader_runtime.inc'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'test.c').write_text(source)
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()


@unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
class ModelThresholds(unittest.TestCase):
    def test_default_and_named_rates_preserve_every_register(self):
        assert uc is not None and arm is not None and Emulator is not None
        stubs = patch.load_stubs()
        for site, original, source, slot in stubs.DETAIL_SITES:
            for factor in (0.5, 0.25, 0.0):
                u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
                for addr in (0x100000, 0x200000, site & ~0xfff): u.mem_map(addr, 0x1000)
                u.reg_write(arm.UC_ARM64_REG_SP, 0x200f00)
                u.reg_write(arm.UC_ARM64_REG_X8, 0x200100)
                u.reg_write(arm.UC_ARM64_REG_W9, struct.unpack('<I', struct.pack('<f', 0.7))[0])
                for n in range(32): u.reg_write(getattr(arm, f'UC_ARM64_REG_Q{n}'), (n+17) * 0x123456789abcdef)
                u.reg_write(arm.UC_ARM64_REG_S0, struct.unpack('<I', struct.pack('<f', 0.2))[0])
                u.reg_write(arm.UC_ARM64_REG_NZCV, 0xa0000000)
                before = [u.reg_read(getattr(arm, f'UC_ARM64_REG_Q{n}')) for n in range(32)]
                w9 = u.reg_read(arm.UC_ARM64_REG_W9)
                code = b''.join(struct.pack('<I', w) for w in stubs.detail_words(0x100000, site, source, slot, factor))
                u.mem_write(0x100000, code)
                u.emu_start(0x100000, site+4, count=20)
                result = struct.unpack('<f', u.mem_read(0x200100 + slot*4, 4))[0]
                self.assertAlmostEqual(result, (0.7 if source == 'w9' else 0.2) * factor, places=6)
                self.assertEqual([u.reg_read(getattr(arm, f'UC_ARM64_REG_Q{n}')) for n in range(32)], before)
                self.assertEqual(u.reg_read(arm.UC_ARM64_REG_W9), w9)
                self.assertEqual(u.reg_read(arm.UC_ARM64_REG_SP), 0x200f00)
                self.assertEqual(u.reg_read(arm.UC_ARM64_REG_NZCV), 0xa0000000)


@unittest.skipIf(uc is None, 'optional ARM64 execution dependency: unicorn')
class AspectBridge(unittest.TestCase):
    def test_private_call_preserves_context_and_exposes_only_declared_outputs(self):
        assert uc is not None and arm is not None and Emulator is not None
        stubs = patch.load_stubs()
        for site, original, event, before in stubs.ASPECT_SITES:
            u = Emulator(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
            for addr, size in ((0x100000, 0x10000), (0x200000, 0x10000), (site & ~0xfff, 0x2000), (0xa0e000, 0x1000)):
                u.mem_map(addr, size)
            u.reg_write(arm.UC_ARM64_REG_SP, 0x20f000)
            for n in range(31): u.reg_write(getattr(arm, f'UC_ARM64_REG_X{n}'), 0x202000)
            for n in range(32): u.reg_write(getattr(arm, f'UC_ARM64_REG_Q{n}'), (n+1)*0x123456789abcdef)
            u.reg_write(arm.UC_ARM64_REG_NZCV, 0x60000000)
            u.mem_write(0xa0e7b0, bytes.fromhex('c0035fd6'))
            u.mem_write(0x108000, bytes.fromhex('c0035fd6'))
            called = []
            def intercept(em, address, size, data):
                if address == 0xa0e7b0:
                    em.reg_write(arm.UC_ARM64_REG_X0, 0x108000)
                elif address == 0x108000:
                    context = em.reg_read(arm.UC_ARM64_REG_X0)
                    called.append(em.reg_read(arm.UC_ARM64_REG_W1))
                    self.assertEqual(context, 0x20ed00)
                    # Simulate a host call clobbering every volatile register.
                    for n in range(18): em.reg_write(getattr(arm, f'UC_ARM64_REG_X{n}'), 0xdead)
                    for n in range(32): em.reg_write(getattr(arm, f'UC_ARM64_REG_Q{n}'), 0xfeed)
                    em.reg_write(arm.UC_ARM64_REG_NZCV, 0xf0000000)
                    if event == 0: em.mem_write(context+8*8, struct.pack('<Q', 1))
            u.hook_add(uc.UC_HOOK_CODE, intercept)
            code = b''.join(struct.pack('<I', w) for w in stubs.aspect_words(0x100000, site, original, event, before))
            u.mem_write(0x100000, code)
            u.emu_start(0x100000, site+4, count=300)
            self.assertEqual(called, [event])
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_SP), 0x20f000)
            self.assertEqual(u.reg_read(arm.UC_ARM64_REG_NZCV), 0x60000000)
            for n in range(31):
                if n in (0 if event == 6 else 8,): continue  # the displaced instruction's output
                self.assertEqual(u.reg_read(getattr(arm, f'UC_ARM64_REG_X{n}')), 0x202000)
            for n in range(32):
                if n == 0 and event in (2,3): continue  # displaced LDR S0 zeroes upper lanes
                if n == 1 and event == 1: continue  # displaced FMOV S1,#.5
                self.assertEqual(u.reg_read(getattr(arm, f'UC_ARM64_REG_Q{n}')), (n+1)*0x123456789abcdef)
