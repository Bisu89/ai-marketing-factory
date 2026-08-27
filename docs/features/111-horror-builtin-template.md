# 111. Built-in "Horror" Template

**Commit:** _(fill in after commit)_

Real user request: they produce MMO content and want to add a horror
niche. Niche isn't a hardcoded concept in this app — content is driven by
the script plus the chosen Template — so this just adds a 4th built-in
Template alongside Emotional Story / Couple Story / Custom.

## What it sets

- `motion`: `SLOW_PUSH_IN`, intensity `STRONG` (slow dread push)
- `captions`: `cinematic` preset
- `audio`: music on, volume `0.22`, ducking on
- `content`: tone "tense, ominous and suspenseful", style "horror
  storytelling", `target_duration` 45s
- `voice`: local provider, speed `0.9` (slower delivery)
- `visual_generation.image_style_prompt`: a dark cinematic-horror style
  string — **only takes effect if the project switches Visuals to
  "Generate Full by AI"**; `mode` stays `library` like every other
  built-in, so nothing is silently opted into billed image generation.

## Key files

- `app/modules/beat/schemas.py` — `HORROR_TEMPLATE`, added to
  `BUILTIN_TEMPLATES`
- `tests/modules/beat/test_templates.py`, `tests/modules/beat/test_router.py`
  — builtin id-set / count assertions updated (3 → 4 builtins)

Frontend needed no change: the template picker (New Video modal, Batch,
Settings) is fully driven by `GET /templates`.

## Verification

`pytest tests/modules/beat` green. One pre-existing unrelated flake in
`test_batch_render.py::RetryTests` (fails the same way on a clean
checkout).
