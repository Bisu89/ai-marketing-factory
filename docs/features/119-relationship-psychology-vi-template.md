# 119. Built-in "Relationship Psychology (VN)" Template

**Commit:** `3b90153`

Real user request: expanding into a new niche — Vietnamese, female-narrated
relationship-psychology shorts in the Robin Norwood / "phụ nữ yêu quá nhiều"
style (a calm third-person story about a woman's love pattern — hook →
story → quiet realization → one-line reframe on the last line). Same as the
horror niche, a niche here is just script + Template, so this adds a 6th
built-in alongside the horror ones.

## What it sets (vs `couple_story`, its nearest sibling)

- `content.language` **vi**, tone "gentle, tender and quietly insightful",
  `target_duration` **60s** (a reflective read, not a 20s twist)
- `voice`: **edge_tts `vi-VN-HoaiMyNeural`** (the female VN voice already
  used for Chinese Drama dubbing — local SAPI5 has no VN voice at all),
  speed **0.9**, `sentence_pause_sec` **0.7** for room between beats
- `captions`: `emotional` preset, `max_chars` 42 → **50** (Vietnamese lines
  run long), `max_words` **8**
- `motion`: `SLOW_PUSH_IN` **SUBTLE** (intimate, not the STRONG dread push)
- `audio.music_volume` **0.12** (under `couple_story`'s 0.15)
- `visual_generation.image_style_prompt`: soft cinematic emotional look,
  woman alone, face turned away; still `mode="library"` like every built-in

## Also created (not code)

Series **#5 "Phụ Nữ Yêu Quá Nhiều"** (DB row) — a VN woman shown from
behind / out of focus, warm muted reflective aesthetic, for AI-image
style consistency across episodes.

Custom template **`relationship_psychology_vn_music`** "Relationship
Psychology (VN) + Music" (`templates.json`) — the built-in's config plus
**Locket Rainfall (Asset #250)** as MANUAL BGM (volume 0.15, ducking on).
Built-in templates can't carry a `bgm_asset_id` (test-guarded), so the
music variant is a custom template, same split as `horror_shorts_music`.

## Key files

- `backend/app/modules/beat/schemas.py` — `RELATIONSHIP_PSYCHOLOGY_VI_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set / count (5 → 6)

Frontend needed no change (template picker is `GET /templates`-driven).

## Verification

`pytest tests/modules/beat tests/api/test_content_stage.py` green (119).
Series #5 created and confirmed via `GET /series`.
