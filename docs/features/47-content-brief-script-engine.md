# 47 — Content Engine: Idea → Content Brief → Script

**Commit:** _(fill in after commit)_

Adds the missing front of the pipeline: a project can now start from a
one-line **Idea** instead of a full **Script**. `FactoryPipeline` gains a
new `PREPARING_CONTENT` stage (between `PREPARING` and `GENERATING_BEATS`)
that turns an idea into a structured `ContentBrief`, then a `Script`,
flattened into the exact same `script_text` string Beat generation has
always consumed — Beat/Visual/Quality/Render are completely untouched.

```
Idea -> ContentBrief -> Script (flattened to script_text) -> Beat -> Visual -> Quality -> Render
```

## Reused, not rebuilt

`app.modules.ai.claude_client.call_structured` (Task 8) is the same AI
client every other generator already uses — no second client, no new
provider abstraction. `Template`/`ProjectConfig` (Task 12) gained one new
named sub-config, `ContentProjectConfig` (language/tone/style/
target_duration/audience/cta_enabled), the exact shape `FactoryProjectConfig`
already established for Task 18's own factory policy. `FactoryRun`
checkpoints, retry, crash recovery, and the `TRANSIENT`/`PERMANENT`/
`USER_ACTION_REQUIRED` classification (Task 19) all cover the new
`PREPARING_CONTENT` stage automatically — no new machinery, just a 14th
stage value in an already-generic system. Task 20's batch engine and AI
semaphore apply unchanged (content generation shares the same
`ai_generation_semaphore` beat generation already uses).

## New: `app/api/v1/endpoints/content_generate.py`

A composition root, same shape as `beat_generate.py`: `generate_content_brief`
and `generate_script` are two separate, real Claude calls (not one combined
call) — Task 21's own reasoning for a real intermediate `ContentBrief`
("the brief creates control") only holds if it's independently inspectable
before Script generation runs, which a single merged call can't provide.
Both use real JSON-schema structured output (never markdown parsing) with
one bounded repair retry, mirroring `beat_generate.py`'s own convention.
`Script` (hook/body/ending/cta) is a transient validation object, never
persisted separately — `.to_narration_text()` flattens it into the one
`script_text` field this app already treats as canonical everywhere else.

## Real gap found and fixed: BeatPlan re-saves were dropping the new fields

`_stage_generate_beats`/`_stage_assign_assets`/`_continue_run_sync`
(factory_pipeline.py) and `_generate_beats_for_item` (batch_render.py) each
construct a fresh `BeatPlan(...)` object and persist it via
`update_project_beat_plan`, which overwrites the whole JSON blob. None of
them carried the new `idea`/`content_brief`/`script_locked` fields forward
— caught by a failing content-stage test (`content_brief` came back `None`
after Beat generation ran), not by inspection. Fixed at all four call
sites by threading `draft.idea`/`draft.content_brief`/`draft.script_locked`
through. The identical class of bug also existed on the frontend
(`VideoFactoryPage.tsx`'s `buildBeatPlanForSave`/`buildProjectConfigForSave`)
and was fixed the same way — see "Frontend" below.

## Word count / length validation

`settings.content_words_per_second` (default 2.2, configurable) times the
template's `target_duration` gives the expected word count; a ±35%
tolerance band gives `SCRIPT_TOO_SHORT`/`SCRIPT_TOO_LONG` (never a silent
truncation — regeneration is the only path forward). `hook`/`body`/`ending`
existence is enforced by `Script`'s own Pydantic validators before the text
is ever flattened, not string-sniffed afterward.

## Manual override

`Project.script_locked` — set automatically whenever a real `script_text`
is supplied directly at creation (`create_project`'s own default:
`script_locked = bool(script_text)`), or whenever a human edits the script
through `update_project_script`/`VideoFactoryPage.tsx`'s Save (auto-locks
the instant the text differs from what was loaded — no separate lock
toggle needed for "human edits always win" to hold). The CONTENT stage's
own idempotency check is `script_locked OR script_text already non-blank`
— the second half alone already covers every pre-Task-21 project (all of
which have a real script and default `script_locked=False`), so nothing
existing changes behavior.

## Invalidation

Reuses Task 19's architecture — no new invalidation engine. Two new,
narrow `project_service` functions carry the two distinct chains section
50 describes:

```
update_project_idea    -- Idea -> Content -> Script -> Beat -> Visual -> Quality -> Render
                           (skipped entirely if script_locked -- an idea
                           edit never touches a human-finalized script)
update_project_script   -- Script -> Beat -> Visual -> Quality -> Render
                           (idea/content_brief untouched)
```
Asset/motion/audio/caption changes are already unaffected (Task 19's
existing behavior, verified, not touched by this task).

## Batch idea import

`CreateBatchRequest` gained `ideas_text`/`dedupe` alongside the existing
`scripts_text` (exactly one required) — `app.modules.batch.schemas` gained
`parse_ideas`/`parse_idea_rows`/`find_duplicate_ideas`/`normalize_idea`,
reusing `parse_scripts`'s own CRLF-normalizing shape. `parse_idea_rows`
sniffs a CSV header (`idea,language,template,duration`) vs. plain
one-idea-per-line — stdlib `csv` only, no new dependency. An idea-based
`BatchItem.script_text` (NOT NULL, an existing column) holds the idea text
itself; these items are processed exclusively through `run_batch_factory`
(Task 20), never the older `batch_render.py` beat-generation/render
endpoints, which remain untouched for script-based batches. Duplicate
ideas are detected via exact-normalized matching only (never AI semantic
similarity, section 33) and surfaced in `BatchPreview`, never silently
dropped unless `dedupe=true` is explicitly requested.

## Frontend

`NewVideoModal.tsx`: Idea and Script are now mutually-exclusive inputs
(entering one disables the other). `BatchPage.tsx`'s `CreateBatchModal`
gained a Scripts/Ideas toggle, duplicate warnings with an opt-in "remove
duplicates" checkbox, and a second "Create & Produce" button alongside the
existing "Create N Projects." `types/videoFactory.ts`/`types/batch.ts`
gained matching fields. `VideoFactoryPage.tsx` has no UI to edit
idea/content_brief (out of scope, same "backend-first" precedent as Tasks
19/20) but now preserves them through every save (see the bug above).
`tsc -b --noEmit`: 0 errors.

## Tests

28 new (`tests/api/test_content_stage.py`): generation + structured-output
enforcement, word-count/structural validation (empty/missing hook/missing
body/too short/too long/reasonable), provider-timeout and invalid-response
error-code mapping, idempotency (existing script skips generation, no
idea+no script is a content-stage no-op), manual-lock protection, both
invalidation chains, crash recovery (`PREPARING_CONTENT` stuck →
reconcile → retry resumes at content, not beats — required fixing the
shared test harness's own `_LOCAL_STAGES`/`_wait_for_run_settled`, which
didn't know about the new stage and was racily returning early), duplicate
idea detection, content fingerprint determinism, a 10-idea batch through
the real `run_batch_factory`, and one full idea→brief→script→beats→queued
end-to-end run. `tests/modules/beat/test_templates.py` updated for the new
`ProjectConfig.content` field. Full suite: 646/646 passing (the one
previously-flaky Windows tempdir-cleanup test happened not to trigger on
the final run — see Task 19/20's own notes on that pre-existing,
unrelated flake).

## Manual verification

Not run against a live server with a real Anthropic key in this pass (same
constraint noted in Tasks 18/19/20 for this dev environment) — verified
instead via the mocked-AI integration tests above, which exercise the real
FactoryPipeline/checkpoint/invalidation/batch-engine machinery end to end,
plus a direct read of all 19 real projects in `backend/data/library.db`
confirming the new JSON-blob fields load with correct, backward-compatible
defaults (`idea=None`, `script_locked=False`, a real `ContentProjectConfig`
default) with zero migration needed (no new SQL columns/tables — Task 21's
new fields all live inside the existing `Project.beat_plan_json` blob).

## Performance

Not benchmarked against a real multi-idea batch with real Claude calls in
this environment.

## Cost

```
Content generation API calls: 2 per project that starts from an idea
                               (1 brief + 1 script call), 0 for a project
                               that already has a script
Content generation cost:      unknown (provider doesn't report per-call
                               cost, same honest "unknown, never invented"
                               convention Task 17 established)
Video generation API calls:   0
Video generation cost:        $0
```
No image/video/I2V generation API was introduced.

## Problems

`VideoFactoryPage.tsx` has no UI to view/edit `ContentBrief` or trigger
`POST /projects/{id}/regenerate-script` yet — the endpoint exists and is
tested, just not wired into this page's own UI (out of scope, matches the
established backend-first precedent). CSV per-item overrides
(language/template/duration) are implemented and tested at the parser/API
level but have no dedicated frontend affordance beyond uploading a `.csv`
file into the Ideas textarea. `AIGenerationHistory` (the existing per-video
generation-history table) was deliberately *not* reused for content-stage
cost tracking — it has a non-nullable FK to a Library `Video`, which most
Factory `Project`s don't have; token/cost bookkeeping instead lives in
each run's own `FactoryCheckpoint.checkpoint_metadata`/`FactoryRun.metrics`
(Task 19's existing mechanism), not a new table.

## Architecture

Reused: `app.modules.ai.claude_client` (the one AI client), `Template`/
`ProjectConfig` (one config system, one new named sub-config), `FactoryRun`/
`FactoryCheckpoint`/retry/crash-recovery (Task 19, unchanged machinery),
`BatchEngine`/AI semaphore (Task 20, unchanged). No image/video/I2V
generation, no new AI client, no new Batch/FactoryPipeline/scheduler/queue,
no Redis/Celery/RabbitMQ, no module-to-module imports (`content_generate.py`
is a composition root, same tier as `beat_generate.py`).

## Next task

Task 22 — Voice Factory: Local TTS → Beat Timing → Narration Track.
