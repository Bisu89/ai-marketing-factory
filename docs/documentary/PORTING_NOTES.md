# Porting notes — 3 capabilities ported from `stickman-video`

Source repo: `C:\Users\hoavx\Desktop\stickman-video` (a separate, unrelated Remotion skill on this
machine). Nothing is imported across repos — only technique/code is read and manually re-typed into
Vox's own files, in Vox's own visual language. No new cross-repo dependency exists after this change.

Read before writing any code (per the task brief): `CLAUDE.md`, `docs/documentary/{README,ARCHITECTURE,
PROVIDERS,COSTS}.md`, `content-prompts/vox_documentary_template/HANDOFF.md`, `remotion/src/{schema.ts,
presets.tsx,collage.tsx,cinematic.tsx,theme.ts,Documentary.tsx,Root.tsx}`, `backend/app/modules/documentary/
{render.py,render_plan.py,storyboard.py,models.py,schemas.py,router_storyboard.py,media.py}`, and the
stickman-video reference files named in the brief (`scripts/gen_audio.py`, `assets/engine/{weather.tsx,
crowd.tsx}`, `references/engine-api.md`).

## A. Synthesized SFX for scene-cut cues

**The gap this closes:** `DocumentaryScene.sfx_cues` already exists in the model, the API
(`SceneUpdate.sfx_cues`), and the Storyboard tab UI ("Gợi ý hiệu ứng âm thanh") — a free-text hint
the user can already type per scene. It has had **zero effect on the render** since it was added
(migration `0011`): nothing reads it at mux time. This is exactly the "chưa làm: SFX" line in
`HANDOFF.md`. Instead of inventing a new field, this wires the existing one up.

- **Dependency decision:** `gen_audio.py` uses `numpy` + `scipy` (Butterworth filters). This repo's
  venv already has **numpy 2.4.6** installed (a transitive dependency of `faster-whisper`/
  `ctranslate2`) but **no scipy**. Pinning numpy explicitly in `requirements.txt` costs nothing (it's
  already present); adding scipy would be a genuinely new dependency for one `butter`/`sosfilt` call.
  Decision: **numpy only**, with a hand-written one-pole IIR low/high-pass replacing
  `scipy.signal.butter` — plenty for a < 2s noise-based transition cue, not a mixing-console filter.
  New file: `app/modules/documentary/sfx.py`.
- **Catalog, not per-scene generation:** 4 fixed styles (`whoosh`, `impact`, `stinger`, `wind`),
  synthesized once into `<library>/_documentary/_sfx_cache/{style}_v{N}.wav` and reused by every
  project (same seed ⇒ same file; `_vN` suffix invalidates the cache if the synthesis ever changes,
  mirroring `PIPELINE_VERSION` in `render_plan.py`).
- **Mapping a hint to a style:** `sfx.match_style(hint)` keyword-matches the user's free text
  (English + Vietnamese words) against the 4 styles, falling back to `"whoosh"` for any non-empty
  hint that names no known style — so *any* hint the user already typed produces a cue; nothing is
  silently dropped, and nothing is invented for a scene with no hint at all.
- **Where it's inserted:** `render_plan.build_sfx_cues(db, project_id, sfx_db)` turns every scene
  with a non-empty `sfx_cues` hint into one `{style, start_sec}` cue at that scene's real cut-in time
  (from `DocumentarySceneTiming`, the same timeline used for everything else). `render.mux_command`
  gained an optional trailing `sfx_cues` parameter that adds each cue as its own ffmpeg input, delayed
  with `adelay` and mixed in under the narration (`amix`) — the same technique
  `app/modules/video_composer/audio_mix.py` already uses for its own (unrelated, Video Factory) SFX
  cues; read for the pattern, not imported (documentary must not import other modules).
- **Default off:** `RenderParams.sfx_enabled: bool = False`, `sfx_db: float = -14.0`. Mirrors how
  `music_path` is optional. The old no-music/no-sfx code path in `mux_command` is untouched
  character-for-character (verified by keeping `MusicMixTests.test_command_shape` green), so every
  existing render stays bit-for-bit reproducible.
- **Cache correctness:** `build_manifest`'s input-hash digest now folds in a hash of every scene's
  `sfx_cues` text **only when `sfx_enabled`** — so turning the feature on, or editing a hint while
  it's on, forces a fresh render; leaving it off never invalidates an existing cached job just because
  someone typed a hint.
- **Exposed through:** `RenderIn` (API), and a minimal checkbox + dB picker in `RenderTab.tsx`,
  mirroring the existing music block.
- **Not done (explicitly out of scope for this task):** no per-cue style override in the UI (the
  mapping is automatic from the existing hint text); no music-style "duck the narration" — SFX cues
  duck nothing, they just sit under the voice at a fixed low level.

## B. `TacticalMap` preset — a diagram, not a decorative map

- `MapZoom` (existing) is explicitly decorative when there's no user-supplied map image
  (`Contours`, abstract seeded ellipses) — `HANDOFF.md` already says so ("chỉ nền đường đồng mức
  trang trí"). This task does not touch `MapZoom` or try to give it real geography (no geo data
  source exists in this app and adding one is out of scope).
- Instead, `TacticalMap` is a **new, 10th preset**: a schematic troop-movement/sequence-of-places
  diagram — labelled unit blocks connected by drawn-on arrows, built entirely from the scene's own
  `texts[]` (role `label`) and a deterministic seeded layout (`scene.key`), the same
  "no real coordinates, honestly a diagram" approach `EvidenceBoard`/`TimelineBuild` already use for
  non-geographic data.
- Looked at `crowd.tsx` for the general technique (deterministic seeded positions, a formation laid
  out from a count) and `engine-api.md` for vocabulary, but **did not** port its stick-figure
  `Soldier`/`Formation` components — they're drawn in stickman-video's own character style, which is
  not Vox's collage/cinematic look. The "unit" is a plain two-tone rotated rectangle (a NATO-style
  unit block), not a person, consistent with every other Vox preset being flat paper/ink/photo, never
  a cartoon figure.
- Registered in all 4 places a preset name has to exist (confirmed by reading, not guessing):
  `remotion/src/schema.ts` (`PRESET_NAMES`), `remotion/src/presets.tsx` (`PRESET_COMPONENTS`),
  `backend/app/modules/documentary/storyboard.py` (`PRESETS`, `PROGRAMMATIC_PRESETS` — it draws
  nothing from an image), `backend/app/modules/documentary/schemas.py` (`VisualPreset`). Also added
  to `derive_texts()`'s `MapZoom`/`ArchivalPortrait` branch (now `MapZoom`/`ArchivalPortrait`/
  `TacticalMap`) so a scene assigned this preset with no manually-typed `on_screen_text` still shows
  the proper noun from its own narration, exactly like `MapZoom` already does.
- **Not** added to `DATA_PRESETS` (`render_plan.py`): that set exists so a scene with literally no
  derivable text doesn't render blank. `TacticalMap` already degrades to a 2-point generic diagram
  with empty labels rather than a blank frame, so the redirect-to-`HeadlineImpact` safety net isn't
  needed for it.
- Frontend: added to `PRESETS` (`api/documentary.ts`) and `PRESET_HINT` (`StoryboardTab.tsx`) so it's
  pickable from the existing preset dropdown — no new UI surface.

## C. Ambient particle overlay (`Scene.ambient`)

- New optional scene-level enum, 4 values: `rain | snow | wind | embers` (the brief's own list).
  Nullable, default `None` — manually set, never auto-detected from narration (weather-guessing from
  text is a real feature, just not one this task was asked to build).
- **Ported from `weather.tsx` almost verbatim** (continuous, seeded, wrap-around particle fields —
  exactly the brief's ask), into a new `remotion/src/weather.tsx`. Ported 6 of its 8 exports
  (`Snowfall, Rain, Wind, Sparks, Water, FallingLeaves`); skipped `Fire` (per the brief: would read as
  literal fire over archival/AI photos, wrong tone unless a scene already depicts fire, which none of
  the 4 wired enum values need) and `ArrowVolley` (a one-shot combat effect, not an ambient/continuous
  one, out of scope for "optional overlay on a still image"). Only 4 of the 6 ported components are
  wired to the enum (`rain→Rain`, `snow→Snowfall`, `wind→Wind`, `embers→Sparks` aimed upward from the
  bottom edge); `Water`/`FallingLeaves` are ported and exported but currently unused — available for a
  future preset, not dead code the compiler would flag (unused *exports* don't error under
  `noUnusedLocals`, unlike unused locals).
- **Palette swap:** `weather.tsx` imported `COL` from stickman-video's own `./fx` (keys `ink orange
  yellow red blue ...`). Vox's `theme.ts` has `COLORS` with `ink yellow red blue` but no `orange` —
  substituted `COLORS.red` for `COL.orange` in `Sparks`/`FallingLeaves`-adjacent uses. Visually close
  (both are warm accents) and keeps the whole app on one palette source instead of two.
- **Where it mounts:** *not* inside each of the 9 (now 10) preset components — that would mean
  touching every one of them and re-testing every one for a regression. Instead it mounts once, in
  `Documentary.tsx`'s `SceneView`, as a sibling drawn after `<Preset/>` inside the same
  fading `AbsoluteFill`, so it fades in/out with the scene like everything else and needs
  `scene.ambient` read in exactly one place. Applies uniformly across all 3 themes (collage/cinematic/
  poster) rather than per-theme, since blowing snow/rain/wind is not a collage-specific idea.
- `pointerEvents: "none"` on the overlay's `<svg>` (it's cosmetic, never meant to intercept anything —
  not that Remotion renders are interactive, but it matches how every other full-bleed decorative
  `<svg>` in this codebase, e.g. `MapZoom`'s `Contours`, is written).
- Backend: new nullable `DocumentaryScene.ambient` column (migration `0017`, guarded exactly like
  `0015`'s `assigned_hash` backfill — `test_migrations.py` enforces model/migration parity, so the
  column and the migration were added together, verified against that test). Exposed through
  `SceneOut`/`SceneUpdate` and a plain `<select>` in the scene editor (no new concepts — same pattern
  as `visual_preset`'s own select).
- Entirely additive: a scene with `ambient: null` (every existing scene, forever, unless a user picks
  one) renders pixel-identical to before this change — the overlay component simply isn't mounted.

## What was deliberately not done

- No frontend UI for picking a *specific* SFX sample per scene beyond the existing free-text hint —
  the hint-to-style mapping is automatic.
- No PyInstaller packaging changes (`numpy` ships as part of the existing `faster-whisper` wheel
  closure already bundled; no new packaging work was in scope here and the task didn't ask for it).
- No change to `MapZoom` itself. `cinematic.tsx`/`poster.tsx` map **every** existing preset name to
  one of their own components (`POSTER_COMPONENTS` maps all 9 to the single `PosterScene`;
  `CINE_COMPONENTS` maps each to its own themed component) — `SceneView` in `Documentary.tsx` does
  `COMPONENTS[scene.preset]` with no fallback, so a preset name missing from either map would crash
  the render (`<undefined/>`) the moment a scene using it rendered under that theme. `cinematic`/
  `poster` are hidden from the Render tab (`HANDOFF.md`: "đã bỏ khỏi tab Render") but both are still
  reachable through the API and a prior project may already be stored with `theme: "cinematic"`
  (`HANDOFF.md`'s own Constantinople project has a rendered cinematic job) — leaving a gap would be a
  real regression for that path, not a hypothetical one. Fixed by adding one line to each: `TacticalMap:
  PosterScene` (matches that map's own "every preset renders the same way" convention exactly) and
  `TacticalMap: CineEvidence` (cinematic's existing pin-and-line evidence board — the closest visual
  match already in that file, reused rather than writing a second bespoke diagram component).
