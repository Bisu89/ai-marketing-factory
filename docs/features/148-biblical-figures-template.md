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

`pytest tests/modules/beat` green (104 passed).

Real end-to-end Factory smoke test (project 90, render job 138): a
hand-written ~120-word "Judas Iscariot" script (content-stage AI and image
generation both skipped on purpose -- script + beats submitted directly,
every beat pinned to the same existing library image) run through Voice →
Motion → Audio → Captions → Quality → Render. Result: `en-GB-RyanNeural`
edge_tts narration (online, male), 1920×1080 h264/aac, 53.6s, burned
`cinematic` captions, Quality Gate **READY 100**, Final QA **PASS_WITH_WARNINGS
97** (the one warning -- flat thumbnail -- is expected, from reusing a
placeholder library image rather than a real documentary still). Confirms
the template's voice/render config resolves correctly end-to-end; no bugs
found. Script tone itself (the "history not theology" framing) wasn't
exercised here since the script was hand-written, not AI-generated --
still worth a real content-stage check before scaling up episode
production.
