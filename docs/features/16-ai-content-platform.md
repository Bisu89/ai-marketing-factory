# 16 — AI Content Platform (Hook + Caption generators, unified `app/modules/ai`)

**Commit:** _(fill in after commit)_

## What shipped

- Relocated `app/modules/story/` to `app/modules/ai/story/` (URL paths
  `/story-jobs` and table names unchanged — pure package move).
- New shared `app/modules/ai/claude_client.py` (structured-output call +
  timing) and `app/modules/ai/history.py` (`AIGenerationHistory` table,
  `record()` helper) — used by Story, Hook, and Caption.
- New Hook Generator (`app/modules/ai/hook/`): `POST /hook-jobs` generates
  5-10 short hooks per call, per-hook favorite toggle.
- New Caption Generator (`app/modules/ai/caption/`): `POST /caption-jobs`
  generates 2 versions, each with Facebook/Instagram/YouTube/pinned-comment/
  CTA text, select-one-version like Story.
- Frontend: `StoryPage.tsx` became `AIContentPage.tsx` (route `/story` →
  `/ai`, Sidebar label "AI Story" → "AI Content"), with a shared video
  picker and Story/Hook/Caption tabs.

## Why one module, not three

Story/Hook/Caption live as sub-packages of a single `app/modules/ai/`
module (not three separate modules) so they can legally share
`claude_client.py`/`history.py` under the existing `app/modules/README.md`
rule ("a module may never import another module") — sharing across
sibling sub-packages of one module isn't a cross-module import.

## Key files

`backend/app/modules/ai/{claude_client,history}.py`,
`backend/app/modules/ai/{story,hook,caption}/{models,schemas,service,router}.py`,
`frontend/src/pages/AIContentPage.{tsx,css}`,
`frontend/src/{api,types}/{hook,caption}.ts`.
