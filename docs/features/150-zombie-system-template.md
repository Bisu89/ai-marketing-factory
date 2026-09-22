# 150 — Built-in "Zombie System (Apocalypse LitRPG)" Template

**Commit:** `cfdb564`

11th built-in, and the first *fiction* one — every earlier built-in is
documentary/biography/history. A school-set zombie apocalypse where the
protagonist secretly gains a hidden game-like System (status window,
levels, skills, quests) the moment the outbreak begins — the "system
apocalypse" trend currently big on webtoon-recap channels (All of Us Are
Dead-style setting + Solo Leveling-style system).

## What it sets

- `content.style`/`tone`: ONE chapter of a continuing story per video,
  tense/urgent/propulsive narration, short system-notification beats
  ("level up", "skill acquired", "quest update") woven into the narration
- `voice`: `en-US-GuyNeural` @1.02 (faster/more urgent than the
  documentary family's 0.95 `en-GB-RyanNeural`)
- `visual_generation.image_style_prompt`: Korean webtoon/manhwa
  illustration style (clean linework, cel-shaded), not photorealistic —
  the whole point of this niche is to look like the source material it's
  recapping
- Everything else inherited from the documentary-family pattern:
  `SOCIAL_LANDSCAPE` 16:9, `SLOW_PUSH_IN`/MEDIUM + auto_rotate, `cinematic`
  captions, 720s target, `package.ai_metadata_enabled=True`,
  `mode="library"` default

## Design decision: library mode is the point, not a fallback

Every other built-in defaults to `library` mode but is *described* as
meant to run with "Generate Full by AI". This one is the opposite: real
verification (see below) showed a small reused manhwa asset pool — a
handful of character/scene images plus 2 blank sci-fi HUD graphics reused
for every system-notification beat — costs $0/beat on a re-render and
looks *more* on-genre than a unique photorealistic AI image per beat
would. The system-notification beats intentionally use blank (no text)
HUD images; the actual "LEVEL UP" / "SKILL ACQUIRED" text is delivered by
the narration + burned captions, not AI-rendered text-in-image (which is
unreliable).

## Real end-to-end verification

Project 93, "Chapter 1: Awakening" — 22 hand-written beats, 10 manhwa/UI
master images generated once (~$0.06 total) and reused via
`visual_generation.mode="library"`. First run hit a real, separate bug
(see [151](151-outro-apostrophe-render-fix.md)); after that fix, final
render: 1920×1080, 345.6s, **$0 image cost this render**, Quality READY
97, Final QA **PASS 100**. Visual spot-check (classroom establishing shot,
a system-alert HUD, the outro card) confirmed correct manhwa styling,
character consistency across reused images, and correct captions.

## Key files

- `backend/app/modules/beat/schemas.py` — `ZOMBIE_SYSTEM_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` — builtin id-set/count (10 → 11)

Frontend needed no change (template picker is `GET /templates`-driven).
