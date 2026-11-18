# ASTRAL CHAIN (`01007300020FA000`)

Update 1.0.1 (v65536) over the base game. PlatinumGames' engine, SDK 6.4.0, NVN, Wwise audio through `AudioOut`; modules `main` and `sdk`. The 1.0.1 profile enables a 60 fps gameplay target with corrected game timing; fixed-step cinematics retain 30 fps. Mac testing completes motorcycle combat and reaches the first on-foot checkpoint. An unsigned IPA builds; iPhone testing is pending.

## What it needs

| Setting | Where | Why |
|---|---|---|
| `mem_reserve 0xf0000000`, `mem_alias 0x10000000`, `mem_stack 0x10000000`, `app_pool 0xCD500000` | [`game.tsv`](game.tsv) | 3 GB heap region; the first Mac boot requests 2.96 GB, with the game's 191 MB BSS counted as used memory |
| `sys_resource 0x0` | `game.tsv` | the NPDM declares no system resource; no virtual address memory |
| `pad_layout full` | `game.tsv` | movement and camera use both sticks |
| `fps_target 60` | `game.tsv`, [`patches.py`](patches.py) | host-paced gameplay with fractional timer carry, integer input windows and camera smoothing; only the verified 1.0.1 main build |
| `depth_mode zero` | `game.tsv` | the game sets the near = 0 depth mode, so the pipeline bases made before it runs (the NSP script's Mac prebuild, and a [pipeline archive made offline](../../../docs/development.md#the-pipeline-archive-made-offline) for the iPhone when one is built with `DM_PSO_GPUS`) take its vertex shaders' `main0_z` entries (the host itself follows the mode the game sets) |

## Files and shaders

- 82 PKZ archives, version `0x10000`, holding 8,556 Zstandard-compressed entries, alongside Bink 2 movies (`.bk2`) and Wwise banks and streams. The PKZ directory and name-table layout matches version `0x20000`; every entry's bounds were checked and one entry per archive was decoded before extending the reader.
- `root.pkz` contains PlatinumGames DAT shader archives. The full split finds 1,348 distinct shaders: 540 vertex, 738 pixel, 70 compute. Single-stage programs produce 1,620 cover pairs. All 1,348 compile for Mac and iOS, with zero undecoded bindings and zero unfillable driver-bank reads.
- GPU code versions in the root shader archives include 1.9, 1.12 and 1.15, despite the linked SDK being 6.4.0. The game sets upper-left window origin, near-zero depth, a 1600×900 swap chain and present interval 2.

## Services and SDK

- **Resolved: startup fails, then cleanup reads null at `main+0x9c0d1c`.** `main+0x40d6c0` loads `hwfillcolor`; its vertex shader is version 1.15. The shader loader compares byte 7 with the driver's newest minor at `main+0x9e97d0` and rejects the old answer 1.14. A probe at `main+0x9dcf28` confirms failure before the subsequent cleanup crash. The host now advertises the translator's supported GPU-code range independently of the linked SDK. No game-code cut is needed.
- [Issue #170](https://github.com/seedds/nxnative/issues/170) independently reports the same initialization crash and PKZ version. Its shader-map generic-type warning was also confirmed: `g_shmap` holds strings, and its declaration now agrees. Its translator source-hash failure was not reproduced; the pinned translator built all shaders without rebuilding the translator.

## Status on the Mac

- ZL+ZR prompt, logos, opening real-time cinematic, character creation (including software-keyboard naming), save creation/reload and the motorcycle tutorial render on an M4 Pro. The original 30 fps run had a warm frame median of 33.34 ms. The 60 fps validation and its limits are below.
- Wwise opens a stereo `AudioOut`; the 15-minute `play03` run reaches 84,000 device callbacks with zero reported underruns. Resident memory grows from 1.44 GB at the title to 2.57 GB on entering the tutorial; Metal allocated memory is about 3.02 GB there.
- The first boot rendered in a Mac window. A later windowed run stalled in the display link; the sustained measurements and screenshots use `DM_WINDOW` unset and `DM_PRESENT_LINK=0`. They measure offscreen native rendering, not on-screen presentation quality.
- **Current:** entering the motorcycle scene reports one cube/2D texture mismatch, handled by the existing [zero-cube fallback](../../../docs/reference/rendering.md#a-2d-texture-in-a-cube-slot-binds-the-zero-cube). The scene renders, but that binding has not been traced to establish whether it is an intentional placeholder.
- Work folder: `/Volumes/T7/nsp/ASTRAL CHAIN/01007300020FA000-work`. `run/boot.py <log-name> <seconds> [KEY=VALUE ...]` launches a bounded run, with its control file at `run/<log-name>.ctl`, logs and saves beside it. The build artifacts and extracted data are in the adjacent `01007300020FA000_build`.

## Frame rate

**Current: 60 fps gameplay target on 1.0.1**, main build `4b159f0f7a360669738390ee8657b4f0`. The profile uses the host's frame step and pacing instead of simply overriding present interval 2. `DM_FPS_TARGET=30` selects a 30 fps cap with the same timing; `DM_FPS_TARGET=0` executes the original instructions at every hook.

**Resolved: half-frame steps stop integer timers.** The earlier four-cut [FPSLocker experiment](https://github.com/masagrator/FPSLocker-Warehouse/blob/v4/SaltySD/plugins/FPSLocker/patches/01007300020FA000/4B159F0F7A360669.yaml) raised the title frame rate, but `main+0x48be14` and `main+0x57e7e0` truncated the half-frame step to zero. The new clock stores the floating 30 Hz step at clock `+0xd0`, carries fractional ticks at `+0xd4` and publishes whole ticks at `+0xd8`. Both 60 half-step updates and 30 full-step updates advance integer timers by 30 ticks. Action/input windows, hit-stop, pad repeat and rumble counters consume those whole ticks; camera interpolation uses elapsed-time decay.

The timer and camera helpers are adapted from the MIT-licensed [AstralChain-Dynamic-FPS v1.1.1](https://github.com/yogesh1239/AstralChain-Dynamic-FPS/tree/79965b4df077f64b27b74456d0db88c6afac5bbe), with its license retained in `patches.py`. Its measured-time core and interval overrides are replaced by a host-paced clock. All 112 hook sites check their original bytes, and the complete set is build-ID gated. Helpers are relocated into the rewriter's allocated patch area rather than overwriting the upstream code caves. With this main's 191 MB BSS, helpers sit before the module base; frame state is at `main+0xccec000`, image size `0xccf0000` (the general allocation fix is linked below).

The engine's fixed-step mode (`w21 == 0` at `main+0x91dc10`) sets the host's 30 fps cinematic flag and a two-vsync step. Variable-step gameplay releases that cap and consumes the host's chosen step, including catch-up after late frames. This preserves the fixed-step mode's original clock rather than forcing every cinematic to 60 fps. Other real-time cinematics can use the engine's variable-step mode. Audio/video synchronization across all movies has not been verified; the upstream patch reports some remaining drift and incomplete timer coverage.

Validation on the M4 Pro:

- ARM64 execution tests run the emitted stubs without game files: fractional carry, integer consumers (including the zero-tick branch), first-sample initialization, cinematic cap/release, input-window duration and flags, original behavior with target 0, and camera decay after equal elapsed time. The original integer conversion failed the 60-half-step check before the fix.
- Native `timing61` loads a save, passes character creation, completes motorcycle combat with firing, steering and evasion, and reaches the first on-foot checkpoint. Movement and camera rendering work there, with sampled windows reaching 60.0 fps. The warmed title holds 60 fps (16.6 ms median); the fixed-step opening cinematic changes to 30 and character creation releases the cap to 60. Motorcycle rendering reaches 59.7 fps but also dips under concurrent machine load; sustained 60 fps throughout gameplay is not established.
- Host telemetry records 30.00 game seconds in 30.00 real seconds in a 60 fps window. With adaptive holds during motorcycle combat, representative windows are 40.98/40.87 and 61.05/60.93 seconds (ratios 1.003 and 1.002). This checks clock speed, not all combat mechanics or on-screen presentation. Later stalls can exhaust catch-up; it is not an unlimited compensation for arbitrary pauses.
- The run uses offscreen native rendering as described above. Later Legion combat, Bink movies, end credits and iPhone performance remain untested.

## Enhanced Mac build (2026-11-16, current experimental)

Branch `codex/astral-chain-enhanced`, based on `codex/mp4-image-quality`
at `7c52697e` (which contains the local `codex/bayonetta3-enhanced` tip).
The installed self-contained app is `/Applications/Games/Astral Chain.app`,
display name **Astral Chain Enhanced**, version 1.0.1. The NSP folder is
`~/Downloads/Nintendo Switch 1:2 — images/Astral Chain [NSP]`; extraction,
shader cache and host are in its `01007300020FA000_build`, and isolated
test saves, screenshots and logs in `01007300020FA000-work`.

### Resolution and memory

[`runtime_patches.py`](runtime_patches.py) emits a strict `DMRT1` manifest for
main `4b159f0f7a360669738390ee8657b4f0` only. Both display getters, startup
and recreation backing-target dimensions, and all three dynamic-resolution
levels receive one canvas. The explicit fixed modes override console mode;
`default` makes zero writes and restores the game's original automatic path.
This preserves the backing/view invariant learned from Bayonetta, and prevents
the game's smaller pause-menu family from reinterpreting another size's data.
The dimensions were checked against disassembly of the local original NSO;
the generator also checks original and rewritten bytes before producing any
manifest. The host checks the build and bytes again at launch.

The site-discovery reference is
[Puddz/AstralChain-PC's resolution patch](https://github.com/Puddz/AstralChain-PC/blob/6b2d624dd6451f9481013fc3a6ccbcd3ba5f1a7a/astral_chain/patches/resolution-1.0.1.pchtxt).
Its foreign SVC hooks and runtime are not imported. The original render-target
arena is 310 MiB at 1600x900; fixed modes reserve pixel-proportional capacity,
rounded up to 64 KiB, while retaining the game's own allocator and failure
handling. This is a conservative reservation, not a measured minimum. The
parent heap independently uses the existing Mac `DM_APP_POOL=10G` option.
Only touched memory becomes resident. High resolutions with the Switch-sized
heap are not validated.

| Launcher setting | Default | Choices / scope |
|---|---|---|
| Resolution (`DM_AC_RESOLUTION`) | `2160p` | original automatic, fixed 1600x900, 1920x1080, 2560x1440, 3840x2160, 5120x2880 |
| Shadow quality (`DM_AC_SHADOW`) | `high` | original 2048 atlas, High 4096, Ultra 8192 |
| Anti-aliasing (`DM_AC_AA`) | `high` | off, original SMAA, SMAA High |
| Game memory (`DM_APP_POOL`) | `10G` | extended or original Switch pool |
| Texture filtering (`DM_NVN_ANISO`) | `16` | game default, 2x, 4x, 8x, 16x; the general surface-sampler rule preserves lookup and shadow samplers |
| Frame rate | 60 | existing verified frame step; fixed-step cinematics retain 30 |

Defaults live in this profile's `setting_default` rows and remain adjustable.
The resolution/memory controls require a matching rewritten runtime manifest
and are Mac-only. iOS quality defaults are unchanged. The app includes all
1,348 shader keys, with zero completeness issues, and a 65.2 MB pipeline
archive for this M4 Max (`applegpu_g16s`). No shader-chain tool changed.

### Shadows and SMAA

The shadow manifest checks seven original instructions and the exported helper
bytes. The atlas constructor and all four tile viewports change together:
High uses 4096 with 2048 tiles, Ultra 8192 with 4096 tiles. A selectable helper
adds the exact extra four-byte guest depth/stencil storage (48 or 240 MiB) to
the chosen resolution's arena without overlapping its resolution write. It
preserves x16/x17 and SP and executes the original store before returning.
This increases shadow resolution; it does not change cascade coverage, bias,
PCF kernel, lighting, textures or model detail.

The game already uses three-pass SMAA. [`shader_runtime.inc`](shader_runtime.inc)
tunes only the GPU copy of the verified shaders' immutable constants: edge
`8d7c664bb174a05f` threshold 0.1 to 0.05, weight `b56e3fc19366bac9` search
bounds +/-31.8 to +/-63.8 pixels. Off uses FLT_MAX for the edge threshold;
composition dependencies and passes remain. Original constants must match
before modification. Other shaders/profiles do not take this hook. This is
spatial anti-aliasing, with no temporal history or texture-detail recovery.

### Validation and limits

Bounded native runs on the M4 Max (48 GB), macOS 27.0 / Xcode 27.2:

- `baseline2`: original 1600x900, 100 seconds offscreen.
- `fixed1080`: 110 seconds offscreen; frame 900 has thirteen 1920x1080
  passes, three 960x540 passes and the corresponding smaller post-processing
  passes. The final crop and screenshots are 1920x1080.
- `fixed1440`: 110 seconds in a Mac window; frame 900 has thirteen
  2560x1440 passes and 1280x720 / 640x360 / 320x180 intermediates.
- `fixed4k`: 180 seconds in a Mac window; frame 900 has thirteen
  3840x2160 passes, three 1920x1080 passes and the matching smaller family.
  Final crop and screenshots are 3840x2160. The introduction, subtitles and
  credits render with their original proportions; no red line, allocation
  failure or crash. Representative cinematic GPU p50 is 7.9–8.6 ms, p95
  10.7–11.0 ms; the game's fixed-step cinematic intentionally holds 30 fps.
  A clock window reports 60.00 game seconds in 60.14 real seconds.

These runs verify the introduction, not sustained combat or cinematic
audio/video synchronization. Later combat, movies, pause/reload transitions,
and the complete original-resolution fallback route remain open. Some
screen-space passes remain at 1280x720 (as seen in the original engine); this
is not a claim that every effect becomes 4K. Model LOD, 120 fps and a native
16:10 camera/HUD adaptation are not implemented here.
The standard fit/fill and optional MetalFX presentation settings remain.

Additional quality runs (offscreen, same M4 Max): `quality4k_high` 75 seconds
at 4K / High shadows / SMAA High, and `quality4k_ultra` 70 seconds at 4K /
Ultra shadows / AA off. Frame 900 confirms 4096/8192 depth attachments and
2048/4096 tile viewports, plus the original aspect and matching scene family.
The SMAA constants log their verified changes. `installed_quality2` checks
the rebuilt installed app for 90 seconds in a Mac window at 4K / High / SMAA
High; its 3840x2160 screenshot and constants agree, with no red line or crash.
Deep/strict ad-hoc signature verification passes. Both offscreen runs finish without a red
line or crash; screenshots show the introduction. `quality1080_ultra` checks
Ultra with a smaller resolution arena. These are introduction checks, not
combat shadow quality or comparative anti-aliasing benchmarks.

### High-resolution exposure overflow (resolved)

5K initially crashed at main+0x999250 (null renderer, caller +0x3c0c28).
The failed 0x6000 GPU resource allocation was a consequence of corrupted
GPURO allocator metadata, not insufficient total memory. Disabling GPU command
execution in LLDB prevented it; the pass dump located the overwrite.

The luminance pass `613993ce8c8986e1` stores one float per 8x8 workgroup into
a fixed 256-float / 1024-byte buffer (constructor main+0xa0392c). Its 1/16-size
input becomes 320x180 at 5K: 40x23 groups write 920 floats. 4K's 30x17 also
exceeds capacity, despite not crashing immediately. The second reduction,
`3dbb6d849ea0d18c`, has only 256 threads, so enlarging the scratch buffer alone
would not make exposure correct.

For fixed modes whose partial sums exceed 256, the runtime manifest selects
the existing 1/32 image at pyramid+0xa0. A helper at main+0x3ffbf8 adds the
ordinary downsample from +0x80 to +0xa0, retaining the original pyramid outputs.
Main+0x4066a0 selects that same image for dimensions, group count and pixel
normalization. 4K now uses 120x67 / 15x9 groups (135 values); 5K uses 160x90 /
20x12 groups (240 values). Through 1440p the original path is unchanged. The
main scene, output, bloom pyramid and shadows keep their selected resolution.
No shader, allocator clamp, null skip or larger fixed GPURO reservation is
used. Both helper code and original instructions are verified before packing.

### RHI task retirement at 60 fps (resolved)

After exposure was fixed, windowed 5K / 60 fps exposed a second crash at
main+0x9db290, calling through a freed buffer object's vtable when entering
the opening movie. The same route passed with original timing or 30 fps.
LLDB stopped at main+0x9db710 while the collector was about to destroy a
buffer whose CPU initialization flag at +0x18 was still 1 and whose virtual
task was main+0x9e7510 (`fivek_retire_pending`). The main thread freed it,
then reused its bytes for another buffer while the resource worker still
held the task. This is separate from exposure's GPU overwrite.

The build-gated profile now checks the pending flag with an acquire load at
main+0x9db704, inside the collector's loop, before unlinking **every** object.
A pending node stays at the head of its ordered retirement bucket, including
when earlier completed nodes were deleted; the head's backward link is
cleared by the original epilogue. The collector proceeds on the next ordinary
frame after initialization completes. The worker at main+0x9db29c writes its
last +0x48 field **before** release-publishing completion at +0x18; it never
touches a completed object afterward. No sleep, longer timeout, forced GPU
finish or 30 fps cap is shipped. The fixes are keyed to the registered NSO
build, independent of the player's resolution and frame-rate choices.

ARM64 tests execute the captured collector loop with a completed first node
and pending second node, then complete the second and verify eventual cleanup
of the complete list. They also verify completion-store ordering, registers,
stack and condition flags. Exposure tests execute the extra native downsample
call and verify that the uniform source and capacity agree for every mode.

### 5K follow-up validation

- `fivek_exposure_fixed`: 95 seconds offscreen at 5120x2880 / High shadows /
  SMAA High; the title scene and prompt render, with no red line or crash.
- `fivek_scene_high`: 75 seconds offscreen through the opening movie at 5K /
  High / SMAA High, screenshots at frames 900 and 1800.
- `fivek_window_retirement2`: 120 seconds in a Mac window at 5K / Ultra /
  SMAA High with the 60 fps profile. The title-to-movie transition succeeds;
  frames 900 and 2700 are 5120x2880, frame 900 has the 8192 shadow atlas and
  4096 tiles, and luminance dispatch is 20x12 over 160x90. No red line or crash.
  The cinematic intentionally keeps its original 30 fps; this is not a 60 fps
  gameplay performance claim.
- `fourk_final_regression`: 45 seconds in a Mac window at 4K / High / SMAA
  High with both fixes; frame 900 is 3840x2160 and the movie transition succeeds.
- The rebuilt self-contained app's launcher lists 5K (5120x2880), with the
  existing 4K default and Extended memory. It packages both fixes and all 1,348
  shader keys. `codesign --verify --deep --strict` passes. The final installed
  app is tested from its bundled RomFS, code and shaders in an isolated save
  (`fivek_installed_final`); frame 900 is 5120x2880 after the movie transition.
- The profile-only static regression (`20261116-224538-chain/report.json`)
  passes all 1,348 shaders with zero changed MSL or new interface failure.
  Scope is Astral's registered NSO and its runtime manifest; no shared host or
  shader-chain code changed in this follow-up. The 63 focused tests pass;
  Python lint reports the same eight inherited findings and none in these
  changes. Later combat, long sessions and movies beyond this route remain
  untested.

**Native 16:10 (open):** main+0x9a30a0 derives projection aspect from a camera's
logical dimensions. The 1280x720 callers at main+0x3a2398 and main+0x9045d4
need separate world-camera/UI investigation; the 256x256 cube camera must
remain square. Backing sizes, UI projection and world-to-screen markers need
joint testing. Fit/fill remains the presentation option; it is not native
16:10 scene rendering.

ARM64 execution tests cover all fixed-size writes, the three levels, backing
constructors, arena capacity and the existing timing stubs; changed builds or
instructions are rejected. `regress.py check --baseline 7c52697e --games
01007300020FA000` passes all 1,348 shaders, no changed MSL or new interface
failure. This profile has no smoke route, so that report contains no boot or
performance comparison; native checks above are separate. The five-game check
was attempted with Astral Chain, Bayonetta 3, Metroid Prime 4, Super Mario
Odyssey and Breath of the Wild (NVN/presentation and launcher coverage), but
stops because only Astral Chain has a source Mac build on disk. Installed apps
do not supply the missing extraction/build folders.

The focused settings/runtime/timing/documentation suite passes 63 tests, with
the ARM64 tests enabled through the shared venv's Unicorn package. The complete
Python tool suite runs 1,680 tests (16 skips), with one failure in the inherited
environment-switch inventory: obsolete MP4 HUD rows and an undocumented
`DM_MENU_TRACE`. The lint ratchet also reports inherited MP4 diagnostic-file
findings and private-import warnings exposed by installing the optional
Unicorn dependency; the new Astral files have no reported lint finding.
Ad-hoc bundle verification (`codesign --verify --deep --strict`) passes.
The quality follow-up C/Objective-C lint uses LLVM 23.1.5: 66 findings in
five files, with zero file/check pairs above the existing baseline. The
Python ratchet retains the same eight inherited findings and no finding in
the new Astral files. The repeated five-game check is blocked by the same
four missing source builds; Astral-only static regression passes again
(`20261116-171634-chain/report.json`).
The complete graphics suite (`make -C dm/gfx/tests GAME=01007300020FA000
-j8 run`, with the shared venv first in `PATH`) passes. The first attempt used
the system Python 3.9 for shader fixtures and stopped on modern type syntax;
rerunning with the shared Python resolves that environment issue.

Reproduce with the shared game venv and local keys (never printed):

```sh
~/games/venv/bin/python3 scripts/build_ipa_from_nsp.py \
  "<NSP folder>" -k "<prod.keys>" --platform mac-app \
  --app-name "Astral Chain Enhanced" --out "<output>/Astral Chain.app" \
  --require-complete-shaders --progress lines
```

## Found on this game

- [A frame-step stub with sub-60 FPS units](../../../docs/reference/frame-rate.md#a-frame-step-stub-with-sub-60-fps-units).

- [A profile-only present counter breaks other NVN host builds](../../../docs/reference/packing.md#a-profile-only-present-counter-breaks-other-nvn-host-builds).

- [Frame-step state with a front patch area](../../../docs/reference/rewriter.md#frame-step-state-with-a-front-patch-area).
- [PKZ version 1 archives](../../../docs/reference/shaders.md#pkz-version-1-archives).
- [Newest GPU code version reported by the driver](../../../docs/reference/nvn-objects.md#newest-gpu-code-version-reported-by-the-driver): precompiled shader versions do not follow the linked SDK.
- [The alpha test through a library of its own](../../../docs/reference/rendering.md#the-alpha-test-through-a-library-of-its-own): the death effect's tendrils (`EffectOpacityBlood`, alpha written by the shader, no `discard`) stayed solid black; reported on PR #32 with an implementation of its own (358 of one frame's 3,048 draws alpha-tested, function 5, GREATER).
- [A resolution family member reads another size's compressed blocks as garbage](../../../docs/reference/rendering.md#a-resolution-family-member-reads-another-sizes-compressed-blocks-as-garbage): a strobing pink / white glow after the pause menu (issue #1935); the 1600x900 HDR targets share their storage with the menu's 1440x810 ones.

## Open

- Check the death effect's tendrils with the host's alpha test (reported fixed on PR #32 with another implementation).
- Validate the unsigned IPA on an iPhone, including memory pressure and touch controls.
- Trace the tutorial's cube placeholder and validate visible effects against the original game.
- Validate later combat input windows, camera behavior and cinematic audio/video sync with the 60 fps profile; establish sustained performance without competing workloads.
- Later levels and Bink movies are untested.


## Graphics controls

**Current:** the Mac launcher exposes independent resolution, dynamic resolution,
shadow atlas, SMAA, anisotropy, texture mip bias, draw distance, model detail,
ambient occlusion, fog density, screen shape and 30/60/120-fps choices. Except for
resolution/AF/shadows/SMAA's existing Enhanced defaults, new effects retain the
original appearance until selected. Changes take effect on the next launch.
All code sites below belong only to main build `4b159f0f7a360669738390ee8657b4f0`;
rewrite and runtime manifests both assert their original bytes.

| Control | Original | Highest option and mechanism |
| --- | --- | --- |
| Dynamic resolution | Console behavior in Original automatic; fixed full scene in explicit modes | On provides the native selector three separately allocated 100/90/80-percent target families; output and HUD remain at the selected maximum. Off gives every family the maximum size. |
| Draw distance | Model's own LostDistRate | Maximum sets the disappearance threshold to zero; frustum culling and spawning remain native. Intermediate choices divide the threshold by two or four. |
| Model quality | Model's DistRate0/1/2 | Maximum retains LOD0; intermediate choices divide detail thresholds by two or four. Does not invent more detailed meshes. |
| Texture sharpness | Game sampler mip bias | Sharp / Very sharp add -0.5 / -1 to surface samplers, with 16x AF available separately. Fixed-LOD, lookup, shadow and reduction samplers stay unchanged. Negative bias can shimmer. |
| Ambient occlusion | Off; the game has no SSAO pass | Low / High / Ultra evaluate 8 / 16 / 32 view-space depth samples at half resolution, then filter by depth and multiply only the opaque scene light. The original distance fog and emissive light keep their light. Transparencies and UI follow afterward. |
| Fog density | Original | Off / Light / Original / Dense change only distance-fog inverse range (0 / 0.5 / 1 / 1.5), in a copied fragment c5 bank with verified fog layout and cube slot 12. This is atmosphere density, not additional volumetric detail. Particle fog retains its own behavior. |
| Screen ratio | 16:9 | 16:10 keeps the horizontal field of view and extends vertically; perspective and flat UI cameras, screen/world mapping and HUD anchors follow. Movies retain 16:9. Internal targets retain the game's 16:9 grid and are presented anamorphically at the camera's ratio. |
| Frame cap | Enhanced 60 fps | 120 fps on a suitable screen, with adaptive host pacing. Cinematics retain 30 fps. [Sub-60 tick ABI](../../../docs/reference/frame-rate.md#a-frame-step-stub-with-sub-60-fps-units). |

**Source research:** [captainj-sparrow/astral-chain-pc-recomp](https://github.com/captainj-sparrow/astral-chain-pc-recomp)
identified model threshold stores, camera/UI contracts and the opaque lighting,
linear depth and fog layouts. The native instructions were checked against this
NSO. UI anchor classification and inverse matrix code retain that project's MIT
notice in the profile includes. The Metal SSAO implementation is separate from
its Vulkan renderer.

**Crowd density — researched 2026-11-18, not exposed:** the binary contains `BehaviorCrowd` (a placed-object behavior; factories `main+0x393840` / `main+0x393920`), but no verified
spawn-count or population budget was found (no BXM tag or value in the RomFS carries one; particles live in 1,028 `.eff` files whose `.est` emitter layout is not decoded; roadmap rows 11). Draw distance can retain existing
people farther away; it does not increase their number. No population slider is
exposed without a validated spawning contract.



## Red speckle with anisotropic filtering (resolved 2026-11-17)

- Symptom: gameplay (Highway Rescue) showed red outlines and speckled surfaces. Not caused by the new controls: the previously installed app with every quality control original and `DM_NVN_ANISO=16` showed it; the same save and frame with `DM_NVN_ANISO=0` is clean.
- Bisect (same save, frame 9000, `DM_NVN_ANISO=16` with the floor applied to one group of samplers): trilinear samplers (min filter 5) clean and sharper; nearest-mip linear samplers (min filter 3) reproduce the speckle.
- Cause: the engine samples data-like textures through min-filter-3 samplers; an anisotropy floor (and a mip bias) on them changes the mip chosen and garbles the data. Fix: `nvn_aniso_floor` and `nvn_texture_bias` (`dm/gfx/nvn/nvn_aniso.h`) now apply only to min filter 5; `t_aniso` covers both. Verified: 3840x2160, High shadows, SMAA High, AO High, AF16 renders clean in the same scene.
- The default Enhanced AF16 setting was affected before this fix. Other games' samplers with min filter 3 no longer take the floor either; not re-measured on them.
- Still open (hypothesis, not measured): AO log reports `fog absent` in this hazy scene, so fog-light preservation is not yet proven; the remaining items of the handoff (AO offline MSL and PSO warm-up, all-mode fog/AO captures, dynamic resolution, 16:10 pixel checks, 4K/5K combat, 120 FPS in cinematics, final packaged app) are not done.

## 5K load hang, fog and AO verification (2026-11-17)

- **5K never finished loading Highway Rescue** (resolved). The game stayed on its LOADING screen with every guest thread idle (CPU 18 %, GPU 0); 4K loaded. Cause (confirmed by effect, not by an allocator trace): the GRAPHIC BUFFER heap (143 MiB inside the 173.375 MiB BUFFER ROOT, constructors at main+575c94 / main+575a30) holds one storage buffer of about 6.97 bytes per render pixel, 103 MiB at 5K. Both sizes now grow by 8 bytes per pixel above 1080p, in whole MiB, through the resolution manifest (`runtime_patches.py`); 5K then loads (CPU 56 %, game time 0.99-1.00 of real time). Site discovery: captainj-sparrow/astral-chain-pc-recomp `patches-v101.txt` (MIT); the instruction bytes are asserted against this build. The earlier dead ends for the 5K exposure race (enlarging pools) are a different problem and stay removed.
- **AO shaders are offline**: `dm/gfx/msl/ac_ao.metal` is compiled with the host (`host_msl.py`); both apply pipelines (R11G11B10F, RGBA16F) are created at the first graphics pass. No run-time MSL compile, no `[RED]` in the verified runs.
- **Fog under AO**: the fog block is voted among draws whose fragment shader reads the cube at slot 12 (stale slot bindings from other draws had been picked, hence "fog absent"); the cube is a six-layer 2D array and is sampled through a cached cube view. The log now says `fog preserved` in gameplay. AO High at 1440p/4K shows contact shading under vehicles with no dark fog silhouettes. Frames were not pose-aligned with the AO-off frames (animation differs per run), so no pixel diff exists.
- **Measured (packaged app, M4 Max, copied save, Highway Rescue tutorial, windowed)**: 5K + Ultra shadows + SMAA High + AO High + model/distance Maximum + AF16 + bias -0.5: loads, clean picture, no `[RED]`/crash. 5K + 16:10 + High shadows + AO High at FPS 60: loads, HUD anchored, GPU about 10 ms in a cinematic, 1611 of 1800 frames late in one window (not sustained 60 in that scene). 1440p at FPS 120: game time 1.000 of real time with 1 tick per frame; frame time p50 9.1 ms, p95 33 ms (hitches and 30 fps cinematics not separated).
- **Not verified**: dynamic resolution transitions under load, pause/reload, 16:10 pixel proportions in the app window (raw captures are 16:9), combat at 4K/5K, 120 FPS cinematic transitions in isolation, the five-game regression (other games' source builds are missing), PCSS, contact shadows, GI, temporal AA, crowd density (unsupported, no safe budget found).

## Frame rate check in the display-link path (2026-11-17)

- Scripted runs had used direct presentation (`DM_PRESENT_LINK=0`), which hid a pacing defect of the app's own path: see [the reference entry](../../../docs/reference/frame-rate.md#a-120-hz-frame-step-games-hold-waited-in-60-hz-display-link-ticks). Fixed in `link_wait`; 30 / 60 / 120 fps measured afterwards with the window frontmost (numbers in the entry).
- Packaged app (rebuilt 2026-11-17): 30 / 60 / 120 fps give 33.33 / 16.67 / 8.33 ms medians and game time 1.000 of real time. Open: cinematic transitions at 120 are not measured in the display-link path.

## Bounce light (screen-space GI) and research results (2026-11-17)

- **Bounce light** (`DM_AC_GI`, Low 0.5 / High 1.0): the half-resolution occlusion kernel also gathers the capped lit radiance of the surfaces that occlude each point; the apply pass adds it, scaled by the non-fog, non-emissive share and 0.35 (assumed albedo), and writes the whole colour instead of multiplying. It needs the occlusion pass and runs it at Low when occlusion is Off. Only visible surfaces bounce light and the effect is subtle: fire tints nearby trucks and road. Verified in the 1440p Highway Rescue scene without artifacts or `[RED]`; not compared pose-aligned, not measured for GPU cost.
- **Not applicable (verified):** the shader map has only vertex (540), pixel (738) and compute (70) programs: no tessellation or geometry stage, so there is nothing to tessellate. No volumetric-light or caustics pass was found in a gameplay frame's pass list (not proof of absence in other scenes).
- **Shadow filtering, PCSS, contact shadows (not done):** no frame sampler has comparison enabled (`cmp=1` count 0 over a gameplay frame), so the game compares shadow depths in its own shader code. Soft or variable-penumbra shadows therefore need a rewrite of those shaders (a translator-chain change with a full shader rebuild), and contact shadows need the sun direction from the lighting constants, which is unknown. Atlas resolution (High / Ultra) is the available shadow-quality control.
- **Reflections (not done):** the frame renders a 128x128 six-face probe every frame and a 256x256 cube camera. The 128 size is an immediate (`orr w1, wzr, #0x80` pairs in `main+0x40e2e0`; earlier searched as MOV, which missed them); see roadmap row 10 for why changing one site stops the probe.
- **Particles, crowd, parallax, temporal anti-aliasing:** no density or budget constant was found (crowd: see above); parallax has no identified shader family; temporal anti-aliasing needs motion vectors the game does not provide. Left unsupported.
- **Already available:** texture sharpness (mip bias), model quality, draw distance, fog density; the launcher groups them by label prefix (Image / Shadows / Lighting / Detail).

## Game data tables (research, 2026-11-17)

The RomFS holds 82 PKZ archives (ZStandard entries) of DAT containers (`DAT\0`: names, extensions, members). 37,256 members were listed; the parameter files are `bxm` (PlatinumGames binary XML: `XML\0` or `BXM\0`, big-endian, header = u16 nodes, u16 data entries, u32 pool size; nodes of four u16 (children, first child, attributes, data index); data entries of two u16 (name, value offsets) into a string pool) and `csv`. A reader is in the work folder's `tools` (not in this repository yet).

- `ObjectParam.bxm` (1,171 files, per object): `DistRate0/1/2`, `LostDistRate` (about 20-40 % of objects override the engine defaults; the model-quality / draw-distance controls patch both the defaults and the named-object stores), `ShadowCast` (346 of 1,171 objects do not cast shadows), `DynamicCubeMapMember` (only 24 of 478 listed objects are drawn into the per-frame dynamic cube), `RimLightID`, `ASTC_Mode`, `EV_LIGHT_NO`, `InstancingOff`.
- `*_clp.bxm`, `*_clh.bxm`, `*_clw.bxm`, `*_spr.bxm` (per character, cloth parameters / header / wind / spring): `m_Num`, `m_BundleNum`, `m_BundleNum2`, `m_Stretchy`, `m_SpdRate`, `m_LimitSpringRate`, `m_ExpandMax` and per-node limits. There is no sub-step or solver-iteration field; the node chains are authored, so no density control exists.
- `CubeMapArea.bxm`, `ShadowArea.bxm`, `ShadeArea.bxm`, `ViewArea.bxm`, `GAArea.bxm` (fog / filter ids per area): volume triggers selecting prebaked cubemaps, shadow / shade regions and fog and filter ids per area; none carries a global quality value.
- Open: whether forcing `ShadowCast` or `DynamicCubeMapMember` on looks better is untested (glass and effect meshes may be excluded on purpose). Changing them needs a RomFS data overlay (same-size value edits inside ZStandard-compressed DATs, padded with a skippable frame to keep entry sizes), which the host does not have.

## Contact shadows, output filter (2026-11-17)

- **Sun direction (found, verified):** in the shadow cascade draws (square depth-only 2048+ targets) vertex constant slot 5 holds the cascade's orthographic light matrix (rows x, y, depth coefficients; last row 0 0 0 1; the three rows' scales shrink per cascade, 0.104, 0.019, 0.0013). The depth row's direction is the same for every cascade; the world has Y up, so the direction toward the sun is the one pointing up: (+0.871, +0.423, +0.250) in the Highway Rescue scene. Slot 0 of the same draws is the main camera's view block.
- **Contact shadows** (`DM_AC_CONTACT`, Low 8 / High 16 steps): the occlusion kernel marches a short ray (0.04 to 0.74 view units, quadratic spacing, per-pixel jitter averaged by the apply pass's 3x3 depth-aware filter) from each surface that faces the sun toward it and tests the depth buffer; hits darken the occlusion factor by up to 70 %. It darkens total light, not only direct light (the game has no separate direct-light target). Verified in the 1440p Highway Rescue scene: no artifacts, `[RED]`-free, effect modest at night; other scenes and cost not measured.
- **Output scaling and sharpening** (`DM_PRESENT_QUALITY`, `present.metal`): Catmull-Rom at 1:1 or larger, a box filter over each output pixel's footprint when shown smaller, optional contrast adaptive sharpening. Whole picture including the interface. Verified to render a full frame at 3840x2160 from a 2560x1440 picture without bars or artifacts; no pose-aligned comparison against the bilinear present.
- **Not done:** ambient-isolated occlusion and temporal denoising, screen-space reflections (the lighting targets' material layout is unknown), soft shadows / PCSS (shadow compares are in the game's shaders), reflection probe resolution (sizes are immediates in `main+0x40e2e0`; raising one size alone makes the per-frame face passes vanish, see the roadmap row 10) and shadow range (game code), particle, crowd, cloth and post-effect controls (see the data-table section; no quality field found).

## Temporal occlusion, screen-space reflections (2026-11-17)

- **Frame targets (texdump of a Highway Rescue frame, 1080p):** the game is not a deferred renderer. Per frame: shadow atlas; a 1920x1080 RGBA8 pair (ser 19 almost constant 0.5, 0.5 with the character's silhouette: probably motion vectors; ser 27 a screen-space sun shadow mask, white lit / black shadow); the RGBA16F scene light (ser 14, before exposure) the occlusion pass edits; SMAA edge and weight targets; the bloom pyramid. There is no roughness / normal / albedo target, so surface properties cannot be read for reflections or for splitting ambient from direct light (an ambient-share estimate needs the albedo, which is unknown: not implemented).
- **Temporal accumulation** (`DM_AC_TEMPORAL`, default on with any of occlusion, bounce light, contact shadows): the half-resolution results are ping-ponged; each pixel's history is fetched at its world position reprojected with the previous frame's view (bilinear, rejected when the stored view depth differs by more than 3 % + 0.04), blended 0.8, with the sample rotation changing every frame (eight patterns). Rejected on a camera jump over 4 units or a gap over 4 frames. Measured on the road region at 1440p, occlusion Low + bounce light (occlusion factor drawn alone, `DM_AC_AODBG=1`): frame-to-frame mean absolute difference 0.67-0.72 without, 0.10-0.11 with (6.5 times lower), mean 90.0 vs 90.5, spatial variation 11.4 vs 10.4. No ghosting seen in the factor image; fast-moving objects may lag slightly (not measured).
- **Screen-space reflections** (`DM_AC_SSR`, Low 16 / High 32 steps): in the whole-colour apply pass, pixels whose depth-derived normal points up in the world (Y up, world normal Y above 0.85) and whose Fresnel term is above 0.08 (grazing angles) march a mirror-direction ray (0.15 to 40 view units, exponential steps, per-pixel jitter) against the depth buffer; a hit adds its scene light (capped at 6) times Fresnel, a screen-edge fade and 0.5, averaged over five taps around the hit (radius 2 to 10 pixels, wider for longer rays) because roughness is unknown. Verified in the 1440p Highway Rescue scene: soft reflections of the fires and embers on slabs and asphalt, no artifacts after the blur was added (the sharp version striped rough asphalt with thin vertical lines). Sky and off-screen hits give nothing, so the game's own probe reflections remain the only source there. Cost not measured.
- **Ray tracing and HDR were built and removed (2026-11-19, at the owner's request: they did not work out for the player).** What they found stays in `ASTRAL_CHAIN_GRAPHICS_ROADMAP.md` ("RT finish", "HDR (item 14)", item 23): the geometry-capture entry point can copy a draw's clip positions inside the game's own render pass; tracing the whole scene as sun-shadow casters blackens the baked-lit road; the tone map (`1ff1c2675d4b87b1`) is a compression whose shoulder approaches 1.0 only in the limit. No code of them is in the tree.
- **Not done:** ambient-share isolation of the occlusion (needs the albedo), roughness-aware reflections (no material target).

## Sun shadow mask and motion buffer in the occlusion pass (2026-11-17)

- **Found per frame:** one pass loads two RGBA8 targets of the scene's size just before the lighting (1080p: serials 19 and 27). The hook recognizes it by that shape (two colour targets, both `NVN_FORMAT_RGBA8`, equal sizes of at least 640 wide) and keeps both; the occlusion pass binds them (1x1 stand-ins when absent).
- **Target 27 is the game's dynamic sun shadow mask** (white = not in a shadow): verified by drawing it as the occlusion factor (`DM_AC_AODBG=2`): the character's silhouette and its long cast shadow on the road are dark. It is white everywhere else, under bridges included, so it is NOT a "directly lit by the sun" signal; an attempt to weaken occlusion where it is white would have removed it under bridges and was dropped. It is used only to skip contact shadows inside a shadow that already exists.
- **Target 19 is a motion buffer of an unclear encoding:** (0.5, 0.5) means none; it holds the character and the far background layer but nothing for near ground. Its red deviation across static far pillars (-21 to -5 of 255) did not match the measured screen shift (about 38 pixels, uniform) of a camera turn, so no scale is used. It only gates history: the blend falls linearly to zero as the deviation goes from 1.5 to 7.5 of 255.
- **Measured** (road region, 1440p, occlusion Low + bounce light, factor drawn alone): frame-to-frame difference 0.14-0.16 with the gate against 0.10-0.11 before it and 0.67-0.72 without temporal accumulation. Moving-character ghosting was not measured.
- Disable both with `DM_AC_SUNMASK=0`.

## Flicker near fires, and 4K / 5K at maximum (2026-11-17)

- **Report:** shadows and lighting near the fires flickered strongly. **Measured** (1080p, 60 fps, ten consecutive frames, mean absolute luminance difference between frames, idle camera):

  | Region | effects off | all effects (before) | all effects (after) |
  |---|---|---|---|
  | ground beside the fire | 0.083 | 1.428 | 0.259 |
  | road right, no character | 0.000 | 0.180 | 0.043 |
  | ground far left | 0.001 | 0.088 | 0.051 |
  | truck side (fire light) | 1.165 | 2.342 | 1.130 |

  Per effect before the fix: occlusion alone 0.009, bounce light 0.106 (road right), contact shadows 0.110 there and 1.638 at the road centre, reflections 1.403 beside the fire.
- **Causes:** the contact-shadow and reflection rays took a per-pixel jitter that changed every frame (binary hits flipped between frames); the reflections also showed the flickering flames at full strength; bounce light follows the flames' brightness. **Fixes:** a fixed per-pixel pattern for contact shadows and reflections; reflections moved into the half-resolution kernel and accumulated with a longer history (blend 0.9 against 0.8), bounce light accumulated the same way. Residual flicker is mostly the flames' own light (bounce light 0.045 against 0.106 before).
- **4K / 5K at maximum settings (packaged app, window in front, 60 fps target, shadows Ultra, SMAA High, AF16, models and distance Maximum, bias -0.5, occlusion Ultra, bounce light High, contact shadows and reflections High, temporal smoothing, output sharpening):** 4K: no `[RED]`, GPU p50 13.2 ms, frame time p50 16.67 / p95 16.81 ms, game time 0.994 of real time (the first window includes loading). 5K: no `[RED]`, GPU p50 22.7 ms, frame time p50 23.15 ms, hold of 3 ticks (about 40 fps), screenshots clean. Memory: 3.7 GB resident / 3.7 GB GPU at 4K, 4.2 / 5.0 GB at 5K.
- **Pacing at 5K, fixed:** a hold of 3 ticks of 1/120 s on a 60 Hz link was truncated to one link tick, so game time ran 7.2 % ahead of the clock; the remainder is now carried (1 and 2 ticks in turn) and game time is 1.000 of real time. A fullscreen 120 Hz link was never affected. One run logged `[RED] audio #0: the device has not called back for 211 ms` under this load (cause not investigated).
- **Not measured:** combat at 4K / 5K, cinematics at these settings, flicker in other scenes.

## Where the remaining flicker on the truck and barrier comes from (2026-11-18)

- **Report:** the white side of the GOL truck and the concrete barrier with the orange lights, and the gravel beside it, seemed to flicker (reflections, light or shadows).
- **Method:** one scene, one run, `DM_AC_AB` turning the effects off and on every 20 frames (1080p, 60 fps, shadows Ultra, SMAA High, models and distance Maximum, AF16, bias -0.5, occlusion Ultra, bounce light High, contact shadows and reflections High, temporal smoothing on), ten consecutive frames per state. Mean absolute luminance difference between frames / share of pixels that change by more than 6 of 255:

  | Region | all effects on | all effects off | bounce light on / off | contact shadows on / off | reflections on / off |
  |---|---|---|---|---|---|
  | truck panel | 0.98 / 0.4 % | 1.88 / 3.6 % | 1.21 / 2.2 % vs 1.83 / 2.9 % | 1.36 / 1.6 % vs 2.93 / 11.2 % | 1.21 / 4.4 % vs 1.82 / 4.4 % |
  | barrier with lights | 2.49 / 4.6 % | 2.86 / 8.6 % | 1.97 / 5.7 % vs 3.11 / 7.8 % | 2.09 / 4.1 % vs 3.10 / 10.9 % | 3.10 / 7.5 % vs 2.96 / 8.1 % |
  | gravel, road right | at most 0.17 / 0.6 % in every state | | | | |

  With every effect off the same areas flicker as much or more, and the unmodified original settings (1080p, no effects) gave 1.85 / 4.1 % on the panel and 2.17 / 3.9 % on the barrier. The effects, with their temporal accumulation, do not add to it and mostly lower it.
- **Cause:** the game's own lighting near the fires: the flames' light on the surfaces changes by about one luma level per frame (mean luma of the panel drifts 95 to 101 over ten frames with the effects off), and sparks and smoke particles drift in front of the panel and barrier, which is where the changing pixels are. This is normal behaviour of the original game, not a defect of the effects.
- **Earlier flicker the effects did add** (contact-shadow and reflection jitter that changed every frame) was measured and fixed on 2026-11-17 (table above in the flicker section); the 4K / 5K runs the player watched were made before that build.
- **Not measured:** the same comparison at 4K / 5K or in fullscreen, flicker in motion (the camera was idle), shimmer from a negative texture bias on moving surfaces, and the uneven frame times of 5K (about 8 % of frames not shown in the packaged run). Any of these could still read as flicker.

## Output dithering and Lanczos scaling (2026-11-18)

- Every `DM_PRESENT_QUALITY` mode except `off` now dithers the output with one level of triangular noise (interleaved gradient noise); on the Police logo menu gradient at 3840x2160 the number of value changes along an 800-pixel line went from 6 hard steps to 311 fine ones, so the contours of the 8-bit gradient are broken up (the faint wide bands of the source remain visible). `lanczos` is a Lanczos-3 variant of the clean scaling (36 taps at 1:1 or larger, the box footprint when shown smaller).
- The temporal smoothing row left the launcher: it is automatic with occlusion, bounce light, contact shadows and reflections (`DM_AC_TEMPORAL=0` still turns it off).
- 6K and 8K were examined and not added: the render-target arena size is a 32-bit `mov w8,#imm<<16` (limit 4 GiB; 6K would need 4.5 GiB), and the exposure pyramid has nothing below 1/32, whose luminance pass takes at most 256 workgroup sums (336 at 6K). See the roadmap row.

## Graphics preset (2026-11-18)

- `DM_AC_PRESET` (launcher row "Graphics preset", basic level, default Custom) names one of `original`, `balanced` (2K), `high` (4K), `maximum` (5K), `performance_120` (2K, 120 fps) or `custom`. The host expands it at the start of `main` (`presets.inc`, compiled only into this profile): the switches the preset lists (resolution, AA, texture bias, output scaling, shadows, contact shadows, occlusion, bounce light, reflections, fog, model quality, draw distance, and the memory pool; Performance also the frame rate) overwrite the environment; screen ratio, dynamic resolution, anisotropy and the frame rate (except in Performance) stay as chosen. The twelve individual rows carry `needs=DM_AC_PRESET=custom`, so the Mac settings window draws them only for Custom.
- Verified: with `DM_AC_PRESET=performance_120` and `DM_AC_AO=ultra DM_AC_RESOLUTION=2160p` in the environment the log shows the preset line, a 2560x1440 scene, no occlusion pass and a 120 fps cap; an unknown name logs `[RED]` and leaves the individual switches. Not verified: how the Mac settings window actually draws the `needs` rows (not opened by hand).

## RomFS data experiment: ShadowCast and DynamicCubeMapMember (2026-11-18)

- **Tool:** `dm/tools/astral_romfs_shadowcast.py <clone> '<pkz:dat,...>' [field]` edits a boolean field of `ObjectParam.bxm` (0 to 1) inside a clone of the RomFS image (`cp -c`), never the original. The BXM string pool is shared, so the data entry's value offset is pointed at a pool string "1"; the DAT is recompressed with ZStandard (level 3 to 22, the smallest that fits) into its slot and the PKZ entry's stored length is updated; a result larger than the slot is skipped. Start the game with `DM_ROMFS=<clone>`. Not wired into the build.
- **Which DATs a scene loads:** `DM_FSLOG=<file>` lists reads without the archive's name for RomFS images, but (offset, length) pairs match the PKZ entry table (1,142 of the 1,793 reads of a Highway Rescue run matched exactly, so the list is incomplete). Loaded objects with `ShadowCast=0` there include `bg0001`, `bg0021-23`, `bg1010`, `bg1011`, `bg1015`, `bg101a`, `bg1024`, `bg1025`, `bg1055`, `bg1101`, `bgc000-021`, `bac00e`, `bac100`, `bac101`, `bae000`, `bh0021`, `bh1011` and many `pl04xx-09xx` costume parts.
- **Measured (1440p, Highway Rescue, same frame count):** `ShadowCast` on `bg`, `ba`, `bh` (148 DATs patched, 477 skipped for lack of a "1" string, no zero or a result larger than the slot): the shadow pass has 76 draws instead of 49. `DynamicCubeMapMember` on `bg`, `ba`, `bh`, `et`, `pl` (323 patched): the cube probe passes go from 6 (clears only, 0 draws) to 66 with 87 draws. The game loads both images without `[RED]`.
- **Verdict:** the mechanism works, but neither change shows a visible gain in the sampled night frames (the sun is weak and off screen; the fires light the scene), and both add GPU work (unmeasured). Left as an experiment. Next step if wanted: a daylight scene, side-by-side crops of metal reflections, then a GPU measurement.

## Body skeletons: no chest or hip bones (2026-11-18)

- **WMB3 layout (partly decoded from `pl0000.wmb`, 2,509,256 bytes):** header `WMB3`, version `0x20160116`, bounding box at 0x14, then (offset, count) pairs from 0x28: bones at 0x90 (87), a table at 0x1e80 (864 entries), others at 0x21e0 (4), 0x25e8c8 (13) and further. A bone is 88 bytes: u16 id, u16 parent index (0xffff for the root), local position at +8, scale, world position at +40 (x, y up, z).
- **Skeletons:** `pl0000` 87 bones (root; hip id 0 at y 1.05; spine ids 1-3 at y 1.055, 1.145, 1.245; neck and head ids 4, 5; shoulders 6-13 and 10-13...; fingers `0x100-0x112` and `0x200-0x212`; legs 14-21; twist helpers `0xA00-0xA31`; a chain `0x300-0x305` at z -0.16 to -0.28 behind the head). `pl0001` 89 bones: the same plus `0xA20` and `0xA30` at x = -0.08 and +0.08, y = 1.04, z = 0 (hip-joint helpers). `pl2100` has 128. No bone lies in front of the torso or behind the hips, so nothing exists to attach a physics chain to.
- **Consequence:** vertex weights were not decoded (no vertex can be bound to a missing bone). The engine's spring and cloth files cover only separate parts (hair, jackets, skirts), so the body needs new bones and weights in the model files (roadmap item 23, path 3) or a vertex-shader offset (path 2). Not decided which skeleton the on-screen heroine uses.

## Bloom and depth of field (2026-11-18)

- **Bloom:** a gameplay frame draws a pyramid 960x540, 480x270, 240x135, 120x67, 60x33 (at 1080p; half the scene size and smaller) with `25575ea35e5b76e1` (first level), `093c6f012b0b614f` (downsample), `11a604000cdc6878` (a blur or upsample, run on the 240, 120 and 60 levels twice) and `d2ffef89a3b9e86b` (a combine). Only `25575ea35e5b76e1` has immutable constants (`DM_AC_C1DUMP`): 0.15, 0.06, 0.004, -0.0667, 0.5866, 0.1145 then zeros. The kernels are in the shader code, so a quality control would mean a new shader.
- **Depth of field:** none in the gameplay frame. The frame's compute dispatches are `cae4a5941da3f59e` (60x120 groups at 1080p, a tiled pass) and the two exposure shaders; the title background's blur is baked into its 1600x900 and 800x450 textures.
