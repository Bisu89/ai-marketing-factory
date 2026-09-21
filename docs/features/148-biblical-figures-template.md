# 148 — Built-in "Biblical Figures" Template

**Commit:** `67f62ff`

10th built-in. Tuned variant of `history_documentary`: one figure from the
Gospels/early-church story per video (Judas Iscariot, Pontius Pilate, Mary
Magdalene, Peter, Paul of Tarsus, etc.) instead of a battle or generic
event/civilization. Same "tuned variant is its own built-in" precedent as
`military_history`.

## What's different from `history_documentary`

- `content.target_duration` **720s (~12 min)**
- `content.style`/`tone`: framed strictly as history/culture, not theology
  — documented events kept explicitly distinct from tradition/legend,
  contested points (motives, identity, fate) presented as differing
  traditions/scholarly views rather than settled fact, no denominational
  or doctrinal stance. This is the deliberate design choice: it's the
  angle that stays safe for ad monetization and doesn't alienate any
  faith audience, at the cost of never taking a devotional point of view.
- `visual_generation.image_style_prompt`: first-century Roman Judea
  setting, reverent and tasteful, otherwise the same painterly
  documentary-still treatment as its parent
- Everything else inherited: `SOCIAL_LANDSCAPE` 16:9, edge_tts
  `en-GB-RyanNeural` @0.95, `SLOW_PUSH_IN`/MEDIUM + auto_rotate,
  `cinematic` captions, `package.ai_metadata_enabled=True`, `mode="library"`
  default (run with "Generate Full by AI")

## Key files

- `backend/app/modules/beat/schemas.py` — `BIBLICAL_FIGURES_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set/count (9 → 10)

Frontend needed no change (template picker is `GET /templates`-driven).

## Verification

`pytest tests/modules/beat` green (104 passed). No live content-stage run
yet — first real script should be checked for tone (no doctrinal claims
presented as fact) before scaling up episode production.
