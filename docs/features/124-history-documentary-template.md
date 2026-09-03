# 124 — Built-in "History Documentary" Template

**Commit:** _(fill in after commit)_

New monetization-oriented faceless niche the user asked for: long-form
English history documentaries (military history, ancient civilizations,
figures, unsolved mysteries). 8th built-in Template — a niche here is just
script + Template, no pipeline change.

## What it sets (vs every earlier built-in)

- **First `SOCIAL_LANDSCAPE` (16:9) built-in** — every prior one is a
  vertical short. `content.target_duration` **660s (~11 min)** long-form.
- `content.language` **en**, tone "authoritative, measured and cinematic,
  like a documentary narrator", style = tell ONE event/figure/civilization/
  mystery as a narrative (scene-setting, cause & effect, tension, meaning —
  never a list of dates)
- `voice`: **edge_tts `en-GB-RyanNeural`** (classic British documentary
  sound), speed **0.95**, `sentence_pause_sec` **0.5**. Note in the
  template docstring: an 11-min script ≈ ~100 per-sentence edge_tts calls,
  so occasional retries/slowness are normal; `local` is the offline
  fallback.
- `motion`: `SLOW_PUSH_IN` **MEDIUM** + **`auto_rotate=True`** — a visible
  Ken Burns move with variety, since "every beat = the same slow zoom" is
  far worse stretched over 11 minutes than over a 20s short.
- `captions`: `cinematic`, `max_chars` **70** / `max_words` **12** /
  `max_duration_sec` **5.0** (16:9 is wider, lines can run longer/hold
  longer)
- `audio.music_volume` **0.14** (a low doc bed), AUTO BGM by tone tag
- `outro.enabled=True` with a default subscribe CTA (an 11-min video
  shouldn't cut dead when narration ends)
- `package.ai_metadata_enabled=True` — the only built-in that opts in; CTR
  on title/thumbnail text matters more than the small per-video cost for a
  channel meant to earn
- `visual_generation.image_style_prompt`: painterly photorealistic
  historical-documentary look, period-accurate, no modern objects/text;
  still `mode="library"` like every built-in — the description tells the
  user to switch Visuals to "Generate Full by AI" (there is no footage of
  the past, and real archive photos are a copyright risk on a monetized
  channel)

## Key files

- `backend/app/modules/beat/schemas.py` — `HISTORY_DOCUMENTARY_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set / count (7 → 8)

Frontend needed no change (template picker is `GET /templates`-driven).

## Verification

`pytest tests/modules/beat tests/api/test_content_stage.py` green (124).
Real content-stage run against a live key ("The night the Library of
Alexandria began to burn") produced a **1335-word** (~11 min) script with
a genuine documentary voice: bold corrective hook, vivid harbour
scene-setting, careful "documented vs. legend" distinction, measured tone
— publishable as-is.
