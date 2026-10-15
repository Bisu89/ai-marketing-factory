# 188 — Documentary: synthesized SFX, `TacticalMap` preset, ambient particle overlay

Ports 3 capabilities from a sibling Remotion skill (`stickman-video`, read manually -- not
imported, no cross-repo dependency) into the Vox Documentary Factory, closing gaps `HANDOFF.md`
already names ("chưa làm: SFX", "MapZoom không có dữ liệu địa lý"). Full reasoning and rejected
alternatives: `docs/documentary/PORTING_NOTES.md`.

- **SFX ($0, off by default):** `app/modules/documentary/sfx.py` synthesizes 4 fixed effects
  (whoosh/impact/stinger/wind) from scratch with numpy (no scipy -- a hand-written one-pole filter
  replaces `scipy.signal.butter`, since the venv has numpy transitively via faster-whisper but not
  scipy). Wires up the scene's own pre-existing `sfx_cues` hint text (in the model/API/UI since
  migration `0011`, never consumed until now): `render_plan.build_sfx_cues` turns each hinted scene
  into one cue at its real cut-in time, `render.mux_command` mixes it in under the narration via
  `adelay`+`amix` (same technique as `video_composer/audio_mix.py`'s own unrelated SFX, read not
  imported). `RenderParams.sfx_enabled`/`sfx_db`, `RenderIn` API fields, Render tab checkbox.
- **`TacticalMap` preset:** a 10th preset -- unit blocks at a seeded layout, connected by drawn-on
  arrows -- for scripts that name a *sequence* of places/moves. Not real geography (same honesty as
  `MapZoom`'s own decorative fallback). Registered everywhere a preset name must exist (`schema.ts`,
  `presets.tsx`, `storyboard.py`, `schemas.py`), plus a safe alias in `cinematic.tsx`
  (`CineEvidence`) and `poster.tsx` (`PosterScene`) so picking it under either theme doesn't crash.
- **Ambient overlay:** new nullable `DocumentaryScene.ambient` (`rain|snow|wind|embers`, migration
  `0017`), manually set, never derived. `remotion/src/weather.tsx` ports 6 of `weather.tsx`'s 8
  continuous particle effects (skips `Fire`/`ArrowVolley`); mounted once in `Documentary.tsx`'s
  `SceneView`, over whatever preset is already showing, across all 3 themes.

**Verified for real, not just type-checked:** `npx tsc --noEmit` (remotion) and `npx tsc -b --noEmit`
(frontend) both clean; `pytest tests/modules/documentary` 187/187 pass (incl. `test_migrations.py`'s
model/migration-parity check); a real `ffmpeg` mux with synthesized SFX cues produced a 6.00s file
with the cue measurably audible (-34 dB mean) against digital silence (-91 dB) elsewhere, and
`mux_command`'s old no-sfx/no-music code path is byte-identical to before; a real
`npx remotion render` of a hand-built manifest produced a 1920x1080 MP4 with both a `TacticalMap`
scene (arrow + 2 labelled unit blocks, screenshot-verified) and a `rain`-ambient scene (streaks
visible over the placeholder card, screenshot-verified).

Commit: "feat: documentary -- synthesized SFX cues, TacticalMap preset, ambient particle overlay (ported from stickman-video)".
