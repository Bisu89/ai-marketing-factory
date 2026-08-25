# 103. Story-to-Scene Analysis

**Commit:** _pending_

Explicit user request: paste a complete story into Script and get a real
sequence of cinematic scenes back automatically -- no manual beat/scene
splitting, splitting by visual/emotional moment rather than by sentence,
with every word of the original narration preserved (for TTS) and a
consistent character/visual description carried across scenes.

## Root cause / scope

This already mostly existed: `beat_generate.py`'s `generate_beat_plan`
(script -> beats via a structured LLM call) is called automatically by the
Factory pipeline's `GENERATING_BEATS` stage every time "Generate Full by
AI" runs -- the "paste a story, get scenes automatically" UX the user
wants was already the existing flow. What was missing was AI *quality*:
the old prompt only asked for a short `visual_hint` label, allowed "light
trimming" of narration (no verbatim guarantee), had no camera/lighting/
emotion/continuity guidance, and never received the project's own
idea/character/tone/style/target-duration context at all.

So this is an in-place upgrade of that existing pipeline, not a new one:

- `beat/schemas.py`'s `Beat` gains 7 new optional fields: `visual_description`,
  `location`, `time_of_day`, `emotion`, `camera`, `lighting`,
  `continuity_notes`. All additive -- a pre-existing or hand-authored beat
  simply has them all `None`.
- `beat_generate.py`'s `SYSTEM_PROMPT`/`OUTPUT_SCHEMA` rewritten to: analyze
  the whole story first, split by visual moment (not sentence) with dynamic
  scene-count guidance by duration bucket, require narration to be a
  word-for-word excerpt of the script, and produce the new fields with
  explicit camera-variety/lighting-progression/character-consistency
  instructions. `generate_beat_plan` gained optional `idea`,
  `character_description`, `tone`, `style`, `target_duration` kwargs folded
  into the user message -- all values that already existed elsewhere
  (`CreateProjectRequest.idea`, `Template.image_style_prompt`,
  `ContentProjectConfig.tone/style/target_duration`), not new storage.
- A new `_narration_diff_note` validator: normalizes whitespace, compares
  the concatenated beat narration word-for-word against the original
  script, and feeds a precise diff (via `difflib`) into the existing bounded
  repair-retry loop on mismatch -- the "every word preserved, in order" the
  original prompt never actually enforced.
- `factory_pipeline.py`'s `_stage_generate_beats` now passes
  `draft.idea`/`draft.config.visual_generation.image_style_prompt`/
  `draft.config.content.tone`/`.style`/`.target_duration` into
  `generate_beat_plan` -- every "Generate Full by AI" project gets the
  richer analysis with zero new UI required (character/visual style is
  already set via the project's Template).
- `imagegen_generate.py`'s `_image_prompt()` now prefers `visual_description`
  over `visual_hint` as the prompt base and folds `location`/`time_of_day`/
  `camera`/`lighting` into a cinematography clause -- this is the actual
  point where the richer scene analysis reaches the AI-generated image.
- Frontend `GeneratedBeat`/`WorkingBeat` types and their conversion
  functions in `VideoFactoryPage.tsx` gained the same 7 fields so opening
  the beat editor and saving doesn't silently strip the AI's scene analysis
  before images are generated.

`ending_text`/`character_description`/`visual_style` from the original
request were deliberately NOT added as new form fields: an ending is just
the last part of the pasted script (the prompt already gives a final punchy
line its own scene when appropriate, per the user's own example ending in
"Day 1 of 100."), and character/visual style already has a working, proven
input -- the project's Template's `image_style_prompt` (also editable
per-template since [102](102-template-voice-caption-controls.md)).

## Verification

`npx tsc -b --noEmit` clean. Backend: `tests/api/test_beat_generate.py`
(existing suite fixed for the new verbatim-narration requirement, plus new
tests for the 7 new fields, verbatim acceptance/rejection including a
dropped-word and an invented-word case, whitespace tolerance, and context
threading), `tests/api/test_factory_pipeline.py`, `test_factory_reliability.py`,
`test_batch_factory_engine.py`, `test_batch_render.py`, `test_imagegen_stage.py`,
`tests/modules/beat/` -- all passing (one pre-existing, already-documented
Windows tempdir cleanup flake reproduced once, confirmed to pass in
isolation, unrelated to this change).

Real, non-mocked verification: called the actual running `/beats/generate`
endpoint with the user's own example story (the "Day 1 of 100" room-cleaning
narration) plus a character description, tone, style, and target duration.
Confirmed on the real response: 7 scenes for a ~36s story (within the
30-60s -> 6-12 guidance, not one-per-sentence), the concatenated beat
narration matched the original script word-for-word (106/106 words),
camera framing varied meaningfully by emotional beat (over-the-shoulder,
wide shot with negative space, extreme close-up on the mirror-realization
beat), lighting progressed from dim/cool at the start to warm sunlight by
the end, and the character description stayed identical across all 7
scenes. Also called `_image_prompt()` directly against one of these real
beats and confirmed the generated image prompt correctly folds in
`visual_description` + camera/lighting/location -- found and fixed a real
double-period cosmetic bug in that output during this check.
