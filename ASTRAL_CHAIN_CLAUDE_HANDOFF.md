# Astral Chain Enhanced: handoff to Claude Code

Updated 2026-11-16. The owner wants the best attainable image quality and the highest usable graphics settings, with every supported option available in the Mac launcher's menu. Finish the work, validate the actual game, and package a self-contained Mac app. Do not equate successful compilation or the title screen with a finished quality implementation.

## Status update 2026-11-17 (second session)

- **FPS pacing bug fixed** (`link_wait` in `hle_nvn.c`): in the app's display-link path a `FPS_TICK_120` game waited in 60-Hz ticks (30 fps target = 66 ms frames). Packaged app now: 30 / 60 / 120 fps = 33.33 / 16.67 / 8.33 ms medians, game time 1.000. Scripted runs must NOT use `DM_PRESENT_LINK=0` for pacing checks, and the window must stay frontmost (a covered window stalls the display link).
- **New launcher settings:** `DM_AC_GI` (bounce light), `DM_AC_CONTACT` (contact shadows, sun direction from the shadow cascade matrices), `DM_PRESENT_QUALITY` (clean scaling / sharpening). Labels are grouped by prefix: Image / Shadows / Lighting / Detail. GI and contact shadows run the AO pass at Low when AO is Off.
- **GPU budget (user's M4 Max):** 5K + AO Ultra + GI High + Ultra shadows is 17-19 ms (30-40 fps); 4K with the same effects is 11.5-12 ms (60 fps, 120 not reachable: the frame step is integral 1/120 s ticks). 120 fps was verified at 1440p with AO / GI off.
- **Research (details in the game note):** title / menu art is 2D (1600x900 and 800x450 textures); no tessellation or geometry shaders; shadow compares are manual (no `cmp=1` samplers); game data tables live in PKZ / DAT / BXM (reader written in the session scratch, to be added to the repository if work continues); cloth / hair have no quality field.
- **Third pass (same day):** temporal accumulation of the occlusion pass (`DM_AC_TEMPORAL`, default on; AO-factor noise 6.5x lower) and screen-space reflections (`DM_AC_SSR`, grazing-angle Fresnel on horizontal surfaces, soft; game has no material target). Frame targets documented in the game note: not deferred, no roughness / normal / albedo buffer, so ambient-share AO isolation and roughness-aware reflections are NOT possible; ser 19 looks like motion vectors and ser 27 is a screen-space sun shadow mask (unused so far). Packaged app rebuilt; with every effect on at 1440p the 60 fps target holds (p50 16.6 ms, p95 18.4 ms, game time 1.000).

- **Mask and motion buffer used (fourth pass):** target 27 = dynamic sun shadow mask (contact shadows skip it; NOT a sunlit-area signal), target 19 = motion buffer of unclear encoding (history gate only). Game note section "Sun shadow mask and motion buffer".
- **Flicker near fires fixed** (static jitter for contact shadows / reflections, reflections in the half-resolution kernel with long history, bounce light accumulated longer; measured table in the game note) and the 5K hold-3 pacing remainder in `link_wait`. 4K / 5K maximum-settings runs recorded in the game note (4K: 60 fps, GPU 13.2 ms; 5K: about 40 fps, GPU 22.7 ms).
- **Open:** AO ambient isolation and temporal denoise, SSR, PCSS, probe resolution, shadow range, RomFS data overlay (`ShadowCast`, `DynamicCubeMapMember`), non-integral frame step for 60-120 fps, HDR output, MetalFX temporal.

## Status update 2026-11-17 (Claude Code session)

Resolved and verified (details and measurements: `dm/games/01007300020FA000/README.md`, sections "Red speckle with anisotropic filtering" and "5K load hang, fog and AO verification"):

- Red outlines / speckle were NOT a new-effect bug: anisotropy and mip bias on min-filter-3 (nearest-mip) samplers garbled data textures. `nvn_aniso.h` now applies both only to min filter 5. This also affected the old default AF16.
- Graphics-test link failure fixed (`dm_fps_tick_hz` weak stub in `t_host_stubs.c`); full graphics suite exit 0; 66 focused Python tests pass; `t_aniso`, `t_fstep` (89 checks) pass.
- 5K never finished loading Highway Rescue: GRAPHIC BUFFER heap and BUFFER ROOT (main+575c94 / 575a30) now grow with pixels via the resolution manifest.
- AO kernels/pipelines are offline (`dm/gfx/msl/ac_ao.metal`, host_msl); fog block is voted among shaders reading the slot-12 cube and sampled through a cube view ("fog preserved" in gameplay).
- App rebuilt with all 1,348 game shaders (`/Applications/Games/Astral Chain.app`), ad-hoc signature verified, packaged-app runs at 5K max, 5K + 16:10 and 1440p / 120 FPS load and render cleanly.

Recommended profiles (from captures, not from slider maxima): Maximum quality = 4K or 5K, High or Ultra shadows, SMAA High, AF16, AO High, models/draw distance Maximum, texture sharpness Original or Sharp (-0.5), fog Original, dynamic resolution Off, 60 FPS. Higher frame rate = 1440p or 4K, High shadows, SMAA High, AF16, AO Off or Low, 120 FPS (if the display supports it).

Still open / unverified: dynamic-resolution transitions and pause/reload; 16:10 pixel proportions in the real window and movie transitions; combat at 4K/5K; sustained 60 FPS at 5K + AO (one window had most frames late); 120 FPS cinematic transitions in isolation; offline PSO manifest (still no R/M rows from gameplay); five-game regression (other games' source builds missing); PCSS, contact shadows, GI, temporal AA, shadow filtering, crowd density (unsupported, no safe budget). The debug `[ac-ao]` passdump lines were removed except the existing pass trace.

## Workspace and rules

- Worktree: `/Users/olegraskin/games/nxnative-astral-chain-enhanced`.
- Branch: `codex/astral-chain-enhanced`; HEAD/base `7c52697ee9013ff9171e563663769038b23ebf96`, based on `codex/mp4-image-quality`, also carrying the Bayonetta enhancements.
- Original checkout `/Users/olegraskin/games/nxnative-mp4-quality` remains separate and was clean after the move. Primary repository `/Users/olegraskin/games/nxnative`.
- ALL changes in this handoff are uncommitted. Several important profile files and tests are UNTRACKED. Preserve them. User has not authorized commits. Read AGENTS.md; no commits unless explicitly requested.
- Repository text/code/documentation must be English. Speak Russian to the user.
- Fixed game addresses must remain gated by the complete verified NSO build ID and asserted instruction bytes. Fix causes; do not ship sleeps, skipped passes or disabled features as unexplained fixes.
- All extracted game files, analysis, logs and test saves belong inside the NSP folder. Do not move them into this repository. Do not print keys.
- Shared Python: `/Users/olegraskin/games/venv/bin/python3` (Python 3.14; capstone and optional Unicorn installed). Unicorn JIT and real Metal tests need normal local execution rather than a restrictive agent sandbox.
- Hardware tested here: M4 Max, 48 GB, macOS 27 / Xcode 27.2, GPU `applegpu_g16s`.

## Paths

The ACTUAL folder contains `1:2`, with a colon:

```
/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/Astral Chain [NSP]
```

Use the following abbreviations below:

- NSP = that directory.
- B = `NSP/01007300020FA000_build`.
- W = `NSP/01007300020FA000-work`.
- Original updated main NSO: `B/extract/v65536/ExeFS/main`.
- Rewritten modules/manifests: `B/patched_v65536`.
- RomFS: `B/extract/v65536/RomFS.img`.
- Keys path: `/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/prod.keys` (never print contents).
- Game/update: Astral Chain 1.0.1, title `01007300020FA000`, update v65536.
- Main build ID: `4b159f0f7a360669738390ee8657b4f0` followed by 32 zero hex digits in the 32-byte NSO field.
- Installed app: `/Applications/Games/Astral Chain.app`.
- Separate older packed app used by source-test runner for its shader/resources: `NSP/Astral Chain Enhanced.app`.
- User save: `/Users/olegraskin/Library/Application Support/nxnative/01007300020FA000/save`.
- Source test runs use COPIES of this save. Never write experiments into the real save.

## Full game-shader/app build command

Run from the worktree:

```bash
cd /Users/olegraskin/games/nxnative-astral-chain-enhanced

/Users/olegraskin/games/venv/bin/python3 scripts/build_ipa_from_nsp.py \
  '/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/Astral Chain [NSP]' \
  --keys '/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/prod.keys' \
  --platform mac-app \
  --app-name 'Astral Chain Enhanced' \
  --out '/Applications/Games/Astral Chain.app' \
  --no-seen-shaders \
  --require-complete-shaders \
  --prebake \
  --progress lines
```

`--no-seen-shaders` requests the entire shader map rather than only observed programs. `--require-complete-shaders` stops before packaging on missing shaders, required variants or known translation loss. All 1,348 game shader keys have compiled successfully, shader chain `b6aa8fd968b7`. Valid cached compilations are reused; this is still a full build, not a partial seen-only build. There is no verified `--force` flag on this builder.

`--prebake` requests offline pipeline prewarming in addition to the GPU archive. The current Astral profile's `pso_manifest.tsv` has no R/M rows, so it does NOT yet give comprehensive offline PSO coverage. The current GPU archive is about 65.2 MB. Expand the manifest from real gameplay for better first-run behavior.

IMPORTANT: the NEW optional AO currently compiles its host MSL source and its pipelines lazily at first use. Therefore, while the command covers ALL original game shaders, the current code does NOT yet fulfill literally zero runtime compilation for every new effect. Move the AO kernels/vertex/fragment shaders into the existing offline host-MSL workflow (`dm/gfx/msl`, `host_msl.py`, `host_lib`) and prewarm its quality/format variants before declaring complete offline compilation.

The last successfully installed app predates the new AO/fog and final source adjustments. Do not claim the installed app already contains every latest setting. Rebuild after remaining fixes. Cached app builds have taken roughly 1–2 minutes, with ad-hoc signing often 30–60 seconds. The first execution of a newly signed large app may take tens of seconds in OS validation with an empty log.

## What was completed before this last graphics-controls request

1. Separate worktree, moved beside `~/games/nxnative` at the owner's request.
2. Build-checked launcher resolution choices: original automatic, native 1600x900, 1080p, 1440p, 4K 3840x2160, 5K 5120x2880. Constructors, output getters, scene families and the render-target arena agree.
3. Shadow atlas choices: Original 2048, High 4096, Ultra 8192. Four shadow tiles are 1024/2048/4096 each. Exact extra D24S8 storage is reserved (48 / 240 MiB for High / Ultra).
4. Original SMAA, High SMAA, Off; High lowers edge threshold from .1 to .05 and increases search bounds from +/-31.8 to +/-63.8. Immutable constants changed only for verified shader hashes; passes remain intact.
5. AF up to 16x, 10-GB address-space game pool, per-profile launcher defaults. Enhanced defaults remain 4K / High shadows / SMAA High / AF16 / FPS60; newly added effects default to original behavior.
6. Two REAL 5K root causes were fixed:
   - Exposure compute reduced an oversized 1/16 image into a FIXED 256-float buffer; 5K dispatched 920 workgroup sums, 4K 510. The final reducer also accepts only 256 values, so merely enlarging the buffer was insufficient. At 4K/5K one extra native downsample fills the existing 1/32 image, used with matching dimensions/uniforms: 5K 20x12=240 sums, 4K 15x9=135.
   - RHI retirement freed resources whose CPU initialization was still queued. The collector now acquire-checks the pending flag at EVERY node, including the inner loop's back-edge, and worker completion is a release-store AFTER its last object access. The guard MUST remain at main+9db704, not 9db700. Pending exit goes to 9db730, not 9db73c.
   No 30-fps workaround, extra sleeps or GPU-finish workaround shipped.
7. A 120-second self-contained installed-app test at 5K / Ultra shadows / High SMAA / windowed passed intro transitions without RED/crash. A separate 4K run passed. Later combat was not validated in those old runs.

## New controls implemented in source during this turn

### Model detail / draw distance

- `DM_AC_MODEL_QUALITY=default|x2|x4|high`.
- `DM_AC_DRAW_DISTANCE=default|x2|x4|high`.
- Stores in default model initialization: 551df0 / 551e0c / 551e28 / 551e44.
- Named-model stores: 55f0ec / 55f134 / 55f17c / 55f1c4.
- DistRate0/1/2 control detail transitions; LostDistRate controls disappearance. Separate manifests and helpers prevent one setting overwriting the other.
- x2 / x4 divide thresholds by 2 / 4; Maximum sets them to zero. Model Maximum retains LOD0; draw-distance Maximum removes that distance-loss threshold. Frustum culling and actual object spawning remain native. No new meshes or additional NPCs are invented.
- Helpers preserve q30/q31, inputs and NZCV; ARM execution tests exercise all source/slot/factor combinations.

### Dynamic resolution

- `DM_DYNAMIC_RESOLUTION=0|1` with fixed resolution choices.
- Resolution manifest variant `_1` gives native selector separately allocated 100/90/80% scene families, rounded to the game's 32x18 allocation grid. Output/UI stay at the selected maximum.
- Off keeps all three families at maximum. Original automatic keeps original console behavior.
- Need a final native run with On, including pause/reload, and confirm the controller's actual lower-level transition under load. Do not claim this transition was measured yet.

### Texture sharpness

- `DM_NVN_TEXTURE_BIAS=0|-0.5|-1`: original / sharp / very sharp.
- Generic opt-in surface sampler offset in `nvn_aniso.h` / `nvn_mtl.m`.
- Excludes comparison/reduction samplers, fixed-LOD, nearest filtering and non-mipmapped screen-space reads. Parsing rejects NaN/out-of-range/junk.
- Negative mip bias can shimmer; highest sharpness is not automatically the best image in motion. No HD texture assets have been added.

### 16:10, including UI

- `DM_AC_SCREEN_RATIO=default|1610`, separate from MP4's crop setting.
- Uses a taller camera retaining horizontal view, NOT MP4's 5%-per-side crop.
- Perspective lens aspect/FOV, visibility cone, interface-camera refresh, world/screen coordinate viewport, flat UI camera 1, layer camera selection and HUD anchors adjusted.
- Internal targets retain the native 16:9 allocation grid; presentation uses the chosen camera aspect anamorphically. Movies/fixed cinematic state retain 16:9.
- Private `nxnativeAcAspectV1` entry via verified nvnBootstrapLoader PLT main+a0e7b0. Every scalar/vector register and NZCV is spilled/restored. Tests simulate a host call clobbering all volatile state.
- Native helper include `nvn_runtime.inc` retains upstream MIT notice. Fixed address accesses are build-gated again in C.
- Loaded real Highway Rescue scene using copied user save; HUD, minimap, mission text and menus were visible. Further pixel/proportion comparison, camera motion, menus and movie transitions are still warranted.

### 120 FPS

- Profile declares fps_max=120; menu offers 30 / 60 / 120 on Mac.
- New VERIFIED frame-state capability `FPS_TICK_120`; loader records 120-Hz unit only for such stubs. Legacy games keep 60-Hz units and their old max step of 3.
- Astral step: one tick = .25 of a 30-Hz game tick. Fractional carry still feeds integral timers. Fixed cinematics request four 120-Hz ticks = 30 FPS.
- Shared pacer storage now allows six ticks, but its default bound remains 3 for legacy units. State-page 120 FPS permits payback; engine-native 120-FPS games retain their old no-payback behavior.
- Screens below 120 Hz get a 60-FPS cap; movies/thermal limits are respected.
- ARM tests passed 120 frames -> exactly 30 integral game ticks, initial target handling, original 30/60 tests and cinematic transitions.
- Native title p50 ~8.33 ms. Highway Rescue logs repeatedly show 1,800 hold-1 frames and game/real time ratios 0.999–1.001. This is NOT a claim of 5K/Ultra AO/120 FPS together, nor broad combat validation.
- There is a remaining full graphics test LINK failure because fixtures do not yet define the new global `dm_fps_tick_hz`. Fix the common test stubs with its legacy default 60; do not alter production semantics merely to make fixtures link.
- Consider gating Astral's 120 launcher option by the verified fixup too: currently the general option uses profile fps_max=120. Unknown/derived builds must not advertise an unsupported step ABI.

### Ambient occlusion (new, needs final QA)

- `DM_AC_AO=off|low|high|ultra` = original / 8 / 16 / 32 samples.
- New native Metal SSAO in `graphics_runtime.inc`; half-resolution view-space depth sampling, depth-aware composition, multi-bounce softening and distance fade; applied to opaque lighting before transparent effects / bloom / UI.
- Copies scene lighting before composition; uses a multiply blend, with fog light and bright emissive contribution protected.
- The game has no native SSAO pass to simply increase; this adds a new effect.
- Both compute and composition shaders compiled successfully on the real GPU with `/tmp/check-ac-ao.m` and `/tmp/ac-ao.metal`.
- Native run `controls_ao_bankfix` succeeded bounded, without RED/crash, and logged `2560x1440 scene, 1280x720 occlusion, 32 samples`.
- IMPORTANT correct API contracts discovered during validation:
  - Main depth is NVN D24S8 converted by Metal to D32F(S8); accept this source format.
  - NVN SetRenderTargets often supplies n=4 with only color[0] populated. Count active attachments, not n==1.
  - Shader c3/c5 map to NVN USER uniform slots 0/2 (bank minus 3), NOT user slots 3/5. Camera capture now uses S.ubo[0][0], fog S.ubo[1][2]. `dmsh_reflect.py` confirms reg=n-3.
- Last source-only edit refined the bright-surface fog formula to the game's luminance weights and soft transition, and added a limited fog-present/absent state log. That exact final edit has NOT yet had a native app rebuild/run.
- First successful AO log said `fog absent` (title); verify that the real world is later recognized as fog-preserved, with before/after captures. Current fog capture picks a late draw, not a majority-voted fog block. Consider tallying c5 + cube bindings like camera voting to prevent incidental bindings overriding the main fog.
- Current SSAO changes ambient-looking contact shading but does not isolate the ambient-light term using the game's ambient cube. Improve this for maximum fidelity, avoid darkening direct illumination; consider upstream's ambient-share/multi-bounce approach and optional GI after basic AO is proven.
- It currently compiles host MSL/pipelines at runtime. Move to offline host-MSL compilation and prewarming as noted above.

### Fog

- `DM_AC_FOG=default|off|light|dense`.
- It is a DENSITY control, not invented volumetric quality: native distance-fog inverse range multiplied by 1 / 0 / .5 / 1.5, on copied GPU uniforms only.
- Applies only to fragment user uniform slot 2 (hardware c5), plausible 80-byte fog parameters, and shaders reading cube slot 12. Main build gated.
- Scripted particles/fog retain their own behavior. Keep the label honest; more fog is not more graphical detail.
- First light-fog run predates the corrected bank mapping, so its visual result is NOT validation of the corrected implementation. Must test Off/Light/Default/Dense with the final code.

### Crowd density

- Binary string search found `BehaviorCrowd` at main+b74edf, but no verified population/spawn budget or count setting.
- Intentionally no fake density slider. Higher draw distance only retains already existing people farther away.
- Claude can trace registration/xrefs of BehaviorCrowd, its scene parameters and object factory, then disassemble and validate a safe population budget. Do not change story NPCs or spawn arbitrary actors based on a guessed integer.

## Material open visual issue

Gameplay screenshots contain pronounced reddish outlines / speckled surface detail. This is visible both with new enhancement settings and in `controls_ao_isolated`, where model/distance/sharpness/AA/fog were original and AO had not yet been applied because of its old detection bug. Thus it is not proven to be caused by a particular new control.

DO NOT silently declare the picture pristine. Compare with a true original-resolution baseline and prior branch/app, and investigate the first pass that introduces the pixels (capture target images / native MSL / texture formats / material constants / blend and depth behavior). The title/intro-only earlier 5K tests did not establish full gameplay image correctness.

Useful screenshots:

- W/controls_ao_gameplay/live_gameplay.png — 16:10 Highway Rescue HUD, visibly speckled surfaces.
- W/controls_ao_isolated/quality_9000.png — 16:9 Highway Rescue with original quality controls, same visual issue.
- W/controls_120_gameplay/quality_2700.png — title at 120.
- W/controls_ao_bankfix/quality_6000.png and quality_9000.png — AO-active run, inspect next.

## Test runners and logs

`W/run.py <run-name> <seconds> KEY=VALUE ...` starts `B/tools/dmhost` against `B/patched_v65536`, RomFS image, and shader resources from the older `NSP/Astral Chain Enhanced.app`. Saves/temp/log/control are isolated under `W/<run-name>`. It stops gracefully after the requested wall time.

After a direct `make -C dm/host GAME=01007300020FA000 -j8`, copy the new `dm/host/dmhost` to `B/tools/dmhost` BEFORE using run.py. The NSP builder does this itself.

Keyboard injection is frame-based or time-based. A tested faster route on the copied Highway Rescue save:

```
DM_KEYS=f1800:ZL+ZR~f60,f2000:A,f2200:A,f2400:A,f2600:A,f2800:A,f3000:A,f3200:A,f3400:A,f3600:A,f3800:A
```

Use `DM_NVN_SHOT=6000,9000:quality_%d.png`. Append commands to the run's `control.txt`:

```
shot live_gameplay.png
passdump 1
A
PLUS
```

`DM_WINDOW=1 DM_PRESENT_LINK=0 DM_SAVE_SYNC=0` used in test runner; the app's normal display-link behavior also needs a final test. Old debug scripts in `W/fivek-analysis` may still reference the PREVIOUS source checkout path; fix before reuse.

- Focused Python checks: **66 passed**, latest log W/validation/controls-focused-tests.log.
  Command: `venv/python3 -m unittest dm.tools.tests.test_astral_quality dm.tools.tests.test_astral_fps dm.tools.tests.test_settings dm.tools.tests.test_runtime_patch dm.tools.tests.test_docs`.
- t_fstep earlier 86 checks passed; three new 120-Hz cinematic tests were added afterward. Re-run them.
- t_aniso passed; includes new sharpness parsing/sampler exclusions.
- FULL graphics suite currently FAILS at link time on missing `_dm_fps_tick_hz` in fixtures: W/validation/controls-gfx-full.log. Fix fixtures and rerun `PATH=venv/bin:$PATH make -C dm/gfx/tests GAME=01007300020FA000 -j8 run`.
- Native AO: W/controls_ao_bankfix/log.txt; bounded run exited 0; no RED; successful 32-sample AO; game-time ratios ~1.
- Full app was not rebuilt after final new effects/source edits.
- Requested five-game regression: Astral, Bayonetta 3, MP4, Mario Odyssey, BOTW. Four local source Mac builds are missing; log W/validation/controls-regress-five.log. Do not call this passed.
- Available Astral static regression: PASS, 1,348/1,348, no translation/interface changes. Report W/regress/reports/20261116-232835-chain/report.json. This checks game shader translation, not new host AO image correctness.
- Previous full Python suite had inherited failures unrelated to Astral (environment inventory / MP4 diagnostics); previous Python lint had eight inherited findings. Rerun appropriate checks and separate new regressions from those.
- No shader translation chain tools changed in this turn; do not bump the chain arbitrarily. If changing them, follow AGENTS: regenerate dmsh_chain.h, rebuild all Astral shaders, host and required regressions.

## Files to inspect first

Untracked but essential:

- dm/games/01007300020FA000/runtime_patches.py
- dm/games/01007300020FA000/shader_runtime.inc
- dm/games/01007300020FA000/nvn_runtime.inc
- dm/games/01007300020FA000/graphics_runtime.inc
- dm/tools/tests/test_astral_quality.py

Main modified files:

- profile README.md, game.tsv, patches.py
- dm/games/settings.tsv, settings.py, dm/games/README.md
- dm/gfx/nvn/hle_nvn.c, nvn_mtl.m, nvn_aniso.h, nvn_fstep.h
- dm/host/dm.h, hle.h, loader.c
- dm/tools/patch_nso.py (state ABI documentation only)
- tests: test_astral_fps.py, test_settings.py, t_aniso.c, t_fstep.c
- docs/reference/frame-rate.md, packing.md, docs/env_switches.tsv, generated symptoms.md and game-patches.md

## Suggested order for Claude Code

1. Read AGENTS and this handoff; inspect the complete tracked AND untracked diff. Preserve existing 5K root fixes.
2. Fix graphics-test fixture definition of `dm_fps_tick_hz=60`, run full graphics tests and focused Python tests. Check new pacer assertions and unknown-build FPS availability.
3. Inspect successful AO screenshots; validate correct fog and ambient-light handling. Move AO into offline host-MSL / PSO warmup. Test all AO and fog modes on a static scene and in motion.
4. Establish a true original baseline for the red/speckled gameplay image and fix its root cause if it is a renderer error. Better resolution cannot hide a wrong material/shader/depth result.
5. Validate dynamic resolution On/Off and actual controller transitions, pause/reload, memory allocation and every launcher option. Confirm 16:10 geometry/UI/markers and cinematics, using the normal app presentation path too.
6. Validate 4K and 5K with Ultra shadows, Maximum LOD/draw distance, AF16, AA High, AO High/Ultra. Measure actual GPU/frame time and memory after loading an on-foot scene and during combat. Do not promise simultaneous 5K + all Ultra + 120 FPS without measurements.
7. For best image quality, compare AA quality in motion: native SMAA High versus higher rendering resolution/downsampling; negative mip bias may need a modest setting rather than -1. Investigate larger shadow distance/cascades, contact shadows/PCSS, higher-resolution reflections/fog where actual passes support it. Optional GI is a later improvement, not already implemented.
8. Trace BehaviorCrowd only if a safe count budget can be demonstrated; otherwise explicitly leave this unsupported.
9. Expand gameplay PSO coverage and produce the final self-contained app with all 1,348 game shaders, offline auxiliary shaders and warmed pipelines. Verify ad-hoc signature, launch from the packaged app itself, and test the menu choices persist/restart correctly.
10. Update the game note with measured configurations and remaining limitations; report unavailable cross-game checks honestly. Do not commit unless owner asks.

## Primary research source

Local MIT source clone: `W/research/astral-chain-pc-recomp`.
Commit: `919cc97777ce614acd87fbbd0f80ba7356d9a578`.
Upstream: https://github.com/captainj-sparrow/astral-chain-pc-recomp
Relevant: `recomp/patches-v101.txt`, `runtime/resolution.c`, `runtime/vk_ao.c`, `runtime/shaders/ao*.comp`.
Original timing research: https://github.com/yogesh1239/AstralChain-Dynamic-FPS/tree/79965b4df077f64b27b74456d0db88c6afac5bbe
Original resolution discovery: https://github.com/Puddz/AstralChain-PC

Native code and Metal implementation were adapted to this repository; no foreign Vulkan runtime or game assets were imported into it. MIT notices are retained where source was adapted.


## Extended technical context for a reader with no prior conversation

This addendum distinguishes **implemented**, **locally observed**, **upstream research**, and **hypothesis**. A code path or menu entry is not proof of correct graphics. The earlier handoff remains the work-state snapshot; this documentation-only follow-up does not rebuild or fix production code.

### What this program actually is

This is NOT a Switch emulator configuration or a conventional PC port with engine source. The Switch game's ARM64 code executes natively on Apple Silicon. `dm/tools/patch_nso.py` rewrites platform-sensitive instructions; `dm/host` supplies Horizon kernel/services; NVN commands are recorded in `dm/gfx/nvn/hle_nvn.c` and replayed on Metal in `nvn_mtl.m`. Shader programs originate in the game's assets and are translated offline. Consequently, a real graphics setting must change an identified engine value, resource-allocation contract, shader input or a deliberately added renderer effect.

The source branch already contains work from `codex/mp4-image-quality` and Bayonetta enhancements. Reuse the infrastructure, not game-specific addresses or assumptions. MP4's 16:10 implementation crops the original picture and fits its UI; Astral's new 16:10 implementation changes the camera and projection instead. They are deliberately separate settings.

Read in this order:

1. Repository AGENTS.md and this handoff, then `git status --short` and the ENTIRE diff including untracked files.
2. `dm/games/01007300020FA000/README.md`: history, baseline, root fixes and measurements.
3. `docs/agents/04-graphics.md`, `docs/agents/05-debugging.md`, `docs/agents/06-dev-loop.md`.
4. `docs/reference/rendering.md`, `shaders.md`, `nvn-objects.md`, `frame-rate.md`; use `docs/agents/symptoms.md` for an observed failure.
5. `dm/games/README.md`, `settings.py`, `settings.tsv`, then this profile's four runtime files and patches.py.

### Mechanism for launcher-selectable executable patches

`patches.py` has two distinct responsibilities:

- `FRAME_STEP[build_id]`: mandatory build-verified clock/timer/camera hooks, plus state-page capability `FPS_TICK_120`.
- `STUBS[build_id]`: mandatory RHI lifetime fixes and emitted optional helper bodies. Emitting a helper does not select its quality option. Its virtual offset is exported as `RUNTIME_<NAME>` in `main.fixups.tsv`.

`runtime_patches.py` runs after the general rewriter. It loads the pristine NSO through `nso.load`, checks the complete build ID, validates original instructions against BOTH pristine and rewritten images, checks helper bytes, then writes DMRT1 manifests:

| Manifest | Environment selector |
| --- | --- |
| main.runtime.tsv | DM_AC_RESOLUTION, variant DM_DYNAMIC_RESOLUTION |
| main.shadow.runtime.tsv | DM_AC_SHADOW |
| main.lod.runtime.tsv | DM_AC_MODEL_QUALITY |
| main.distance.runtime.tsv | DM_AC_DRAW_DISTANCE |
| main.aspect.runtime.tsv | DM_AC_SCREEN_RATIO |

The loader validates a whole manifest before any writes and applies it before sealing executable memory. `default` makes zero optional writes; mandatory safety fixes remain. Multiple manifests must not modify the same instruction under simultaneously selectable options. The common generator is `dm/tools/runtime_patch.py`, loader ABI is `dm/host/runtime_patch.h`. Current limits: 16 total choices (including default), 1,024 writes, 64 bytes per write. A Cartesian product of resolution/aspect/DR/options can exceed this; do not casually combine everything into one oversized manifest.

A variant is `<base choice>_<variant value>` and is selected only when declared. Current five resolution bases plus five `_1` dynamic variants fit. Variant 0 falls back to the base. Do not assume a `_default` variant is applied. Every declared non-default choice must have writes. Export names must be uppercase `[A-Z][A-Z0-9_]*`; lowercase detail names previously stopped rewriting and were corrected.

A large BSS can place helper code BEFORE main's module base. Never assume exported offsets are positive file offsets. `checked_stub` accounts for negative PATCH_OFF using FILE_IMAGE_LEN. A plain `image[stub:]` is wrong in that layout. Branch reach and per-build addresses must remain checked.

Launcher data is built from `dm/games/settings.tsv` by `settings.py`, then packed as `dm/launcher.json`. The Mac Swift front end consumes this generated list. Changing the table requires REPACKING the app to see new rows. Conditions use `|` for OR, `&` for AND, `runtime:DM_VAR=value`, `fixups:NAME`, platform and profile macro comparisons. No general arbitrary-expression parser exists. Runtime-choice conditions also validate manifests against the rewritten image. Per-profile `setting_default` rows have exactly environment variable and value fields; `ios|mac` is a platform-specific default. Keep unfamiliar builds and iOS from advertising unsupported controls.

### Native-to-host extension ABI for 16:10

The host already reserves names starting `nxnative` for private per-profile functions, resolved before the ordinary NVN name table. This avoids replacing genuine NVN semantics. `nvn_runtime.inc` is included only for this profile by `hle_nvn.c`. Its `nvn_profile_set_rt` can initialize presentation; it MUST NOT rewrite individual draw viewports/scissors independently.

Astral's bridge saves 0x300 bytes: X0..X30 at offsets 0..240, NZCV at 248, Q0..Q31 at 256..767. The C declaration `AcContext` is size-asserted. Its original SP is `(context + 1)`, so the original local matrix at SP+0x10 is `(uintptr_t)(context+1)+0x10`. The C helper changes only intended saved register outputs or identified game objects. It must preserve inline-hook semantics, not merely the platform's volatile-register ABI. The ARM tests deliberately clobber all volatile registers/vectors in a simulated host call.

### Verified camera and UI address map (1.0.1 ONLY)

- `main+9a30a0`: initializes a lens from dimensions. Callers: game `3a2398` (1280x720), interface `9045d4` (1280x720), cubemap `3c0ccc` (256x256). Leave the square camera alone.
- Lens pointer is `*(handle)`; game camera handle is generally at camera+0x58.
- Lens+260: viewport integer x/y; +268/+26c width/height; +270/+274 near/far; +278 aspect; +27c vertical FOV radians; +28c dirty flag. Projection matrix at +40, built through `9b28e0`.
- `9a2fa0`: build view/projection matrices. Dirty hook at `9a3004`, with lens X24, handle X23, output W8.
- Projection FOV loads `9a3010` (X24 lens) and `9a3054` (X8 lens).
- `991240`: visibility-cone function; `99132c` hook widens the angular cone.
- `9a31f0` / `9a3270`: world/screen mapping; viewport argument hook at `9a320c` / `9a327c` with lens X4, output X8.
- `main+dc1910`: pointer to interface camera handle. Its matrices are normally made only once at `9045f4`; changing its aspect alone is insufficient. Refresh through native `9a2fa0` when necessary. Eye `(640,360,-2040,1)`, target `(640,360,-2039,1)`, up `(0,-1,0,1)`.
- `main+dc2d50`: pointer to pointer to the flat-camera array. Three entries, 0x40 bytes each. Bounds at +18: left/right/bottom/top/near/far; dirty +30. `9e4030` creates them, `9e3f70` updates, `9e3f84` hook uses X19 and output W8. Keep camera 0 for full-screen effects; camera 1 fits interface layers. `9e2080` binds the camera indexed by W2.
- Layer sites `403670`, `403424`, `403644`, `403704` choose flat camera 1 for selected UI layers instead of 0. World effects that must cover the frame retain camera 0.
- HUD part update `910f60`; hook `9111d8` follows world-matrix construction. Part X19, parent transform X21, matrix original SP+10. Top-level HUD block anchors move by 40 logical pixels vertically for 1280x800 versus 1280x720; descendants inherit the move.
- UI instance: archive id +b4, UID +b8, transform +10, parts pointer +150, part count +160. Part size 470; owner +8, place +1d8, scales +1f0/+238, drawable +400, child +428, sibling +430. `main+dc18f0` gives the archive table. Only archive `hud2` is anchored; menus remain centered compositions, world markers keep their world placement.

The taller vertical angle must be `2*atan(tan(original_angle/2)*(16/9)/new_ratio)`, not a naive aspect write or linear multiplication of the FOV angle. Keep projection, visibility and world/UI coordinates coherent. A future FOV slider must compose with these same hooks rather than write a conflicting second manifest. Upstream 1.0.1 also identifies render-scene FOV copies at `998b5c` and `998f90` (store S0 to object+140); these two sites were NOT locally disassembled/implemented during this task. Verify them before using them.

Presentation currently calls `mtl_present_layer(16,10)` or `(16,9)` according to movie state. Confirm this state remains paired with the correct queued picture when the game renders ahead. Raw texture screenshots are still 16:9; they cannot alone prove on-screen pixel proportions. Compare an actual window/screen capture for 16:10. The current movie test uses `dm_movie_playing()`, which also sees fixed cinematic state; verify that intended real-time cinematics are not unnecessarily forced to 16:9.

### Exact high-resolution / allocator forensic findings

- Resolution getters: main+4328c0/+4328c8 and +4328e0/+4328e8.
- Full target constructor selections: 40d5e8/+40d5f4 and 40fb0c/+40fb18.
- Dynamic family selection blocks: 40f184 (16 bytes), 40f1a4 (28 bytes), 40f1d0 (16 bytes); actual native level creation 40fb60 and per-frame selection 4183a0 are upstream research leads, not locally validated new hook sites.
- Frame render-target arena budget instruction: 40e0b0, original 310 MiB. Current reservation scales pixels relative to 1600x900 and rounds UP to 64 KiB. 5K reserves ~3,174 MiB; plus other heaps and optional shadow storage. 10G is an address-space pool setting, not a promise the game always consumes 10 GB physical RAM.
- Exposure pyramid pointer: main+dba228. Frame path at 3ffb60; native downsample routine 99b190. Existing pyramid texture slots +40/+60/+80/+a0. Hook 3ffbf8 adds +80 -> +a0; 4066a0 makes exposure setup derive dimensions/group count/normalization from +a0. Do not change just one of these.
- Luminance shader keys `613993ce8c8986e1` (one result/workgroup) and `3dbb6d849ea0d18c` (256-thread final reduction). Fixed buffer constructor a0392c. App memory increases cannot make a 920-value write fit 256 values.
- RHI worker loop 9db200. Queue head/tag pair at manager+490 and queued count +4a8. Pending flag object+18; object links +28/+30; final worker clear at +48. Native init method `9e7510` calls NVNBufferGetAddress. Collector bucket list manager+320+bucket*16, native loop 9db6ec..9db73c, 10-node batches. Inner back-edge at 9db72c enters 9db704. This is why moving the guard four bytes earlier fails for later nodes.

Dead ends already tested for the ORIGINAL 5K failure: enlarging app pool to 16G, scaling the ~143 MiB GRAPHIC/GPU buffer heap and its ~173.375 MiB root, reducing the frame arena below 2 GiB, changing allocator classes, alias changes, and `DM_NVN_PRESENT_FINISH=1` did not fix the underlying exposure corruption / resource lifetime race. They were removed. Full GPU-command suppression under LLDB prevented the first corruption; partial small-draw suppression did not because compute still executed. Do not reintroduce these as fixes for the known original failure.

HOWEVER, fresh upstream research reports a SEPARATE later File 02 GRAPHIC BUFFER exhaustion at 4K, with a ~6.97 bytes/output-pixel storage allocation. Upstream v101 sites `575a30` (BUFFER ROOT default 0xad60000) and `575c94` (GRAPHIC BUFFER default 0x8f00000) grow those heaps. This was NOT validated on our later gameplay. Earlier failed heap enlargement is not proof that later heap exhaustion is impossible. If a later level fails, inspect actual allocator ownership/high-water/headers, verify these sites locally and diagnose it independently.

### Rendering / SSAO contracts to preserve

- Frame recognition uses full scene depth and light targets, then an R32F linear-depth pass, then opaque lighting. The first armed pass can be a color-masked visibility pass, so only run AO after the armed pass actually wrote scene color. Transparencies, glow/tonemap, SMAA and HUD come afterward.
- API attachment count can include null slots. Metal's reported pixel format numbers are NOT the original NVN format enum. E.g. observed Metal RGBA16F=92 and D32F_S8=260 do not mean guest format 92/260.
- c3 camera is NVN user slot 0, 256 bytes: view rows 0–3, projection rows 4–7, view-projection rows 8–11, inverse-view rows 12–15. Row-major CPU layout; do not transpose twice when uploading Metal constants. Camera snapshot should reflect deferred inline uniform writes, not just the guest's latest CPU bytes.
- c5 fog is NVN user slot 2. Fog row 2: start, inverse range, exponent, color scale. Row 4 .y/.z: bright-surface luminance threshold and fog multiplier. Texture slot 12 is the fog cube. Ambient cube slot 5 and c5 row1.w supply the ambient-light term (upstream research; not yet integrated into our AO).
- `ubo_read` understands deferred inline updates and staged snapshots; reading `(void*)addr` directly can pick another frame or miss an update. General `cbuf_slot` returns GPU addresses; a GPU address cannot safely be cast to a CPU pointer.
- Sky handling and depth reconstruction must use the game's depth mode (`depth_mode zero` for this build; `g_depth_zero` in Metal). Inverse projection is used for Z. X/Y also need projection off-center terms and the actual camera aspect.
- Current AO trace captures camera blocks by address and vote. Fog currently captures a late draw only; use proper voting and the shader's actual bindings before relying on it. Avoid recognizing unrelated data as fog merely because five floats happen to be finite.
- Preserve fog light: compute the fog's color contribution, subtract it from the pixel before deciding the occludable share, then apply occlusion only to that share. A blanket multiply makes distant fog dark silhouettes. Bright-surface fog transition must use the game's weights `(0.2989, .587, .114)` and continuous threshold blend.
- Current derivative selection clamps neighbor coordinates. At the last row/column it can select a zero difference in a tie and normalize a degenerate cross product. This is a CODE-REVIEW HYPOTHESIS, not a demonstrated current crash. Audit normal reconstruction and missing/singular geometry handling before adding more samples.
- Current code flushes AO on target changes only. Upstream also flushes before copies or compute dispatches. Audit the recorded operation stream; add a correct optional profile boundary hook if such a boundary can occur before the next target, rather than assuming every frame has the same ordering.
- Metal 4 has no MTL4BlitCommandEncoder protocol here: `enc_b_begin(g_cb)` returns a compute encoder with blit commands; establish queue-stage barriers. Use existing `enc_c_begin` / argument-table / arena / residency / deferred-release helpers. Restore dirty pipeline and binding state after custom work.
- `enc_c_begin` can land deferred uniforms and end a pass. Do not call custom encoders recursively from callbacks whose state is only half updated. Frame scratch must stay resident/alive until queued GPU use completes, including on a resolution change.

### Source research for future maximum-quality features

IMPORTANT SOURCE-QUALITY WARNING: this fork contains reused code/comments referring to TOTK/Link and version tables v121/v143. It is not a list of verified Astral 1.0.1 patches. The local `recomp/patches-v101.txt` sites used above were checked against our NSO; unrelated tables and generic shader rules were not. Read actual shader/binary contracts before porting anything. In particular, shadow cascade range constants and c4 deferred-light layouts below are research leads, not established values for this build.

| Feature | Where to investigate in local upstream clone | Native implementation direction / caveat |
| --- | --- | --- |
| Better shadow filtering | tools/xlate/patches/0011-shadow-filter-spread.patch; runtime/vk_exec_draw.c shadow_spread_params | Describes reducing four-tap UV offsets by inverse map scale so an enlarged map does not merely separate/soften four edge copies. Its matcher explicitly says TOTK, c56, exclude fp_c4: DO NOT transplant that matcher to Astral. Locate Astral's actual compare shaders/constants; scale only their verified texel footprint. Our current atlas size change does not yet establish that this footprint follows it. |
| PCSS / variable penumbra | tools/xlate/patches/0010-pcss-for-cascade-compares.patch; runtime/vk_exec_draw.c pcss_params | Blocker search plus receiver/blocker-depth-based comparison radius. Upstream support-buffer offsets 1408/1424 are ITS ABI, not this repo's. Its 2D-array shadow assumption may not match Astral's packed 2x2 atlas. Verify sampling layout; prevent taps crossing tile boundaries; preserve comparison, bias and reversed/forward depth. Prefer verified profile shader inputs over a global shader rewrite. |
| Contact shadows | runtime/vk_contact.c; runtime/shaders/contact_shadow.comp | Screen-space march toward the sun after opaque lighting, before transparencies. Header describes a different G-buffer/half-light/composite pipeline and c4 rows 7/8/14/44; first prove those inputs on Astral. Once identified, reconstruct ray in consistent view units, use thickness and offscreen fallback, leave shadowed/emissive/transparent contributions correct. Not implemented here. |
| Shadow distance / cascades | runtime/resolution.c res_shadow_range, references to patches-v143.txt | Research describes 20/40/80/160-unit ends and a 50–400% range. The relevant table is NOT v101 and may concern another game. Find our actual cascade splits/matrices and culling first. Increased range spreads texels across more world and can REDUCE near sharpness unless atlas/filter changes compensate. |
| More accurate AO | runtime/vk_ao.c and shaders/ao*.comp | Horizon/slice visibility model, ambient cube contribution, multibounce and thin-occluder penalty. Current native AO is a separate, simpler sampling implementation, not a full port. Improve normals, ambient-share isolation, fog preservation and temporal stability before increasing cost. Low/High quality should change integration accuracy, not arbitrary darkness. |
| Screen-space GI / bounce | runtime/vk_rc.c, shaders/rc_trace.comp, rc_resolve.comp, rc_temporal.comp, rc_view.comp; vk_ao.c | Radiance cascades reuse view-Z and a fog-removed source-light pyramid. Probes/directions/intervals grow by cascade; trace from coarse to fine, resolve against ambient. Only visible surfaces can supply light; offscreen disocclusion and history rejection need handling. Port to Metal/offline shaders, do not import Vulkan descriptors or Windows runtime. This is NOT ray tracing and is NOT implemented here. |
| Temporal AA / temporal MetalFX | runtime/vk_dlaa.c; shaders/dlaa_mv.comp; current renderer's DLSS/MetalFX paths | Upstream constructs camera and object motion vectors, jitters scene draws, runs temporal reconstruction before bloom at native size or at the scene-to-output scaling pass; HUD excluded. Apple needs MetalFX/native or a portable implementation, not Windows DLSS/XeSS DLLs. Validate motion-vector sign, pixels versus normalized units, Y direction, previous object transforms, skinned animation, cuts, jitter removal and reactive transparencies. Blindly adding jitter or history blend will ghost. |
| Supersampling / downsampling | existing 4K/5K modes, present path | A 5K internal render displayed on a smaller screen already provides a useful spatial quality route. Verify the downsampling filter and actual shown size; do not assume bilinear presentation is optimal for large reductions. Distinguish internal render size from window size and actual aspect. Keep UI crisp instead of sharpening/downsampling it blindly. |
| Texture quality / HD assets | original mip chain, sampler state, any discovered texture streaming budget | AF16 and negative mip bias use existing detail only. Find streamed residency/mip selection and allocation limits before raising texture budgets. New HD assets would require legitimate replacement sources and an asset-pack workflow; none have been provided. A guessed global LOD floor can sample unmapped levels or corrupt lookup/lighting data. |
| Higher-resolution reflections / fog effects | capture real pass graph, shaders, allocations and material constants | Not yet located as reliable quality controls. Cubemap prepass observed at 256x256, small color cubes at 128x128, and surface distance fog exist; that does not prove these are user-facing reflection/fog-quality knobs. Identify what the target feeds, format/mips/faces/storage and its cost before changing dimensions. |
| Crowd count | BehaviorCrowd string main+b74edf, its code xrefs/registration, scene resources | Follow constructor/behavior parameter readers and the spawn manager. Separate ambient crowd from mission/story/physics actors and actual active count from distance culling. Need a verified budget, stream-in/out and save/mission validation; no safe address or cap is known. |
| Free FOV slider / broader aspect support | camera/UI map above; upstream resolution.c rt_fov_* and rt_wide_* | Compose FOV and aspect in ONE projection path; update render-scene culling values as needed. Keep square reflection cameras and cutscene framing intact. Extend to ultrawide only after 16:10 is fully verified. |
| Frame rates above 120 | current FRAME_STEP clock and host unit | NOT supported by setting fps_max higher. Fallback `120/target` truncates to an integer; above 120 can become zero. 90/144 are not exactly representable as constant whole 1/120 ticks either. A finer or rational/elapsed-time ABI, integer timer carries and all consumers must be designed/tested, plus display pacing. 120 is the present verified ceiling, not a proven engine maximum. |

Upstream AO constants to understand rather than blindly copy: radius 1.5 view units/metres as described there, half-resolution scale 2, maximum reach one quarter of picture height, fade 60–120 view-distance units, power 1.5, multibounce albedo .3, squared view-direction penalty 4. Ambient cube slot 5, one level above its smallest mip; c5 row1.w is an ambient factor. Their renderer measures light/visibility and credits bright blockers rather than treating all obstructing geometry as black.

Upstream GI source specifically warns that interpolation at a depth texel's CENTER versus along the actual sample ray changes grazing-ground angles, back-facing geometry should block but not emit, and distant sky geometry must not become an unlimited light source. Its temporal history is short at probes, with depth/motion rejection still important. Published upstream GPU timings concern different hardware/resolution and are NOT our performance measurements.

### Shader compilation: three separate things

1. Game shader translation + Metal libraries: 1,348 game keys currently complete. `--no-seen-shaders --require-complete-shaders` requests/checks the full map; valid cache reuse is correct.
2. Host helper Metal libraries: `dm/host/Makefile` discovers `dm/gfx/msl/*.metal` and `dm/gfx/tools/host_msl.py` embeds compiled libraries in `gen/msl-macosx/host_msl_gen.h`. Use existing `host_lib` / `host_msl_lib` for AO rather than `newLibraryWithSource`. Inspect generator flags/toolchain rather than inventing a new compile workflow. `host_msl.m` has a source fallback that logs RED if a library was absent or incompatible; a clean final run should not take it.
3. Render/compute pipeline states: metallib completeness does not mean all PSOs are baked. PSOs depend on render target/depth formats, masks, blend, sample counts and shader variants. Astral's pso_manifest currently lacks R/M rows. Populate it with representative menus, Highway Rescue, combat, effects and later areas, then use the existing archive/prebake workflow. Pre-create new AO composition PSOs for the actual supported formats/quality specializations.

Shader chain `DMSH_CHAIN` versions translator TOOLS and ABI globally, not every tuning constant. Profile input tables participate in cache keys/stamps. A host-side feature alone does not justify faking a new chain version. If modifying any chain tool or its ABI, run `dmsh_chain.py --header`, rebuild full profile shaders and host, and run impact-appropriate regressions. Never reuse a library whose stamp belongs to different profile inputs or chain.

### Validation strategy and exact entry points

Start by fixing `_dm_fps_tick_hz` in `dm/gfx/tests/t_host_stubs.c`. This file explicitly exists for weak definitions of new host symbols linked by graphics tests. Default 60 is important; a zero default would introduce divisions by zero in tests and misrepresent legacy production behavior. Tests with their own stronger definitions must still override it. Independently audit test binaries that include hle_nvn directly.

Baseline matrix: original automatic / fixed native / 1440p / 4K / 5K; 16:9 and 16:10; FPS30/60/120. Establish one stable same-save/camera baseline, then change ONE setting. Follow with the combined maximum case. For AO/fog/shadows compare linear/HDR intermediate targets as well as final PNGs; autoexposure can otherwise mask a wrong lighting change. Motion matters for texture shimmer, temporal AA and PCSS.

Run the existing focused command from the earlier section; do not stage files just to make a tracked-file inventory test discover new untracked code. Re-run the graphic suite with the shared venv on PATH; system Python 3.9 cannot run some fixtures using newer type syntax. Check exact exit status and summary; one passing subtest does not make `make run` passed. Focused ARM tests do not replace gameplay tests.

Available native runner configuration example (after copying built host to B/tools/dmhost, and using copied test save):

```bash
/Users/olegraskin/games/venv/bin/python3 \
  '/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/Astral Chain [NSP]/01007300020FA000-work/run.py' \
  claude_quality_test 120 \
  DM_AC_RESOLUTION=2880p DM_DYNAMIC_RESOLUTION=0 \
  DM_AC_SHADOW=ultra DM_AC_AA=high DM_NVN_ANISO=16 \
  DM_AC_MODEL_QUALITY=high DM_AC_DRAW_DISTANCE=high \
  DM_NVN_TEXTURE_BIAS=-0.5 DM_AC_AO=high DM_AC_FOG=default \
  DM_AC_SCREEN_RATIO=1610 DM_FPS_TARGET=60 DM_APP_POOL=10G DM_WINDOW=1 \
  'DM_KEYS=f1800:ZL+ZR~f60,f2000:A,f2200:A,f2400:A,f2600:A,f2800:A,f3000:A,f3200:A,f3400:A,f3600:A,f3800:A' \
  'DM_NVN_SHOT=6000,9000:quality_%d.png'
```

This is a proposed combined quality TEST, not a previously measured configuration. At FPS60, frame-based keys and shots take longer; inspect the live log and use control.txt as needed. Screen-space UI can remain visible in a wrongly proportioned raw screenshot; inspect actual app presentation as well.

Before maximum settings, run the original baseline with all optional variables original/default and the same save. No MSL debug highlighting was inherited in the inspected environment: DM_NVN_HILITE and DM_NVN_MAGSCAN were unset. Red speckling appeared before corrected AO was active and with original quality toggles, but there is STILL no conclusive pristine original-resolution comparison. Avoid declaring either a new regression or a preexisting bug without that comparison.

Regression five-game command (currently missing four source builds):

```bash
/Users/olegraskin/games/venv/bin/python3 scripts/regress.py \
  --root '/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images/Astral Chain [NSP]/01007300020FA000-work/regress' \
  --games-dir '/Users/olegraskin/Downloads/Nintendo Switch 1:2 — images' \
  check --baseline 7c52697ee9013ff9171e563663769038b23ebf96 \
  --games 01007300020FA000,01004A4010FEA000,010019A01E2F2000,0100000000010000,01007EF00011E000 \
  --no-smoke
```

`--no-smoke` is static validation only. An installed app does not supply the extracted/source Mac build that this harness needs. If only Astral is available, run that ID alone and record the missing others; do not fabricate PASS. After packing, verify `codesign --verify --deep --strict '/Applications/Games/Astral Chain.app'` and execute the HOST/ROMFS/SHADERS FROM THE APP, not the external development artifacts. W/fivek-analysis/installed_run.py demonstrates that isolated packaged-app test; inspect its paths first.

Refresh documentation only with the matching generators: `python3 dm/tools/docs_patches.py` for patch index, `python3 dm/tools/docs_symptoms.py` after reference findings. New game-specific measurements go in the game note; reusable mechanisms in docs/reference with a link from the game note. Keep this handoff synchronized with resolved/open status so another reader does not repeat abandoned experiments.

### Quality goal and completion criteria

The owner wants the highest attainable IMAGE QUALITY, and access to the highest meaningful settings; this is not a request to maximize every arbitrary number regardless of appearance. Give them a proven maximum-quality configuration and a separate optional maximum-FPS configuration. Disable dynamic resolution in the quality preset; choose native supersampling, AF16, well-filtered high-resolution shadows and stable AA. Dense fog, -1 mip bias, oversized cascade range or overly strong AO may look worse than a moderate physically consistent setting. Keep those controls available with honest labels, but recommend from captures and motion measurements.

Done means: a correctly rendered, self-contained Mac app; no unresolved new crash/resource errors; all implemented options visible and persistent in the launcher; final build has all game and auxiliary shaders compiled with representative PSOs warmed; 4K and 5K tested in gameplay, 16:10 UI/camera verified, 120-FPS timing and cinematics correct; reports name exactly what was measured. Crowd count, additional GI, contact shadows or higher-than-120 FPS remain explicitly unsupported until a real implementation is validated. Do not expose placeholder switches.
