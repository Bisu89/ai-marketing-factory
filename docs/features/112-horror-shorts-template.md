# 112. Built-in "Horror Shorts (Rules & Twists)" Template

**Commit:** `c4dbd37`

Follow-up to [111](111-horror-builtin-template.md). The user is producing
short-form twist horror in three recurring formats (strange-rules /
impossible-event / found-footage), all 15-25s with a one-line twist
ending. `HORROR_TEMPLATE` (45s cinematic narration) is the wrong shape for
these, so this adds a 5th built-in tuned for them — same relationship
`couple_story` has to `emotional_story`.

## What it sets (vs the general Horror template)

- `content.target_duration` 22s (not 45s), tone "eerie, unsettling and deadpan"
- `motion`: `SLOW_PUSH_IN` **SUBTLE** (locked-camera / CCTV feel, not cinematic)
- `captions`: `word_highlight`, `max_words=4`, `max_chars=24` — the twist
  line lands word-by-word and fills the frame instead of shrinking
- `voice`: local, speed 0.95 (not 0.9 — too slow for a 20s short)
- `visual_generation.image_style_prompt`: security-cam / found-footage
  grain look; still `mode="library"` by default like every other built-in

## Key files

- `app/modules/beat/schemas.py` — `HORROR_SHORTS_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set / count (4 → 5)

Frontend needed no change (template picker is `GET /templates`-driven).

## Verification

`pytest tests/modules/beat` green.
