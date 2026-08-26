# 108. Landscape (16:9) Render Profile + Long-Form target_duration

**Commit:** `9fc6686`

Real user request: a long-form (7-8 min) YouTube documentary/journal series
("MMO Journey to 10K") in traditional 16:9, not this app's original
vertical-only Shorts pipeline.

## What was actually blocking it

Two independent, real gaps found by trying to create the project end to end
(not just reading code):

1. **Only one render profile existed** (`app.core.render_profile`):
   `SOCIAL_VERTICAL` (1080x1920) and `PREVIEW` (720x1280) -- no landscape
   option at all. Most of the pipeline (composition render, the caption
   engine's own word-wrap-by-pixel-width, motion) already derives its
   geometry from whichever profile is requested rather than hardcoding
   `SOCIAL_VERTICAL`'s numbers -- confirmed by reading each, not assumed.
   The one real hardcoded exception was AI image generation:
   `app.modules.ai.image_client.IMAGE_SIZE` was a single hardcoded
   `"1024x1536"` (portrait) constant, and `imagegen_generate.py`'s own
   image-prompt template hardcoded the literal string "vertical 9:16
   composition" into every prompt regardless of the project's actual
   profile.
2. **`ContentProjectConfig.target_duration` capped at 120 seconds** --
   discovered by literally trying to create the template and hitting a
   real 422 validation error. Root cause: it reused `Beat.duration`'s own
   `MAX_DURATION` (120s, correct for one beat/segment) as its own ceiling,
   never designed against a whole video's length. A video is many beats
   concatenated -- nothing about rendering, captions, or audio actually
   caps total length at 120s.

## What changed

- `app/core/render_profile.py`: added `SOCIAL_LANDSCAPE` (1920x1080, 30fps
  -- the exact rotation of `SOCIAL_VERTICAL`).
- `app/modules/ai/image_client.py`: `IMAGE_SIZE` split into
  `IMAGE_SIZE_PORTRAIT`/`_LANDSCAPE`/`_SQUARE` (all 3 sizes GPT image
  models actually support, verified against the installed `openai` SDK's
  own `Literal` type) plus `IMAGE_SIZE_DIMENSIONS`. `generate_beat_image`
  gained an optional `size` parameter, defaulting to the original portrait
  size for every existing caller.
- `app/api/v1/endpoints/imagegen_generate.py`: new
  `_image_size_for_profile(profile)` derives which size to request from
  the profile's own width vs height (never branches on profile *name*, so
  a future square profile works automatically); `_orientation_phrase`
  makes the "vertical 9:16 composition" text in the AI prompt dynamic
  instead of hardcoded. The resolved size is threaded through to both the
  OpenAI API call and the registered Asset's width/height.
- `app/modules/beat/schemas.py`: `ContentProjectConfig.target_duration`
  now validates against a new, separate `MAX_TARGET_DURATION = 1800.0`
  (30 min) instead of `Beat.duration`'s `MAX_DURATION` (120s) --
  `Beat.duration`'s own cap is untouched (still correct for one segment).

## Verification

Backend: new tests in `test_render_profile.py` (the new profile's
geometry), `test_image_client.py` (size passthrough, default, rejection of
an unsupported size), `test_imagegen_stage.py` (a real landscape-profile
project end to end -- correct API size requested, correct orientation
phrase in the prompt, correct Asset width/height registered), and
`test_schemas.py` (target_duration accepts a long-form value, still
rejects past the new ceiling). Full sweep of every touched suite --
`tests/modules/beat/`, `tests/modules/ai/`, `tests/api/test_imagegen_stage.py`,
`tests/core/`, `tests/api/test_content_stage.py`, `test_factory_pipeline.py`,
`test_caption_stage.py`, `test_audio_stage.py` -- 205 passed. Also caught
and fixed a real, unrelated pre-existing gap this sweep surfaced: 3 tests
in `test_content_stage.py` used a `generate_beat_plan` mock with the old
2-positional-argument signature, broken since
[103](103-story-to-scene-analysis.md)'s `idea`/`character_description`/
`tone`/`style`/`target_duration` kwargs were added but this one file's own
mock was missed at the time.

Real, non-mocked verification: created an actual Template
("MMO Journey to 10K", `render.profile=SOCIAL_LANDSCAPE`,
`content.target_duration=450`) and Series via the real running app's API
-- both succeeded (previously the target_duration alone would have 422'd).
Confirmed the Series appears on the real Series page via a live browser
check.
