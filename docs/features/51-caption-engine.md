# 51 — Caption Engine: Script/Timing → Styled Captions → ASS

**Commit:** `<pending>`

Adds a new `GENERATING_CAPTIONS` FactoryRun stage (after `GENERATING_AUDIO`,
before `QUALITY_CHECK`) that turns each Beat's own final narration text plus
its Voice-settled `[start, end]` timing into a styled, cached `captions.ass`:

```
Beat.narration + Beat.start/end (Task 22) -> phrase segmentation -> per-segment
timing (weighted, min/max-duration bounded) -> ASS serialization -> captions.ass
```

No ASR, no AI caption/transcription API, no live TTS word-boundary call —
purely deterministic, local, and $0. Depends only on Voice's settled Beat
timing (not Motion or Audio, both independent siblings), so it's placed
right before Quality among the local-artifact stages.

## Key pieces

- `app/modules/caption/` (new, pure, no cross-module imports):
  `segmentation.py` (`split_beat_into_segments` — mirrors
  `app.modules.voice.timing`'s own weighted-estimate + minimum-duration-
  rebalance shape, applied one level down: one Beat's text → N caption
  segments), `ass_writer.py` (`build_ass_content` — duplicates
  `video_composer.service`'s own proven `CAPTION_PRESET_CONFIG` values/ASS
  template, not imported, per this codebase's established module-boundary
  convention), `schemas.py` (`CaptionSegment`, error codes).
- `app/api/v1/endpoints/caption_generate.py` (new composition root): the
  idempotent stage function, a cache fingerprint over Beat narration +
  Voice-settled timing + caption config + `ENGINE_VERSION`
  (`"caption-v1"`), sidecar `captions.meta.json`.
- `CaptionsProjectConfig` gained `max_words`, `max_chars`, `min_duration_sec`,
  `max_duration_sec`, `max_lines`, `reading_speed_wps` (all bounded/validated).

Deliberately produces a standalone artifact and does **not** touch
`composition_render.py`/`video_composer`'s own existing, separate live
caption-burning path — final video composition is a later task, matching
Task 24's identical scoping decision for `audio_master.wav`.

## Segmentation & styling

Phrase-boundary-first split (sentence-end/comma preferred over a blind
word-count cut), falling back to a hard word/char limit when a single
phrase is still too long. Duration is word/punctuation-weighted across the
Beat's own window, rebalanced so no segment falls below `min_duration_sec`,
then capped at `max_duration_sec` — a short text chunk given a
disproportionately long Beat window is capped rather than stretched,
leaving an intentional trailing gap (Task 25's own explicit allowance).

All 5 existing presets (`emotional`, `cinematic`, `word_highlight`,
`big_statement`, `quote`) render — no per-word "karaoke" animation, since no
per-word timestamps exist here (Task 25's own explicit "MVP = per-segment,
not per-word" instruction): `emotional`/`word_highlight` degrade to plain
static segment-level text (same font/color/position as their live-render
counterparts, just without the per-word highlight motion).

## Cache & invalidation

SHA-256 over every Beat's `id:narration:start:end` + caption config +
`ENGINE_VERSION`. A script edit or a Voice-driven timing change both
invalidate; a style-only change (e.g. preset) invalidates independently
without touching Beat.asset_id or any other stage's state (verified
directly). Disabled captions (`enabled=false`) skip cleanly — no empty
placeholder file.

## Recovery

`GENERATING_CAPTIONS` is a plain `FACTORY_STAGES` value — Task 19's generic
checkpoint/retry/reconcile machinery covers it automatically (verified: a
run stuck at `GENERATING_CAPTIONS` reconciles to `FAILED`/
`FACTORY_INTERRUPTED` on restart). Quality Gate extension mirrors Task 24's
own Audio pattern exactly: `captions_artifact_checked`/
`captions_artifact_valid` only flag a stale/missing `captions.ass`
(`CAPTIONS_ARTIFACT_MISSING`, warning) when a prior run actually claimed to
have produced one.

## Tests

65 new: `tests/modules/caption/test_segmentation.py` (26 — chunking,
sentence/phrase boundaries, min/max-duration rebalancing, timing
containment/continuity), `tests/modules/caption/test_ass_writer.py` (22 —
every preset, line wrapping, structural validation, Vietnamese/Spanish/
English Unicode round-trips), `tests/api/test_caption_stage.py` (17 —
generation, presets, idempotency, invalidation, crash recovery, stage-error
translation, pipeline integration, a real 5-project batch). Full suite:
835/835 passing.

## Manual verification

Real end-to-end run against an isolated scratch database (never the real
`data/library.db`): a 4-beat project through real Voice (settling Beat
timing) then real Captions, producing a valid `captions.ass` with 10
correctly-timed Dialogue lines; confirmed idempotent on a second call; a
temporary FFmpeg burn-in preview (verification only, not final composition)
rendered successfully.

## Cost

External ASR/transcription: $0 (none used). External caption/AI API: $0.
External video generation: $0.

## Next task

Task 26 — Final Composer: Beat Clips + Audio Master + Captions → final.mp4.
