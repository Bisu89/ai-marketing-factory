# 53 — Thumbnail + Metadata: Final Video → Ready-to-Post Package

**Commit:** `69effbf`

Adds a new `PACKAGING` FactoryRun stage (after `RENDERING`, before
`COMPLETED`) that turns a project's own `final.mp4` into a complete,
manually-postable local package:

```
final.mp4
 ↓
candidate frames (10/25/40/55/70/85% offsets) -> scoring (brightness/
contrast/edge-density) -> best frame -> optional headline -> thumbnail.jpg
 ↓
ContentBrief + HOOK beat narration (or a manual override) -> deterministic
title/description/hashtag templates -> metadata.json
```

No AI image generation, no LLM call — every artifact is derived from a
real video frame already produced by the Factory, or content the Factory
already generated in Task 21.

## Key pieces

- `app/modules/thumbnail/` (new, pure + one I/O-owning `renderer.py`,
  mirroring `app.modules.caption`'s own schemas/pure-logic/renderer
  split): `scoring.py` (deterministic brightness/contrast/edge-density
  scoring + rejection, no AI vision); `renderer.py` (real ffmpeg frame
  extraction, real Pillow raster compose/headline/validate).
- `app/modules/metadata/` (new, pure): `service.py` — deterministic
  title/description/hashtag derivation and normalization, manual
  overrides always win.
- `app/api/v1/endpoints/package_generate.py` (new composition root): the
  idempotent, independently-fingerprinted (thumbnail vs. metadata) stage
  function, plus `regenerate-thumbnail`/`regenerate-metadata`/
  `regenerate-package`/`package-overrides` endpoints.
- `app/modules/beat/schemas.py`: `BeatPlan`/`ProjectOut` gained
  `manual_title`/`manual_description`/`manual_hashtags`; `ProjectConfig`
  gained `PackageProjectConfig` (thumbnail headline/candidate-count,
  `max_hashtags`, `platform_profile` — a plain label only, no
  platform-specific behavior).
- `app/modules/factory/models.py`: `PACKAGING` stage; `factory_pipeline.py`'s
  `_on_render_job_completed` now runs Packaging synchronously (still on
  `VideoComposerService`'s own single worker thread — no second queue)
  before marking a run `COMPLETED`.

## Thumbnail architecture

```
final.mp4 -> Candidate Frames -> Frame Scoring -> Best Frame -> Optional Headline -> thumbnail.jpg
```

6 candidate offsets by default (configurable via
`PackageProjectConfig.thumbnail_candidate_count`), extracted via `ffmpeg
-ss`. Scoring is pure arithmetic over Pillow histogram statistics
(brightness/contrast mean+stdev, edge density via a `FIND_EDGES` pass) —
weighted sharpness (45%) + contrast (35%) + brightness-closeness-to-ideal
(20%). Near-black/near-white/flat/blurred candidates are rejected first;
selection is deterministic (ties broken by earliest offset). A real,
uniformly flat/low-detail video (every candidate rejected) falls back to
the least-bad candidate rather than hard-failing the whole stage — see
**Real bug found** below.

## Encoding & cropping

Cover-crop (scale + center crop, never stretch) to the project's own
render-profile dimensions (verified for 16:9/1:1/9:16). No per-frame focal
metadata exists for an arbitrary extracted video frame, so this always
center-crops — section 12's own documented fallback. Headline text
(optional): Pillow `ImageDraw`/`truetype`, deterministic word-boundary
shortening + upper-casing (no LLM), drawn on a fully opaque black banner
(not just a stroke) at the bottom.

## Metadata

- **Title**: manual override → `ContentBrief.core_message` → HOOK beat's
  own narration → project name, word-boundary-truncated, illegal
  filesystem/control characters stripped.
- **Description**: manual override (used verbatim, never has hashtags
  appended) → `[summary]\n\n[CTA]\n\n[hashtags]` template.
- **Hashtags**: manual override → normalized from `ContentBrief`'s own
  topic/angle/emotion/tone (`"#LoveStory"`/`"love story"`/`"love-story"`
  all normalize identically), deduped case-insensitively, capped at
  `max_hashtags` (default 8).
- **Language**: `ContentProjectConfig.language`. **Category**:
  `ContentBrief.topic` (free string) — this codebase's real `Category`
  table is Video-library-level with no FK relationship to a Factory
  Project at all; reusing it would need a genuinely new schema
  relationship, out of this task's "reuse existing" scope. Same reasoning
  already applies to `ContentBrief.emotion` vs. the real `Emotion` table.
- **Platform profile**: a plain label (`general`/`youtube_shorts`/
  `tiktok`/`instagram_reels`/`facebook_reels`), echoed into metadata.json;
  nothing branches on its value (no platform-specific logic exists yet).

## Package

```
<library_dir>/_video_composer/job_<render_job_id>/output/
├── video_hoan_chinh.mp4   (Task 26's own final.mp4)
├── thumbnail.jpg
├── metadata.json
└── package.meta.json      (private cache sidecar, fingerprints only)
```

Right next to the video that already lives there — no second "output"
directory, no file ever duplicated/copied.

## Cache

Two independent fingerprints, `post-package-v1`:
- **Thumbnail**: video file identity (mtime+size) + thumbnail
  dimensions/candidate-offsets/headline text/config + engine version.
- **Metadata**: `ContentInputs` (core_message/cta/topic/angle/emotion/
  tone/hook text/project name) + manual overrides + package config +
  language + video duration/dimensions + engine version.

A description-only edit regenerates metadata.json only; a real video
change regenerates the thumbnail (and, if content also changed,
metadata) — verified directly.

## Invalidation

`Render → Thumbnail → Package` (a new/changed `final.mp4`) and
`Content/Hook/Description/Hashtags → Metadata → Package` are the only two
chains; neither ever touches Motion/Audio/Captions/Render themselves
(section 41's own explicit "do NOT invalidate" list) — nothing about
Packaging's own inputs feeds back upstream.

## Recovery

`PACKAGING` is a plain `FACTORY_STAGES` value — the existing
`reconcile_factory_runs_on_startup` already had a generic "any other
in-flight stage" branch that correctly marks it `FAILED`/
`FACTORY_INTERRUPTED` with zero changes needed. `retry_run` and
`retry_batch_failed` both needed a new, explicit branch for
`failed_stage == "PACKAGING"`: without it, a Retry would silently replay
the *entire* pipeline from `PREPARING`, reaching `_stage_render` again and
genuinely re-rendering the whole video (Task 26 has no render-level
cache) — directly violating section 52's "do not rerender the video."
Both now resume Packaging alone, verified with a real crash-simulate +
retry test confirming `render_job_id` survives unchanged.

## Tests

72 new: `tests/modules/thumbnail/test_scoring.py` (23, including the
fallback-selection tests below), `tests/modules/thumbnail/test_renderer.py`
(16, real ffmpeg/Pillow), `tests/modules/metadata/test_service.py` (32),
`tests/api/test_package_stage.py` (16 — full pipeline, metadata field
shape, manual overrides, cache, invalidation, incomplete package,
independent regeneration, stage-error translation, crash recovery,
batch), plus 1 in `test_pipeline_hardening.py` (unrelated, carried over
from Task 26 bookkeeping). Full suite: 931/931 passing (several different
pre-existing order/timing flakes surfaced across separate full-suite
reruns, each confirmed unrelated by isolated rerun).

Three *existing* end-to-end tests (`test_one_project_five_beats_local_assets_renders_final_mp4`,
`test_running_after_completion_does_not_render_twice_unless_forced`,
`test_create_and_start_run_starts_a_fresh_run_for_a_stale_completed_project`)
initially failed against this task's changes — not because of a code bug,
but because they reached the newly-added PACKAGING stage for the first
time and required a real thumbnail. This directly surfaced the real bug
below rather than needing any test changes once it was fixed.

## Real bug found and fixed during this task

`select_best_frame` originally returned `None` (hard failure,
`THUMBNAIL_NO_VALID_FRAME`) whenever *every* candidate frame tripped the
brightness/contrast/edge-density rejection heuristic. Several existing
end-to-end tests use flat, solid-color synthetic beat images (no
real-world texture at all) — a legitimate edge case, not just a test
artifact, since some real videos (simple text-on-solid-background
content) are genuinely low-detail throughout. Hard-failing the entire
Package stage (and therefore the whole FactoryRun) over a merely
suboptimal thumbnail contradicted this codebase's own repeated "never
block the near-$0 factory over a soft failure" precedent (BGM-missing,
Motion-cache-miss, etc.). Fixed by adding `select_best_frame_with_fallback`:
falls back to the least-bad candidate instead of failing outright, only
raising `THUMBNAIL_NO_VALID_FRAME` when there is truly nothing to choose
from (extraction produced zero frames at all).

A second, purely cosmetic bug was caught by real manual verification (not
by the automated suite, which never renders a full project with real
photographic content and a headline together): the thumbnail's headline
text, drawn near the bottom, visibly overlapped with Task 25's own
burned-in captions sitting in the same region of the source frame — a
stroke alone, and even a 92%-opaque banner, both still let the caption
text ghost through legibly underneath. Fixed with a fully opaque banner
extending to the frame's true bottom edge.

## Manual verification

A real 3-beat project (real ContentBrief, real HOOK beat) run through
Voice → Audio Master → Captions → Final Composer → Packaging: produced a
playable `final.mp4`, a correctly cropped/legible `thumbnail.jpg` (visually
inspected), and a `metadata.json` with a real title/description/4
hashtags/language/category/duration/aspect ratio. Confirmed idempotent
(second call: no regeneration).

## Cost

AI image generation: $0. AI metadata generation: $0. Cloud rendering: $0.
External API: $0. Entirely local FFmpeg + Pillow.

## Problems

Frontend's `ReadyToPostCard` polls `GET .../package` for up to 60s after a
render completes (Packaging is fast in practice, a few seconds, but runs
asynchronously after the render job itself already reports "completed")
rather than being pushed a real completion event — a reasonable, simple
choice given `ProductionProgress` already hands off display responsibility
to the classic render-job UI the instant `render_job_id` is set, well
before Packaging even starts.

## Next task

Task 28 — Final QA + Ready-to-Post: Validate 10–20 Projects → Factory
Completion.
