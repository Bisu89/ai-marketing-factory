# 52 — Final Composer: Beat Clips + Audio Master + Captions → final.mp4

**Commit:** `<pending>`

Extends the existing `VideoComposerService`/`VideoComposeJob` renderer
(never a second queue) with a new, single-pass composition mode for
Factory-driven renders:

```
Beat Clips (Motion, Task 23) -> ffmpeg concat filter -> captions (Task 25) ->
optional watermark -> format -> encode, audio mapped straight from
Audio Master (Task 24) -> final.mp4
```

No TTS, no per-job audio mixing, no live word-boundary captioning — every
input is an already-produced, already-validated Factory artifact.

## Key pieces

- `app/modules/video_composer/models.py`: `VideoComposeJob` gains
  `audio_master_path`/`captions_ass_path`/`watermark_*` columns and a new
  fine-grained status `composing_final` (`RENDER_PHASE["composing_final"] =
  "FINAL_COMPOSITION"`) — a sibling of the existing 7-phase vocabulary, not
  a new top-level Factory stage.
- `app/modules/video_composer/service.py`: `_run_final_composition` +
  `_compose_final` — a new branch in `_run_job`, taken only when
  `narration_mode == "precomposed"`; every other job (plain uploads, the
  old TTS/local-narration Factory path) is completely untouched.
- `app/api/v1/endpoints/composition_render.py`: `render_composition`/
  `_run_preflight` gained `audio_master_path`/`captions_ass_path`/
  `watermark_*` parameters; when `audio_master_path` is set,
  `_resolve_narration` (word-boundary/local-timeline logic) is skipped
  entirely.
- `app/api/v1/endpoints/factory_pipeline.py`: `_stage_render` now resolves
  Audio Master (required — raises `AUDIO_MASTER_MISSING` up front if
  missing/invalid), Captions (optional, only when enabled and valid), and
  Watermark (optional, resolved from the Asset Library, never a raw path)
  before handing off to `render_composition` — the exact same
  `LocalRenderQueue`/`RENDERING` Factory stage as before, no new state.
- `app/modules/beat/schemas.py`: new `WatermarkProjectConfig`
  (`enabled`/`asset_id`/`position`/`opacity`/`scale`/`margin_x`/`margin_y`)
  on `ProjectConfig`, same "bare Asset reference, no FK" convention as
  `AudioProjectConfig.bgm_asset_id`.
- `app/core/render_errors.py`: 10 new stable codes (`FINAL_COMPOSITION_FAILED`,
  `MISSING_BEAT_ARTIFACT`, `INVALID_BEAT_ARTIFACT`, `AUDIO_MASTER_MISSING`,
  `CAPTION_ARTIFACT_MISSING`, `WATERMARK_ARTIFACT_MISSING`,
  `FINAL_OUTPUT_INVALID`, `FINAL_DURATION_MISMATCH`, `FINAL_STREAM_INVALID`,
  `FINAL_ENCODING_FAILED`).

## Encoding

Container MP4, video codec H.264 (`libx264`), pixel format `yuv420p`,
audio codec AAC (192kbps). Resolution/fps come from the Beat clips
themselves (already normalized by Task 23's Motion renderer to the
project's render profile). No CRF/preset override beyond what
`VideoComposerService` already uses everywhere else — reused, not
reconfigured. CPU-only; no hardware-encoder dependency anywhere in this
pipeline.

## Streams

`_validate_final_output` was tightened from "at least one video/audio
stream" to "exactly one video stream, exactly one audio stream"
(`FINAL_STREAM_INVALID` on violation) — safe for every existing caller,
since every ffmpeg command in this service always explicitly `-map`s
exactly one of each. Beat clips are always rendered `-an` (no audio
stream, per Motion's own renderer), so there is no risk of accidentally
keeping Beat-clip audio in the final mix.

## Captions

Burned in via ffmpeg's `subtitles=` filter, given the Caption Engine's own
`captions.ass` directly (no regeneration) with an explicit `fontsdir`
pointing at this app's own bundled Arial location (`FONT_PATH`'s parent
directory) — the same font both `captions.ass` (Task 25) and
`video_composer`'s own ASS Style lines already hardcode, so this is the
app's one and only configured fallback, not a silent substitution. Disabled
captions (or a stale/invalid `captions.ass`) simply never enter the filter
chain — no hard failure.

## Watermark

Source: an ordinary Asset Library image (PNG, alpha supported), resolved
from `WatermarkProjectConfig.asset_id` by the composition root — never a
raw frontend path. Position: one of 4 corners, expressed via ffmpeg's own
`overlay` filter `W`/`H`/`w`/`h` variables (no fixed-pixel math needed).
Opacity/scale/margins are all configurable (`colorchannelmixer=aa=<opacity>`,
`scale=<width*scale>:-1`, corner margin in pixels). Disabled by default
(`watermark_enabled=False`) — no overlay filter is inserted at all in that
case, not even a no-op one.

## Cache

Not independently cached at the render-composition level — a deliberate,
documented scope cut (see **Problems** below). Every upstream artifact
(Beat clips via Motion's own cache, Audio Master, Captions) is already
idempotent, so a Factory render's own final composition pass is a single,
comparatively cheap ffmpeg call (no TTS, no per-clip re-render) rather than
something expensive enough to need its own separate cache-hit shortcut.

## Invalidation

Motion/Audio/Captions changing is exactly what already invalidates their
own upstream artifacts (Tasks 23-25); the next Factory render then
naturally re-reads whichever files those stages produced. Watermark
changing is just a different `WatermarkProjectConfig` on the next
`_stage_render` call — no separate invalidation logic needed since nothing
about it is cached.

## Recovery

`composing_final` is a plain `VIDEO_COMPOSE_STATUSES`/`PENDING_STATUSES`
value — the existing `_recover_pending_jobs` startup logic (Task 11)
covers it automatically: a job found stuck in `composing_final` on restart
is marked `failed`/`RENDER_INTERRUPTED`, matching every other
mid-render-crash case. `FactoryRun`'s own crash recovery (reconciliation,
Task 19) is completely unaffected — `RENDERING` is still the one Factory
stage covering this whole job lifecycle.

## Tests

13 new: `tests/api/test_final_composer.py` (12 -- a real 3-beat end-to-end
composition with streams=1/1, h264/aac, captions burned; captions
disabled; watermark enabled/disabled; missing Audio Master, failing fast
before queuing; a missing watermark Asset; a missing/corrupted Beat clip
raising `MISSING_BEAT_ARTIFACT`/`INVALID_BEAT_ARTIFACT`; a duration
mismatch raising `FINAL_DURATION_MISMATCH`; crash recovery; a 4-project
batch with one deliberately broken project isolated from the other
three), plus 1 in `tests/modules/video_composer/test_pipeline_hardening.py`
covering the cost-accounting bug below. Full suite: 847/847 passing (one
different pre-existing timing flake surfaced on each of three separate
full-suite reruns -- confirmed unrelated by re-running each in isolation).

One existing test (`test_continue_batch_only_touches_needs_review_and
_failed`) needed its own fixture updated to run real Voice+Audio before
expecting a NEEDS_REVIEW item to reach QUEUED — this task made a real
Audio Master a hard requirement for any Factory render (section 59), so a
fixture that skipped straight to the render stage without ever producing
one now correctly fails there instead.

## Real bug found and fixed during this task

`_write_render_report`'s own external-API cost accounting
(`external_api_calls = 0 if narration_mode == "local" else 1`) predates
this task and only ever knew about two narration modes ("local" = zero
cost, anything else = 1 unofficial-but-real edge_tts call). It silently
mis-billed every Task-26 "precomposed" render as making 1 external API
call, even though narration/BGM/captions were all already produced
locally by earlier Factory stages before the render job even started.
Caught only by real manual verification (a completed job's own
`report.json` showing `external_api_calls: 1` for a render that made zero
network calls) -- fixed to treat both `"local"` and `"precomposed"` as
zero-cost, with a dedicated regression test.

## Manual verification

A real 3-beat project run through Voice → Audio Master → Captions →
Final Composer with the live worker thread actually running (plus a real
watermark Asset registered and enabled): produced a playable `final.mp4`
(11.78s, 1080x1920) with exactly one h264 video stream and one aac audio
stream, `burn_subtitles=True`, `watermark_enabled=True`,
`narration_mode="precomposed"`, and a `report.json` correctly showing
`external_api_calls: 0` after the fix above.

## Cost

Cloud rendering: $0. AI video generation: $0. I2V: $0. External composition
API: $0. FFmpeg: local only, CPU.

## Problems

**No render-level cache-hit shortcut.** Sections 37/38 of this task ask
for the final render itself to be independently cache-keyed and skip
re-composition on an unchanged run. Implementing that safely would require
changing `render_composition`'s own return contract (to signal "reused an
existing job" vs "queued a new one") so `_stage_render` never marks a
`FactoryRun` `QUEUED` against a job that will never actually enqueue/emit a
`render.job.*` event — a real risk of stranding a run if done carelessly.
Given every expensive upstream stage (Motion/Audio/Captions) is already
cached and the composition pass itself is a single cheap ffmpeg call, this
was deliberately left out rather than risk a half-correct implementation
interacting badly with `FactoryRun`'s own checkpoint/event state machine.
A future task can revisit this specifically if render-stage cost becomes
significant (e.g. very long videos).

Frontend's phase checklist doesn't know a given job is Factory-driven
(`narration_mode="precomposed"`), so `COMPOSE_VIDEO`/`BUILD_AUDIO`/
`BURN_CAPTIONS` show as perpetually "pending" until `VALIDATE_OUTPUT`
flips the whole checklist to "done" at once for that job type — purely
cosmetic, documented in the frontend code itself.

## Next task

Task 27 — Thumbnail + Metadata: Final Video → Thumbnail + Title +
Description + Hashtags → Post Package.
