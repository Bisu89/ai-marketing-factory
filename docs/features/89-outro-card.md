# 89. Outro Card: Typed CTA + Music Swell After Narration Ends

**Commit:** `6f8f63f` (Generate Full by AI follow-up: `c0571ea`)

Real user report: videos cut off the instant narration finished, with no
room for a closing CTA. Requested, confirmed via clarifying questions: a
new (not replacing existing beats), optional 5-7s trailing segment --
solid black background, a manually-typed ending text revealed
character-by-character, background music swelling up to full volume
across the segment -- appended after the main composed video. The text is
never AI-derived from the script; a separate field, usable for every
video-creation flow (not just "Generate Full by AI").

## New module: `app/modules/outro`

`renderer.py`'s `render_outro_clip()` -- black background (`color=c=black`
lavfi source) + one `drawtext` filter per revealed prefix *per line*
(ffmpeg has no native "reveal text over time" primitive; this is the
standard chained-filter-with-`enable=between(t,...)` technique), each
line's fully-typed state staying visible via an open-ended
`enable='gte(t,...)'` filter once the next line starts, so earlier lines
don't disappear. Music (if any) ramps via `volume=eval=frame:volume='...'`
from the project's configured `music_volume` up to `1.0` linearly across
the clip's own duration -- the outro's duration *is* the swell duration.

Real bugs hit and fixed during this feature's own build (all confirmed via
direct ffmpeg testing before wiring into the app):
- ffmpeg's filter parser treats `:` as an option separator even inside
  single-quoted values -- `fontfile='C:/Windows/Fonts/arial.ttf'` failed
  with "No option name near...". Fixed the same way
  `video_composer/service.py`'s own `_escape_for_ffmpeg_filter` already
  does for the identical Windows-drive-letter case.
- A literal 2-char `\n` in a drawtext `text=` value is NOT interpreted as
  a line break (renders as a literal backslash+n); an actual raw newline
  byte IS interpreted as a break but drawtext renders a stray glyph box
  alongside it. Fixed by abandoning embedded newlines entirely -- one
  `drawtext` filter per *line*, each with its own explicit `y` offset,
  computed via real Pillow glyph measurement (`font.getlength`) for
  word-wrap instead of a chars-per-line guess (which badly overflowed the
  frame at the font sizes tested).
- Naive per-character string slicing for the reveal sequence could cut a
  prefix exactly between an escape sequence's backslash and its following
  character (e.g. mid-`\n`), producing a prefix ending in a lone
  backslash that swallows the filter string's closing quote and breaks
  the entire filter graph. Fixed with a small tokenizer
  (`_reveal_tokens`) that treats every 2-char escape as one atomic unit.

## Wiring into the Factory pipeline only

Threaded as a new optional `outro_clip_path` parameter through
`render_composition` -> `VideoComposerService.create_job` (persisted as a
new `VideoComposeJob.outro_clip_path` column, additive migration in
`app/db/migrate.py`) -> the worker's `_run_final_composition` -> a new
`_append_outro_clip()` step, run *after* the main video is fully composed
and validated against Audio Master's own duration (so that check, which
is only about the main video/audio staying internally consistent, never
needs to know about the outro deliberately extending things). Uses
ffmpeg's `concat` *filter* (full re-encode of both inputs together), not
the `concat` demuxer's `-c copy` -- the demuxer requires exact codec/param
matches between two separately-invoked ffmpeg encodes, which isn't
guaranteed; the filter re-encodes fresh regardless.

`app/api/v1/endpoints/outro_generate.py` (new composition root, mirrors
`imagegen_generate.py`'s shape) resolves the clip: reads the BGM track
`audio_generate.py`'s own Audio Master mix already chose
(`audio_master.meta.json`'s `bgm_artifact`) rather than re-running BGM
selection, so the outro swells whatever track is already playing under
the main video. Called from `factory_pipeline.py`'s `_stage_render`,
right before `render_composition` -- same "only the Factory pipeline
supplies this" shape `audio_master_path`/`captions_ass_path`/
`watermark_path` already have; the classic manual "Quick Render" path
(`create_video_compose_job_from_composition`) never sets it, matching
those three's own existing scope limitation.

Scoped to the Factory pipeline only (not the classic manual render path)
-- a deliberate scope decision given the size of this feature, matching
the existing precedent those three fields already set.

## Real bug found during live verification: Final QA false mismatch

Running this end-to-end against the user's own real, running app (project
29, a completed video, given a real outro through the real UI) surfaced a
fourth real bug: `final_qa.py`'s own `expected_duration` came straight
from re-probing Audio Master's own (outro-unaware, shorter) duration,
never from `render_meta`'s already-correctly-extended value -- so a
render with a real outro correctly appended still got flagged
`FINAL_DURATION_MISMATCH` ("Duration 45.78s differs from the expected
39.74s by 6.04s") by Final QA, moving it to `NEEDS_REVIEW`. Fixed by
adding the outro clip's own probed duration to `expected_duration`
whenever the completed job has one. New regression test
(`test_final_qa_stage.py`'s `test_outro_card_extended_duration_does_not_
trigger_a_false_mismatch`) exercises the real end-to-end pipeline with a
real outro and asserts the duration check now reports PASS.

## Config: `ProjectConfig.outro`

New `OutroProjectConfig` (`enabled`, `text` <= 80 chars, `duration_sec`
bounded 5.0-7.0, default 6.0) on `beat/schemas.py`'s `ProjectConfig` --
defaults `enabled=False`, so every existing project/template is
unaffected. `text` blank is treated as not-configured even if
`enabled=True` -- can't be a no-op-by-accident footgun the other way.

## Frontend

Added to `VideoFactoryPage.tsx`'s Step 4 (Audio), next to the existing
Background music controls -- one universal touchpoint that works for
every project regardless of how it was created, since every project
eventually saves its config through this page. `enabled` is derived
from the text field being non-blank (no separate checkbox to fall out
of sync).

### Follow-up: "what about Generate Full by AI?"

That flow (`NewVideoModal.tsx`) creates the Project and starts the
FactoryRun in one call, before there's ever a BeatPlan to attach a
Step-4-style edit to -- unlike every other flow, there's no "create now,
tune Step 4 later" opportunity before the render actually runs. Added a
new optional `outro_text` field to `CreateProjectRequest`
(`beat/router.py`, same "creation-time override" precedent
`content_language`/`visual_generation_mode` already established) plus a
matching "Ending text (outro, optional)" field in the modal itself, so
this flow doesn't require editing after the fact to get an outro.

## Verification

New real end-to-end tests (`tests/api/test_final_composer.py`'s
`OutroCardTests`, using the file's own established "exercise the real
engine, no mocking" pattern): disabled-by-default produces no extra
duration; enabled produces a real, ffmpeg-probed final video whose
duration equals narration length + the outro's own configured duration
(within 1s tolerance); blank text with `enabled=True` correctly produces
no outro. Plus a regression test for the Final QA duration bug above. All
4 new tests pass. Full backend suite green. `npx tsc -b --noEmit` clean.
The renderer itself was also verified visually (extracted PNG frames) and
acoustically (`ffmpeg volumedetect` showing mean volume ramping from
-33dB to -18dB across the clip) before being wired into the pipeline at
all.

Real end-to-end run against the user's own actual running app (not just
the isolated test suite): opened Video Factory for their real, already-
completed project 29, typed a real Vietnamese ending text into the new
Step 4 field, saved, triggered a real factory run (reusing all cached
beats/visuals/voice -- no re-billed AI cost), hit the Final QA bug above,
fixed it, restarted the backend, retried -- completed with QA 100/100,
real final duration 45.78s (39.74s narration + 6.04s outro), and a real
extracted frame from the actual output file confirms the black-background
typed CTA plays correctly at the end.

The `CreateProjectRequest.outro_text` follow-up was verified directly
too: a real Playwright run against the running app opened
`NewVideoModal`, confirmed the new field, filled it in, submitted (with
"Produce automatically" off to avoid AI spend), and a fresh `GET
/projects/{id}` on the real created project confirmed
`config.outro == {enabled: true, text: "...", duration_sec: 6.0}`.
