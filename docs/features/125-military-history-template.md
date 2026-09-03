# 125 — Built-in "Military History (Decisive Battles)" Template

**Commit:** `75eebee`

The sub-niche the user settled on after a 2026 trend analysis (search:
"faceless history documentary 2026", "history YouTube RPM by sub-niche"):
**ancient & medieval military history, one decisive battle per video.**
Highest-value history RPM band (~$7–13), high-disposable-income audience
(older male / veteran / wargamer), and the "one specific battle /
commander" angle is under-served relative to the audience size (the big
channels cover the same popular topics). 9th built-in.

## What it sets (vs `history_documentary`, its parent)

- `content.target_duration` **900s (~15 min)** — battle docs hold
  retention at that length (general history template is 11 min)
- `content.style`: ONE decisive battle told as a narrative — strategic
  situation & stakes, the two armies + commanders, the terrain, the battle
  **phase by phase**, the turning point, the consequences — "grounded in
  specific numbers, units, formations and geography, never vague"
- `audio.music_volume` 0.15 (a touch up from 0.14 for a martial score)
- `visual_generation.image_style_prompt`: battle-specific — massed
  infantry in formation, cavalry charging, period-accurate arms/armor,
  dust & smoke, dramatic low battlefield light
- `outro` CTA reworded to "a new decisive battle every week"
- Everything else inherited: `SOCIAL_LANDSCAPE` 16:9, edge_tts
  `en-GB-RyanNeural` @0.95, `SLOW_PUSH_IN`/MEDIUM + auto_rotate,
  `cinematic` captions, `package.ai_metadata_enabled=True`, `mode="library"`
  default (run with "Generate Full by AI")

## Also created (not code)

Series **#6 "Decisive Battles"** (DB row) — a shared painterly historical
war-art style description for AI-image consistency across episodes.

## Verification — real 1-minute smoke test

End-to-end Factory run at a temporary `target_duration=60` + `local` voice
(a content/pipeline check, not the real format), library placeholder
images, idea "The Battle of Cannae, 216 BC…":

- Content stage → a **163-word, accurate** military-documentary script:
  bold numerical hook ("a smaller Carthaginian army surrounded and
  annihilated a Roman force of roughly 70,000 to 80,000"), real specifics
  (Aufidus River, consuls Varro & Paullus, the elastic centre, the
  cavalry envelopment phase by phase), an analytical close.
- 7 beats (HOOK/SETUP/BUILD×2/REVEAL/REACTION/ENDING), Quality Gate
  **READY 100**, Final QA **PASS 100**.
- Render → `1920×1080` h264/aac, 78s, burned 2-line `cinematic` captions,
  Ken Burns motion. (Visuals were deliberate placeholders — a real run
  uses "Generate Full by AI".)

## Key files

- `backend/app/modules/beat/schemas.py` — `MILITARY_HISTORY_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set / count (8 → 9)

Frontend needed no change (template picker is `GET /templates`-driven).
