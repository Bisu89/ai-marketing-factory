# 25 — Video Factory Audio + Caption Pipeline

**Commit:** _(fill in after commit)_

## What it does

Extends `video_composer`'s audio and caption rendering so a generated video
feels finished rather than a slideshow: configurable narration volume,
background music with **real, dynamic ducking** under narration (not just a
lower static volume), optional per-scene SFX cues, fade in/out, and **5
distinct caption presets** (`emotional`, `cinematic`, `word_highlight`,
`big_statement`, `quote`) instead of one hardcoded style. No AI video
generation, no new TTS/music providers — reuses `edge_tts` (already
integrated) and `video_composer`'s existing ASS-based caption renderer.

## Key files

`backend/app/modules/video_composer/{models,service,router,schemas}.py`
(extended, not rewritten), `backend/app/modules/composition/schemas.py`
(new `CaptionPreset` enum + music/narration/ducking/fade fields on
`CompositionPlan`), `backend/app/api/v1/endpoints/composition_render.py`
(new `_compute_scene_start_times`/`_build_sfx_cues`, extended field
threading), `backend/tests/modules/video_composer/test_audio_captions.py`,
extensions to `backend/tests/api/test_composition_render.py`.

## Architecture: extending, not duplicating

Per this task's own instruction ("do not create a second caption renderer
if one already exists"), every new capability was built as an **extension
of `video_composer`'s existing pipeline** — `_mix_audio` and
`_write_subtitles` — never as a parallel system:

- **Audio**: `_mix_audio` gained `narration_volume`, `music_ducking_ratio`,
  `fade_in_sec`/`fade_out_sec`, and `sfx_cues` parameters, but the same
  method, the same `_run_ffmpeg`, and the same deterministic
  `-t {video_duration}` output contract as before.
- **Captions**: `_write_subtitles` gained a `caption_preset` parameter and
  dispatches to 5 new private helper methods
  (`_ass_events_emotional`/`_word_highlight`/`_static_lines`/
  `_big_statement`/`_quote`), all sharing the same word-boundary timing
  data and the same `_split_line_for_width` row-wrapping the original
  method already had. `"emotional"` *is* the original, already-shipped
  karaoke-highlight-box behavior ([17](17-karaoke-highlight-box.md)),
  unchanged — one preset among five now, not the only option.

No cross-module imports were introduced anywhere — `video_composer` still
imports nothing from `motion`/`asset`/`beat`; `composition` still imports
nothing from any module. All new `CompositionPlan` fields
(`music_ducking_ratio`, `caption_preset`, etc.) are plain, independently-
validated Pydantic fields, mirroring `video_composer`'s corresponding
column names by *value*, never by import.

## Contract additions (`app.modules.composition.schemas`)

`CompositionPlan` gained: `narration_volume`, `music_path`, `music_volume`,
`music_ducking_ratio`, `fade_in_sec`, `fade_out_sec`, `caption_preset`
(all composition-wide, matching `voice`/`narration_script`'s existing
precedent of mapping directly onto `video_composer` job-level fields).
`SceneAudio` gained `sfx_volume`. `SceneCaption.preset` is now a validated
`CaptionPreset` enum instead of a free string.

`music_ducking_ratio` deliberately mirrors ffmpeg's own `sidechaincompress`
`ratio` parameter directly (1.0 = no ducking .. 20.0 = ffmpeg's max) rather
than an approximate dB value — the number means exactly what the renderer
does with it, no unit-conversion guesswork at the adapter boundary.

## `VideoComposeJob` schema change

Five new columns (`narration_volume`, `music_ducking_ratio`, `fade_in_sec`,
`fade_out_sec`, `caption_preset`) plus one JSON column (`sfx_cues`) were
added directly to the model. No migration was needed — this dev environment
has no existing `data/library.db` yet, so `Base.metadata.create_all()`
creates the final schema fresh; had a populated dev DB existed, this would
have needed the same `ALTER TABLE`-or-recreate handling documented in
[10](10-scene-cutter.md)/[11](11-video-composer.md). These are columns
(not just constructor arguments) for the same reason `voice`/`music_volume`
already are: `_recover_pending_jobs()` re-reads jobs from the DB after a
crash, so the settings a job was created with must survive there.

## SFX cue timing (the adapter's job, not `video_composer`'s)

`video_composer` has no concept of "scenes" — `_mix_audio` just accepts a
generic `sfx_cues: list[{"path", "start_sec", "volume"}]`. Computing
*when* each cue should play is `composition_render.py`'s job:
`_compute_scene_start_times()` reproduces (not imports — a handful of
arithmetic lines on primitive floats) the exact cumulative-duration-minus-
overlap formula `_merge_clips_with_transitions` itself uses, so an SFX cue
lands at approximately the right moment in the final timeline. Uses each
Scene's *requested* duration, not a post-render probed one — good enough
to place a sound effect, not frame-accurate.

## Real bugs caught during verification

Both found by actually rendering audio through real ffmpeg, not by reading
the code — the same discipline as [23](23-local-motion-renderer.md):

1. **A ducking-acoustics test initially "proved" ducking was backwards.**
   The first verification measured the *final combined mix's* overall
   loudness during narration vs. silence — but the combined mix always
   sounds louder while narration plays, since narration itself is an
   unmodified, loud signal added into that mix; the test was measuring the
   wrong signal, not exhibiting an actual bug. Isolating just the ducked
   music branch (mapping `[ducked]` instead of the final `[a]`) confirmed
   *real* ducking: music measured ~6.6 dB quieter while narration played
   vs. while it was silent, using `ffmpeg`'s own `volumedetect` filter.
2. **`sidechaincompress` silently truncated the mixed output back to
   narration's raw (pre-padding) length**, even when narration had already
   been `apad`-ed to the full target duration *before* being fed into the
   compressor as its sidechain input — reproduced directly (narration=2.0s,
   video_duration=3.0s, music present → output measured 2.0s, not 3.0s).
   Padding narration alone, upstream of the compressor, was not reliably
   enough. Fixed by moving the `apad` to the very end of the filter chain
   (`apad=whole_dur={video_duration}` applied to the fully-combined output,
   right before the optional fade filters) — `whole_dur` only ever *adds*
   silence if a stream is shorter than the target, never trims, so this is
   a safe no-op once a stream is already long enough, with the outer
   `-t {video_duration}` remaining as the final, authoritative trim.
   Confirmed fixed across narration-only, narration+music, narration+SFX,
   and narration+music+SFX combinations, and with fades additionally
   applied.

Also folded in, while already touching every `_run_ffmpeg`/`_probe_*` call
site for this task: the `-nostdin`/`stdin=DEVNULL` fix flagged as an
unresolved follow-up in
[23-local-motion-renderer.md](23-local-motion-renderer.md#unresolved) — a
real, reproducible ffmpeg-hang risk in `video_composer`'s own helpers, not
just `motion`'s.

## Verification

`python -m unittest discover -s tests` — 184 tests total (31 new for this
task): **command-generation tests** for `_mix_audio` (ducking ratio
reflected exactly in the generated `sidechaincompress` filter, absent
entirely when music is missing/optional; fade filters present/absent and
correctly timed; narration volume applied; SFX cues produce the right
`adelay`/extra input; missing optional music and missing optional SFX both
produce valid, minimal commands) via a mocked `_run_ffmpeg` capturing
arguments, no real ffmpeg needed; **caption generation tests** (all 5
presets produce valid, structurally distinct ASS content; unknown preset
raises; `big_statement` upper-cases and groups two words; `quote` wraps in
curly quotes; `cinematic` genuinely has fewer Dialogue events than the
word-timed presets; caption timing reflects real word-boundary start/end
timestamps and changes when those timestamps shift; SRT output is
preset-independent, as intended); and a **real-ffmpeg integration suite**
(auto-skipped if unavailable): audio duration is exactly deterministic
across every optional-layer combination and with fades, the acoustic
ducking-reduction proof described above, and all 5 presets burn
successfully via ffmpeg's real `subtitles=` filter. `tests/api/test_composition_render.py`
gained a **final-muxing end-to-end test**: a `CompositionPlan` with
narration + ducked music + one SFX cue + `cinematic` captions completes,
confirms the settings were actually persisted to the job (not just that
`render_composition` didn't raise), and confirms the finished file has
both a video and an audio stream via `ffprobe`. All pass in ~18s; the 153
pre-existing tests (Beat + Asset + Motion + Composition + Task 07's
integration) are unaffected.
