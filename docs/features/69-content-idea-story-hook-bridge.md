# 69. Content Idea → Story → Hook Bridge

**Commit:** `pending`

## Restoring ai/story and ai/hook

This task's brief assumed `app/modules/ai/story` and `app/modules/ai/hook`
existed. They had in fact been deleted earlier in the same session (see
[63-remove-ai-content-and-insights.md](63-remove-ai-content-and-insights.md))
at the user's own explicit request, after being confirmed unused at the
time. The user was asked directly and chose to restore them (not to
substitute the Factory's own Script mechanism), so `models.py`/
`schemas.py`/`service.py`/`router.py` for both, plus the shared
`app/modules/ai/history.py`, were restored byte-for-byte from before that
deletion (`git checkout` from the parent commit) and re-registered in
`app/api/v1/router.py`. `app/modules/ai/caption` was deliberately **not**
restored -- this task never mentioned it, and it has no bearing on the
Story/Hook bridge. The Library frontend (`PublishLogSection.tsx`, which
lost its "pick an AI Story version" dropdown in that same deletion) was
**not** restored either -- out of this (backend-only) task's scope.

## The bridge

`app.modules.content_strategy` and `app.modules.ai.story`/`ai.hook` may
not import each other (module isolation). New composition root
`app/api/v1/endpoints/content_idea_generation.py` is the one place
allowed to import both:

- `POST /content-ideas/{idea_id}/generate-story` (body: `video_id, style,
  language`) -- loads the ContentIdea + its Pillar/Format/Emotion names,
  renders one extra text block, and calls the *existing*
  `StoryService.generate()`.
- `POST /content-ideas/{idea_id}/generate-hooks` (body: `video_id`) --
  same idea, calls the *existing* `HookService.generate()`.

Both service methods gained one new optional parameter,
`extra_context: str | None = None`, appended to the user message only
when given. Every existing caller (plain `POST /story-jobs`,
`POST /hook-jobs`) never passes it, so their prompts are byte-identical to
before this task -- verified below, not just asserted.

`StoryJob` gained one new nullable column, `content_idea_id` (bare int, no
FK/relationship -- `ai/story` must never import `content_strategy`, same
convention as `PublishLog.ai_story_job_id`/`BatchItem.project_id`
elsewhere in this codebase), set only by the bridge endpoint. `HookJob`
was **not** given an equivalent column -- the task's own Provenance
section named only StoryJob, and Hook has no natural "belongs to one
idea" concept beyond being video-level exactly like Story already is.

No `ContentStory`/`ContentHook` table was created. `ai_generation_history`
is unchanged and still the sole generation-history store (both new
endpoints reuse the existing `history.record()` calls already inside
`StoryService.generate()`/`HookService.generate()` -- nothing new writes
to it). No new Claude/OpenAI client, no global orchestrator -- the bridge
file is ~110 lines, only ever called from the composition-root position,
same shape as `content_generate.py`/`factory_pipeline.py`.

## Verification (real AI calls, not mocked -- `.env` already had real keys)

Against an isolated backend + temp SQLite DB (existing dev server on 8000
untouched), with a real Video row and a real Pillar-linked Format:

1. `POST /content-ideas` → `POST /content-ideas/1/generate-story`
   (`video_id=1, style=dramatic`) → **201**, `content_idea_id: 1`, 2
   `StoryVersion`s, both genuinely on-theme with the idea's premise
   ("hidden messages", "confronts him on camera").
2. `POST /story-jobs/1/versions/1/select` (existing, untouched) → the
   version's `is_selected` flips correctly.
3. `POST /content-ideas/1/generate-hooks` (`video_id=1`) → **201**, 8
   `HookVersion`s, also on-theme, in Spanish (Hook's system prompt is
   hard-coded Spanish -- a pre-existing quirk, left untouched).
4. `ai_generation_history` has exactly 2 real rows (`kind=story`,
   `kind=hook`), correct `video_id`/`provider`/`model`/token counts.
5. **Regression check**: plain `POST /story-jobs` (no idea) →
   `content_idea_id: null`; its `ai_generation_history.prompt_user` was
   read back and is byte-identical to the idea-driven call's prompt *minus*
   the "Content strategy context" block -- proving the no-idea path is
   genuinely unaffected, not just returning a plausible-looking response.
   Plain `POST /hook-jobs` (no idea) also still returns a completed job
   with 8 hooks.
6. Error paths: `generate-story` with a nonexistent `idea_id` → 404;
   with a nonexistent `video_id` → 404 (existing `StoryService._get_video`
   check, reused as-is).

Real cost was incurred (4 real OpenAI calls, ~300-450 tokens each,
`gpt-5.6-luna` per this deployment's configured provider) -- small, but
real, not simulated.
