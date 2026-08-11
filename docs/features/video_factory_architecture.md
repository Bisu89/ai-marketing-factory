# Video Factory — Architecture Reconnaissance

Pre-implementation architecture review for a cost-optimized, local Video
Factory (Beat → Asset → Motion → existing Video Composer). **No application
code, database tables, or frontend code were created for this task** — this
document is the only deliverable. It answers the ten questions from the task
brief and proposes a structure to build against; it is not itself the
feature.

## 1. Current architecture findings

- **Layering is real and enforced by convention, not tooling.** `api/` →
  `services/<area>/service.py` (business rules) → `services/<area>/repository.py`
  (persistence) → `models/` (schema) → `schemas/` (I/O shapes) is the
  documented shape for new core code. No linter enforces it; discipline is
  carried by precedent in existing files.
- **`app/modules/` is the extension point, and its rule is absolute in
  practice, not just in the README.** Every existing module (`scene_cutter`,
  `video_composer`, `ai/story`, `ai/hook`, `ai/caption`) independently
  duplicates rather than shares: each of `scene_cutter/router.py` and
  `video_composer/router.py` has its **own** `tkinter` folder-picker endpoint,
  byte-for-byte the same idea, explicitly commented "duplicated (not
  imported)". This is a real, followed convention, not aspirational.
- **The one sanctioned exception is sibling sub-packages of the *same*
  module.** `app/modules/ai/{story,hook,caption}/` share
  `app/modules/ai/claude_client.py` (the Claude call wrapper) and
  `app/modules/ai/history.py` (`AIGenerationHistory`, one row per LLM call).
  [16-ai-content-platform.md](16-ai-content-platform.md) states the rule
  explicitly: sharing is legal *within* a module's sub-packages, never
  *across* modules. This is the load-bearing precedent for this task — see
  §2.
- **Every "job" module follows one shape**: `<Thing>Job` (status machine,
  timestamps, `error_message`) with a real FK'd, `relationship()`-backed
  one-to-many child table (`StoryJob`→`StoryVersion`, `HookJob`→`HookVersion`,
  `CaptionJob`→`CaptionVersion`, `SceneCutJob`→`SceneCutResult`,
  `VideoComposeJob`→`VideoComposeClip`). All of these live in one module —
  none of them span a module boundary. This is strong, consistent evidence
  about where real FK relationships are allowed to exist.
- **Two background-job patterns exist, chosen by cost of the operation**:
  - `scene_cutter` and `video_composer` each run their **own** single-worker
    thread + `queue.Queue`, explicitly *not* sharing `DownloadEngine`
    (`app/services/download/engine.py`'s worker pool), because ffmpeg
    encoding is CPU-bound, single-user, and shouldn't share failure modes
    with an unrelated subsystem. Both persist status synchronously to SQLite
    per step (`_set_status`) and both have a `_recover_pending_jobs()` that
    re-queues anything left mid-flight after an unclean shutdown.
  - `ai/story`, `ai/hook`, `ai/caption` run **synchronously inside the
    request** — no queue at all — because a Claude text call is fast enough
    (single-digit seconds) not to need one.
- **No shared ffmpeg utility module exists.** `video_composer/service.py` and
  `scene_cutter/service.py` (via PySceneDetect) each own their own
  `subprocess.run(["ffmpeg"/"ffprobe", ...])` calls; `video_composer` has
  `_run_ffmpeg`, `_probe_duration`, `_probe_video_info` as **private static
  methods on `VideoComposerService`**, not a reusable module. There is
  nothing today a new module could import for ffmpeg work — only a pattern to
  copy, the same way the folder-picker was copied.
- **Cross-module/cross-domain references that can't be a real FK use a bare,
  unconstrained `Integer`, never a string-based `ForeignKey`, even though
  SQLite would technically allow the latter.** Two precedents:
  `AIGenerationHistory.job_id` (must point at `story_job`, `hook_job`, or
  `caption_job` depending on `kind` — "a single column can't carry a real FK
  to three different tables") and `PublishLog.ai_story_job_id` ("deliberately
  not an FK/relationship — core must never import `app/modules/*`"). This is
  the pattern to reuse for any Beat/Asset reference back to a Library `Video`
  or an `ai/story` `StoryVersion`.
- **`EventBus` (`app/core/events.py`) is small, synchronous, in-process
  pub/sub** (`subscribe`/`publish`, handlers run in the publisher's thread, a
  raising handler is logged and swallowed). Today it has exactly one real
  publisher (`DownloadEngine` → `"video.downloaded"`) and **zero
  subscribers** — every module built so far (`scene_cutter`, `video_composer`,
  `ai/*`) is triggered by a direct user action through its own router, not by
  reacting to an event. The "future module reacts to new videos" design in
  `app/modules/README.md` has not actually been exercised by any shipped
  module yet.
- **Reusable core surface for a new module**: `Video` (with `tags`,
  `category`, `emotion`, `is_downloaded`/`video_path` — read-only from a
  module's perspective), the `/videos` search/browse API
  (`app/api/v1/endpoints/videos.py` + `app/services/library/*`), and
  `library_dir`-relative artifact storage (`library/<platform>/<channel>/<video_id>/`
  for library-sourced content, or a module's own `library/_<module_name>/`
  bucket for standalone artifacts — precedent: `_video_composer/`,
  `_uploads/`, `_local_files/`).
- **No test suite exists to constrain design** (`backend/tests/` has only an
  empty `__init__.py`). Verification for every shipped module so far was
  manual, end-to-end, against the real backend (curl/Playwright), documented
  in the feature's doc under "Verification" — not a pytest suite. Nothing in
  the new modules needs to be designed for testability infrastructure that
  doesn't otherwise exist in this codebase.
- **No migration framework.** `Base.metadata.create_all()` is additive-only,
  run at every startup. New tables are free; column changes on existing
  module tables have twice required dropping and recreating the dev DB
  (documented in [10](10-scene-cutter.md) and [11](11-video-composer.md)).
  New Beat/Asset tables carry no migration risk; anything that *changes* an
  existing table (there should be none needed here) would.

## 2. Proposed architecture

```text
app/modules/
├── ai/
│   ├── claude_client.py        (existing, shared within ai/ only)
│   ├── history.py              (existing, shared within ai/ only)
│   ├── story/                  (existing)
│   ├── hook/                   (existing)
│   └── caption/                (existing)
├── beat/                        <- NEW parent module
│   ├── models.py                 BeatPlan, Beat
│   ├── schemas.py
│   ├── service.py                script -> beats (sync, no worker thread)
│   ├── router.py                 /beat-plans
│   ├── asset/                    <- NEW sub-package of beat/
│   │   ├── models.py             Asset (FK: beat_id -> beat.id)
│   │   ├── schemas.py
│   │   ├── service.py            pick-from-Library / upload, own single-worker
│   │   └── router.py             /beat-plans/{id}/beats/{beat_id}/assets
│   └── motion/                   <- NEW sub-package of beat/
│       ├── ffmpeg.py             Ken-Burns/pan-zoom filter builders (pure fns)
│       └── service.py            renders one Asset -> one clip file (ffmpeg)
├── scene_cutter/                (existing, unchanged)
└── video_composer/              (existing, unchanged — reused as the renderer)
```

**Key deviation from the sketch in the task brief, and why:** the brief lists
`beat/`, `asset/`, `motion/` as three flat, top-level siblings of `scene_cutter/`
and `video_composer/`. §1's evidence says that shape is wrong for this
specific trio: Beat and Asset need a real, cascading, `relationship()`-backed
FK (a beat has an ordered list of assets — exactly the `Job`→`Child` shape
every other module in this codebase already uses), and per
`app/modules/README.md` a real FK + relationship across a module boundary
either isn't possible without one module importing the other's ORM class, or
requires quietly bending the "module → module: never" rule. The `ai/`
sub-package precedent exists *specifically* to solve this: things that are
one coherent pipeline with shared internals become sub-packages of one
module, not separate modules. Beat/Asset/Motion are one pipeline (plan →
assign visuals → render motion) the same way Story/Hook/Caption are one
family (three generators sharing a Claude client and a history log). This is
a decision this document is flagging for explicit sign-off, not a silent
substitution — see "Unresolved questions" at the end.

**What is deliberately *not* proposed:**
- No `VideoFactoryService` and no new top-level orchestrator. The pipeline is
  coordinated by the frontend calling three independently-usable module APIs
  in sequence, then handing off to the *existing, unmodified* Video Composer
  API — exactly how a user today manually chains Scene Cutter output into
  Video Composer input by hand. Video Factory automates that chaining in the
  UI; it does not create a new backend service that knows about all four
  modules.
- No new shared "video factory core" package outside `beat/`. `motion/`'s
  ffmpeg helpers are useful only to `asset/`'s render step, so they live
  inside `beat/` (permitted, since they're siblings) rather than as a new
  cross-cutting utility.

## 3. Module responsibilities

**`beat/` (parent module)**
- Owns `BeatPlan` (one row per planning run) and `Beat` (one row per
  narrative segment, ordered, with text + an estimated spoken duration).
- Turns a script into an ordered list of beats. MVP: a deterministic,
  local, non-LLM heuristic (sentence/paragraph boundaries + word-count-based
  duration estimate) — mirrors the "cost-optimized" and "no unnecessary
  abstraction" constraints, and mirrors `video_composer`'s existing
  `_group_words_into_lines` gap/word-count heuristic rather than inventing a
  new technique. Does **not** call `app/modules/ai/story` — it takes plain
  `script_text` as input (typed, pasted, or copy-pasted from an already-
  generated Story version by the user), the same way `video_composer`
  already takes a plain `script` string with no dependency on `ai/story`.
- Owns nothing about visuals or rendering.

**`beat/asset/` (sub-package)**
- Owns `Asset`: one row per beat's assigned visual — `beat_id` FK, a source
  description (existing Library `video_id`, an uploaded file, or a
  `scene_cutter` output path), `file_path`, trim in/out points, and the
  motion parameters to apply (plain nullable columns — see §7, no separate
  motion table).
- Selection UI is backed by the **existing** `/videos` search API for
  Library-sourced assets (reused read-only, never duplicated) and a small
  upload endpoint that copies the existing `scene_cutter.save_uploaded_file`
  / `video_composer.save_input_clips` pattern for user-uploaded stills/clips.
- Explicitly out of scope, per the task's "no AI video generation" / "no
  cloud rendering" constraints: no generated visuals, no stock-footage API
  search. Asset selection draws only from what already exists locally
  (Library, Scene Cutter output, direct upload).

**`beat/motion/` (sub-package)**
- Pure local computation: builds ffmpeg pan/zoom ("Ken Burns") filter
  strings from an `Asset`'s motion parameters, and a small single-worker
  render step (same shape as `scene_cutter`/`video_composer`'s worker) that
  turns one `Asset` into one rendered clip file on disk.
- No database table of its own — motion has no independent lifecycle or
  identity apart from the `Asset` it's rendering (see §7/§9's "no
  unnecessary abstraction" reasoning).
- An `Asset` that is already a video clip (no motion requested, or the
  source is a `scene_cutter` scene) skips this step entirely and is used
  as-is — the same "skip the no-op ffmpeg pass" optimization
  `video_composer` already applies for a single-clip merge.

**`video_composer/` (existing, unchanged)**
- Remains the sole renderer of the final video: merge-with-transitions,
  narrate, subtitle, mix audio, finalize. Video Factory's job is to produce
  an ordered list of per-beat clip file paths and one full script string,
  then submit them to the *existing* `POST /video-compose-jobs` contract —
  identical to what a user does by hand today, just assembled by the new
  pages instead of a manual multi-file picker. See §6 for why no contract
  change is required for the MVP.

## 4. Dependency rules

- `beat/`, `beat/asset/`, `beat/motion/` may import `app/models`,
  `app/services/library` (read `Video`, search via the existing repository),
  and `app/db` — same "module → core, inward only" rule every existing
  module already follows.
- `beat/asset/` and `beat/motion/` may import from `beat/` (their own
  parent's `models.py`/shared helpers) — sibling-sub-package sharing, the
  same relationship `ai/story` has to `ai/claude_client.py`.
- `beat/*` must **never** import `app/modules/ai/*`, `app/modules/scene_cutter`,
  or `app/modules/video_composer`, and none of those may import `beat/*`.
  Where Beat needs to reference something that lives in another module (a
  Story version the user copied a script from, for provenance only), it
  stores a **bare `Integer`, no FK constraint** — the `AIGenerationHistory.job_id`
  / `PublishLog.ai_story_job_id` pattern, not a new one.
- `app/main.py` (composition root) is the only place that constructs and
  starts `beat/asset/`'s and `beat/motion/`'s worker services and mounts
  their routers — same as every existing module.
- The only place that "knows about" both `beat/*` and `video_composer` at
  once is the **frontend** (or, if a server-side convenience endpoint is
  added later, a thin handler at the API layer that calls both modules'
  already-public service methods — not a new shared service class; see §9's
  risk note on this).

## 5. Data flow

```text
1. User provides a script (typed, pasted, or copied from an ai/story
   StoryVersion the user already generated and liked).
      -> POST /beat-plans  { script_text, video_id? (bare int, optional,
                              provenance-only) }
      -> beat.service splits script_text into ordered Beats (local heuristic,
         no LLM call). Persists BeatPlan + Beat rows. Returns immediately
         (no worker queue -- this step is as fast as ai/story's sync path).

2. For each Beat, the user assigns a visual, one of:
      a. an existing Library video (browsed/searched via the *existing*
         GET /videos API, reused unmodified)
      b. a scene_cutter output clip (the user already has the path/known
         file from a prior Scene Cutter job)
      c. a direct upload
      -> POST /beat-plans/{id}/beats/{beat_id}/assets
      -> beat.asset.service persists an Asset row (beat_id FK, file_path,
         trim points, motion params).

3. User triggers render.
      -> POST /beat-plans/{id}/render
      -> beat.motion.service's worker thread renders each Asset with motion
         parameters into <library_dir>/_beat_plans/plan_<id>/beat_<n>/clip.mp4
         via a local ffmpeg pan/zoom pass (Assets with no motion / already a
         clip pass through unchanged -- no redundant re-encode, same
         optimization video_composer already applies for a single input clip).
      -> Poll GET /beat-plans/{id} for status, same 2s-poll convention as
         scene_cutter/video_composer.

4. Hand-off to the existing, unmodified Video Composer.
      -> Once every Beat's clip is rendered, the frontend collects the
         ordered clip paths + the full concatenated script text and calls
         the *existing* POST /video-compose-jobs (frontend/src/api/
         videoComposer.ts, unchanged) exactly as if the user had picked
         those files by hand in today's Video Composer page.
      -> video_composer runs its existing pipeline: merge+transition,
         narrate, subtitle, mix audio, finalize. No code in video_composer
         changes.

5. Result: the same VideoComposeJob polling UI already shipped now shows a
   video that was assembled by an automated Beat/Asset/Motion pipeline
   instead of a manual multi-file picker.
```

No EventBus involvement anywhere in this flow — see §9 for why.

## 6. Proposed contracts

- **`video_composer`'s existing contract is reused unmodified for the MVP**:
  `POST /video-compose-jobs` (`title`, `script`, `voice`, ordered `files[]`,
  optional `music`, `music_volume`, `transition_duration`, `burn_subtitles`,
  `output_dir`). Video Factory's only job is to produce the same shape of
  input a human already produces by hand today — an ordered list of clip
  files and one script string. This is the safest possible extension point:
  zero lines of `video_composer` code change.
- **Safe, additive, optional future extension (explicitly not MVP)**: a
  nullable `source_asset_id: int | None` column on `VideoComposeClip`,
  populated only when a clip originated from a Beat Plan, for traceability/
  debugging ("why does this clip look like this — what Asset/motion made
  it?"). Bare `Integer`, no FK, following §1's established pattern for
  cross-module provenance — never a relationship. This does not change the
  ffmpeg pipeline, request shape, or response shape, so it can land any time
  after the MVP without a compatibility break.
- **Not proposed, and flagged as risky if requested later**: per-beat
  narration/subtitle timing (i.e., `video_composer` accepting a structured
  list of `{clip, narration_line}` instead of one flat script for the whole
  merged output). That's a real contract and pipeline change to
  `video_composer`'s narration/subtitling stage, not an additive one — out
  of scope for this reconnaissance and for the MVP.
- **`beat/` module's own contracts** (new, self-contained, no interaction
  with other modules' contracts):
  - `POST /beat-plans` → `BeatPlanOut` (id, beats[])
  - `GET /beat-plans/{id}` → status + beats[]
  - `POST /beat-plans/{id}/beats/{beat_id}/assets` → `AssetOut`
  - `POST /beat-plans/{id}/render` → 202/started, poll `GET /beat-plans/{id}`
    for per-beat render status (mirrors `scene_cutter`/`video_composer`'s
    status-polling shape, not a new pattern).

## 7. Persistence strategy

Necessary tables (additive only, no changes to any existing table):

| table | purpose | key columns |
|---|---|---|
| `beat_plan` | one row per planning run | `video_id` (bare int, nullable, provenance only — not FK), `script_text`, `status`, timestamps |
| `beat` | one row per narrative segment | `beat_plan_id` FK, `order_index`, `text`, `estimated_duration_sec` |
| `asset` | one row per beat's assigned visual | `beat_id` FK, `source_kind` (`library`/`upload`/`scene_cutter`), `source_video_id` (bare int, nullable, provenance only), `file_path`, `trim_start_sec`, `trim_end_sec`, `motion_type` (nullable), `motion_pan_direction`/`motion_zoom_start`/`motion_zoom_end` (nullable) |

**Not a table**: Motion. It has no independent identity or lifecycle — it's
a rendering instruction that belongs to exactly one `Asset` for exactly as
long as that `Asset` exists. Giving it its own table would be the kind of
unnecessary abstraction the task brief explicitly rules out; a handful of
nullable columns on `Asset` carries the same information with one join
fewer and nothing to keep in sync.

This mirrors the DB doc's own established shape: `scene_cut_job`/
`scene_cut_result`, `video_compose_job`/`video_compose_clip`,
`story_job`/`story_version` are all exactly this "parent run + ordered
child rows" shape — `beat_plan`/`beat`/`asset` is a three-level version of
the same pattern (the extra level exists because Assets belong to a Beat,
not directly to the Plan).

## 8. Filesystem strategy

- Rendered per-beat clips: `<library_dir>/_beat_plans/plan_<id>/beat_<n>/clip.mp4`
  — follows the existing `_video_composer/job_<id>/`, `_local_files/job_<id>/`,
  `_uploads/` convention of a module-namespaced bucket directly under
  `library_dir` (keeps everything reachable through the existing `/media`
  static mount, exactly like `video_composer`'s output).
- Uploaded assets: staged the same way `scene_cutter.save_uploaded_file`
  already does — random filename under the plan's own folder, avoiding
  filename collisions/sanitization concerns.
- Assets sourced from an existing Library video or a Scene Cutter output
  are referenced **by path**, never copied — `asset.file_path` simply points
  at the already-organized file (`library/<platform>/<channel>/<video_id>/video.mp4`
  or a `scene_cut_result.file_path`). No duplication of video bytes for
  Library-sourced assets.
- Nothing here needs a new database entity purely to represent "a file
  exists" — nothing beyond `Asset.file_path` and `VideoComposeJob.output_path`
  (existing). Filesystem-only, no DB row, applies to: the intermediate
  `tmp/` scratch files `video_composer` already deletes after each job (no
  change), and any transient render scratch space `beat/motion/` needs while
  running ffmpeg (should follow the same "own `tmp/`, deleted after,
  `shutil.rmtree(..., ignore_errors=True)`" pattern).

## 9. Risks

- **The flat-vs-nested module structure is a real deviation from the task
  brief's sketch (§2) and needs explicit sign-off before implementation** —
  it's the single biggest judgment call in this document, made on strong
  in-codebase precedent (§1's `ai/` evidence) rather than a guess, but it is
  a deviation and should be confirmed, not silently built.
- **Ffmpeg pan/zoom (`zoompan`) rendering is CPU-bound and can be slow on
  weaker desktop hardware**, especially over a full-resolution image or long
  clip. The existing single-worker-thread pattern (already used by
  `scene_cutter`/`video_composer` for the same reason) caps this to one job
  at a time rather than trying to parallelize on a single desktop — consistent
  with "cost-optimized local," but sets user expectations that a render
  queue, not instant generation, is the shape of this feature.
- **The MVP beat-splitting heuristic (sentence/paragraph + word-count) will
  sometimes produce beats that don't line up with how a human would actually
  pace a script.** Mitigated at the UI/product level (let the user edit beat
  boundaries before assigning assets), not an architecture concern, but
  worth flagging so it isn't mistaken for a bug later.
- **No automatic asset matching or stock-footage search exists or is
  proposed** — per the "no cloud rendering / no external infrastructure"
  constraint, Asset selection is manual, drawing only from what's already
  local (Library, Scene Cutter output, direct upload). If the product
  intent was "automatically find b-roll per beat," that is explicitly out of
  scope for this architecture and would need its own decision (likely
  involving an external API, which the task brief rules out).
- **Bare-`Integer` provenance links (`beat_plan.video_id`, `asset.source_video_id`)
  have no referential integrity** — a deleted Library video silently
  orphans the reference, exactly like `PublishLog.ai_story_job_id` already
  tolerates today. This is a consistent, accepted tradeoff in this codebase,
  not a new risk category, but worth naming explicitly since it will look
  like an oversight to anyone who doesn't already know the precedent.
- **Temptation risk, not a technical one**: the natural next feature request
  ("auto-generate the whole video in one click") will pull hard toward a
  `VideoFactoryService` that imports `beat`, `asset`, `motion`, and
  `video_composer` directly. The frontend-orchestration / plain-data-handoff
  design in §5 is what keeps that from happening — this needs to be a
  conscious choice maintained under future feature pressure, not just an
  artifact of this being an MVP.

## 10. Recommended implementation order

1. `app/modules/beat/` skeleton — `models.py` (`BeatPlan`, `Beat`),
   `schemas.py`, `service.py` (synchronous script→beats split, no worker
   thread needed), `router.py`, mounted in `app/api/v1/router.py`. No
   dependency on any other module. Independently testable/usable before
   anything else exists.
2. `app/modules/beat/asset/` — `models.py` (`Asset`, FK to `beat.id`),
   upload endpoint (copy the `scene_cutter`/`video_composer` staging
   pattern), and a thin pass-through for picking an existing Library video
   (calls the existing `/videos` search, doesn't duplicate it).
3. `app/modules/beat/motion/` — pure ffmpeg filter-builder functions first
   (unit-testable without a worker), then the single-worker render service
   wired into `app/main.py`'s `lifespan` the same way
   `scene_cutter_service`/`video_composer_service` already are.
4. Frontend: a guided Beat Plan page (script in → beat list → per-beat
   asset picker, reusing Library search UI patterns already built for
   `LibraryPage`) → render → call the **existing**
   `frontend/src/api/videoComposer.ts` `createVideoComposeJob` unchanged
   for the final hand-off. This is the step that proves the "no contract
   change needed" claim in §6 for real.
5. Only after the above is proven working end-to-end: revisit whether the
   optional `VideoComposeClip.source_asset_id` traceability column (§6) is
   worth adding, and write the `docs/features/NN-....md` entry for whatever
   actually shipped, per `CLAUDE.md`'s documentation rule.
