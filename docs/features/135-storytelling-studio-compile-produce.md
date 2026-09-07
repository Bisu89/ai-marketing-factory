# 135. AI Storytelling Studio — Phase 5 (compile → Factory)

The last phase of the Studio's technical path: turn a planned Story into
renderable `beat.Project`(s) and hand each to the existing Factory
pipeline. No new render pipeline — `COMPILING` builds the beat plans,
`PRODUCING` calls `factory_pipeline.create_and_start_run` per project (the
same path the Video Factory button uses).

## What it does

- **`POST /stories/{id}/produce`** — a `PRODUCE`-scope `StoryRun`:
  - `COMPILING` — per `StoryCompileProjectConfig.compile_mode`:
    - `per_chapter` → one `BeatPlan`/`Project` per chapter, id stored on
      `StoryChapter.compiled_project_id`
    - `single` → one `Project` for the whole story, ids on
      `Episode.compiled_project_ids_json` (when the story has an episode)
  - Each `StoryScene` → one `Beat`: scene type mapped to the smaller
    `BeatType` set, `duration_hint` → `duration`, and a
    `visual_description` that **inlines every on-screen character's locked
    `canonical_prompt_block` verbatim** — that is the character-consistency
    mechanism (identical block in every scene's image prompt). Scenes under
    `merge_scenes_under_seconds` fold backward into the previous beat.
  - The compiled config forces `audio.narration_enabled = True` (the
    Factory has no silent-render path) and
    `visual_generation.mode = "ai_generated"` with the style bible's
    palette/lighting/mood as the `image_style_prompt`.
  - `PRODUCING` — one `factory_pipeline.create_and_start_run` per project.
  - `COMPLETED` once every project is handed off; `Story.status →
    PRODUCING`. The renders themselves are tracked as `FactoryRun`s.
- **`GET /stories/{id}/compiled`** — each compiled project + its latest
  `FactoryRun` status, for the Studio UI.
- **Frontend** — `/studio/:storyId` gains a **Produce** panel: appears
  once the plan is `READY` / `SCENES_READY`, shows the compile→produce run
  status, and lists each compiled project with a live Factory-run badge +
  an "open in Video Factory" link. Polls while a run or a handed-off
  render is active.

## Key files

- **New:** `app/api/v1/endpoints/story_compile.py`,
  `tests/api/test_story_compile.py`, `frontend` Produce panel (in
  `StudioStoryPage.tsx`)
- **Modified:** `app/modules/story/service.py`
  (`set_chapter_compiled_project`, `set_episode_compiled_projects`),
  `app/api/v1/router.py` (mount), `frontend/src/api/story.ts` +
  `types/story.ts` (`produceStory`, `getCompiledProjects`, produce stages)

## Non-obvious decisions

- **The produce run is idempotent at the run level.** `COMPILING` first
  checks the run's own `compiled_project_ids_json` — if those projects
  still exist, it skips straight to `PRODUCING`. Combined with the
  per-chapter / per-episode reuse, a retried produce run never creates
  duplicate projects.
- **A cost-guard `BLOCK` refuses to produce** (`estimate_cost` is
  re-checked at `POST /produce`), the same gate the planning run's
  `SCENE_CLASSIFICATION` stage applies — never compile + spend on a run
  that's already over budget.
- **The story run finishes at handoff, not at render completion.** Each
  `FactoryRun` has its own crash-safe lifecycle and its own UI (Video
  Factory); duplicating that polling into the story run would be a staler
  second copy. `GET /compiled` surfaces the Factory status where it's
  useful.

## Verification

9 compile/produce tests + 28 story-api tests + 882 `tests/modules` +
factory/beat regression pass. `npx tsc -b --noEmit` clean; `npm run build`
succeeds. HTTP smoke: `GET /stories/1/compiled` → `[]` for a fresh story;
`POST /stories/1/produce` on a scene-less story → `400` with the "run the
planning pipeline first" message.

## Landed in

`TBD`
