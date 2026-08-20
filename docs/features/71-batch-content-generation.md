# 71. Batch Content Generation (Idea → Story → Score → Approve)

**Commit:** `60835d9`

Batch: N selected `ContentIdea`s → generate a Story for each → score it →
auto-approve/reject against a configurable threshold, all in the
background so a 20-30-item batch never blocks an HTTP request.

## Architecture decision (reported before implementation, per this task's own instruction)

Inspected first: `StoryService.generate`/`StoryQualityService.score` are
synchronous, single-digit seconds each; a real batch needs 2 real AI
calls per item (generate + score), so 20 items ≈ 40+ calls, unsafe inside
one request. The existing project already has a proven, minimal pattern
for exactly this (`app/api/v1/endpoints/batch_render.py`'s
`_run_batch_beat_generation`/`_generate_beats_for_item`): one daemon
`Thread` per "Run" click, internally a `ThreadPoolExecutor` bounded by
`settings.max_concurrent_ai_generation`, each task also wrapped in
`app.core.concurrency.ai_generation_semaphore` (the same process-wide AI
call limiter already shared with the Factory pipeline). **Reused this
pattern exactly** -- no new worker abstraction, no persistent queue
table, no second concurrency limiter, per this task's own "do not build a
giant background job system" constraint.

## Product decision (asked directly, since it materially shapes the schema)

`StoryJob.video_id` is `NOT NULL` -- Story has always been "narration
options for one already-downloaded Video," never redesigned for a
video-less planning idea. A batch of fresh `ContentIdea`s has no video of
its own. Asked the user directly: **every item in one batch shares one
caller-chosen Video** (not 20 separate videos) -- Story generation for
each of the N ideas is filed under that shared video's story-job list.

## New module: `app/modules/content_batch/`

Mirrors `app.modules.batch`'s exact shape (own tables, `SessionLocal`-
per-call service functions callable from both request handlers and the
background thread, atomic `claim_item()` via UPDATE-WHERE for race safety,
`bulk_cancel_claimable_items()`, `recompute_batch_status()` deriving
`ContentBatch.status` from item statuses). `ContentBatchItem.idea_id`/
`story_job_id`/`story_version_id` are bare ints, no FK -- `content_batch`
must never import `content_strategy` or `ai.story` (module isolation);
`ContentBatch.video_id` is a real FK (module → core is allowed).

Status vocabulary: the task's own required
`pending/generating/completed/scored/approved/rejected/failed`, plus
`cancelled` (needed because cancellation, itself required, needs a
terminal status distinct from failed). Per item: score only version[0] of
the 2 generated (kept simple -- scoring both and auto-picking the best was
considered and left out as beyond this task's literal scope). Threshold
is 0-10 (`ContentBatch.score_threshold`, default 8.0, the task's own
"8.0 / 10"), independent of Task 05's fixed internal 0-90
`QUALITY_PASS_THRESHOLD` -- compared as `quality_score / 9 >= threshold`.

New composition root `app/api/v1/endpoints/content_batch_generate.py`
(the one place allowed to import `content_batch` + `content_strategy` +
`ai.story` together): `POST /content-batches`, `GET /content-batches`,
`GET /content-batches/{id}`, `POST /content-batches/{id}/run`,
`POST /content-batches/{id}/cancel`,
`POST /content-batches/{id}/items/{item_id}/retry`.

**Preserve successful results / do not silently discard**: each item
processes independently in its own try/except with its own DB row: a
failure never touches another item, and a FAILED item's row (with
`error_message`) is never deleted -- retry re-claims it atomically and
reprocesses. A failure *after* story generation succeeded (i.e. scoring
fails) still keeps the generated `story_job_id`/`story_version_id` on the
item -- the real work isn't discarded just because the score step failed.

## Frontend

`ContentStudioPage.tsx`'s existing bulk-selection bar gained a "Tạo Story
hàng loạt" button (new `CreateContentBatchModal`, reusing
`STORY_STYLE_LABELS` from `types/publishLog.ts` and `fetchVideos` from
`api/videos.ts` -- no new video picker built). New pages
`ContentBatchesPage.tsx` (list) and `ContentBatchDetailPage.tsx`
(progress + retry + cancel, 2s polling while active -- mirrors
`BatchDetailPage.tsx`'s own `useCallback`/`useRef`/`useEffect` polling
shape exactly), new sidebar item "Content Batches" (distinct from the
existing "Batches" video-production batches).

## Verification

Real AI calls throughout (this env's `.env` has real keys), plus
controlled fault injection (monkey-patching `StoryService.generate` for
one specific item only, inside an otherwise-real concurrent run) for the
failure/retry paths that can't be reliably forced via real infrastructure:

1. Real 3-item batch, threshold 5.0: polled live through
   `PENDING → GENERATING → COMPLETED → APPROVED/REJECTED`; final scores
   44/46/40 (out of 90) correctly yielded reject/approve/reject
   (44/9=4.89, 46/9=5.11, 40/9=4.44 vs threshold 5.0). `ai_generation_history`
   has exactly 3 `story` + 3 `quality_score` rows (real).
2. Cancel: a 2-item batch never run → cancelled → both items `CANCELLED`,
   zero AI calls made.
3. Partial failure (real + simulated in one concurrent run): idea 2's
   item forced to fail story generation while ideas 1 and 3 process for
   real; batch correctly reaches `PARTIAL_FAILURE`; ideas 1/3 land on
   real `APPROVED` with real `story_job_id`s, completely unaffected by
   idea 2's failure (preserve successful results, proven not asserted).
4. Retry: atomic claim of the FAILED item succeeds once, a concurrent
   second claim attempt is correctly rejected (no double-processing);
   retrying with the real (unpatched) pipeline succeeds, batch reaches
   `COMPLETED`.
5. Real browser run (Playwright/Chromium): Content Studio → select 2
   ideas → "Tạo Story hàng loạt" → fill modal (name/video/style/language/
   threshold) → submit → real navigation to the batch detail page → real
   live polling to "Hoàn tất" with real scores (48/90, 45/90) shown →
   `/content-batches` list page shows it. Zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean
throughout. Existing dev servers on 8000/5173 untouched.
