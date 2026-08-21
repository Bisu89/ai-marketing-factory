# 79. AI-Generated Images Now Follow the Selected Template

**Commit:** `44a54c8`

Real user report: "chose a template but Generate Full by AI always uses
the default like before." Root cause: `imagegen_generate.py`'s
`_image_prompt()` built every beat's OpenAI image prompt from a single
hardcoded style-suffix constant, never reading the project's own
template-derived config at all -- `draft.config` was already loaded one
line above the call site and simply never passed in. Every other
template-driven setting (render profile, motion preset, caption style,
audio defaults) genuinely does flow through correctly; only the AI image
generation stage dropped it, which is why this was invisible anywhere
except image style.

## Fix

`backend/app/api/v1/endpoints/imagegen_generate.py`: `_image_prompt()`
now takes the project's `ContentProjectConfig` and folds its
`tone`/`style` (real, template-differentiated fields -- e.g. Emotional
Story's `"warm and emotional"`/`"storytelling"` vs. Couple Story's
`"tender and reflective"`/`"relationship story"`) into the prompt's
style suffix. The per-*beat* consistency guarantee the old constant
existed for is unchanged -- every beat within one project still shares
the same anchor; it's the anchor itself that now correctly varies per
template instead of being identical for every project regardless of
selection.

## Verification

`tests/api/test_imagegen_stage.py` (8 tests, boundary-mocked) still
green -- the signature change didn't break anything holding a reference
to the old 1-arg form. Direct verification that the three built-in
templates now produce genuinely different prompts for the same beat
(printed all three side by side); Custom's default tone/style matches
the pre-existing `DEFAULT_PROJECT_CONFIG` exactly, so a template-less/
Custom project's output is unchanged from before this fix.
