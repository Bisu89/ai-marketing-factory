# 120. Clean Up the Factory's Per-Beat Render Cache

**Commit:** `8e4c75d`

Real user report: the Asset Library fills up with thousands of
`beat_beat_0X.wav` / `.mp4` rows. Those are the per-beat narration
segments (`voice_factory`, feature 48) and motion clips (`motion_engine`,
feature 49) the Factory registers as ordinary Assets — one set per
project, kept forever, even though every one is a deterministic cache the
Voice/Motion/Audio stages rebuild on the next render.

## What it adds

`POST /assets/cleanup-generated` — unregisters (and by default deletes the
files for) generated per-beat assets belonging to **finished** projects
only: ≥1 COMPLETED render job, none QUEUED/RUNNING. A project that never
rendered, or is mid-render, is skipped and counted separately.

- `sources` (default `["voice_factory", "motion_engine"]`; `ai_image_generator`
  allowed but off by default — an AI image costs money and, unlike the
  deterministic voice/motion passes, regenerates to a *different* image,
  so it's a creative artifact, not a cache)
- `delete_files` (default true) — also unlinks files and removes the now
  fully-regenerable `_voice/_motion/_audio/project_<id>/` dirs wholesale
  (incl. unregistered sidecars: `narration.wav`, `*.meta.json`,
  `audio_master.wav`); `_imagegen/project_<id>/` is swept too only when
  `ai_image_generator` is in `sources`
- `dry_run` (default false) — same counts, no changes; used by the UI to
  preview before confirming

Asset Library page: a **"Clean Render Cache"** header button (dry-run →
`window.confirm` with the MB estimate → real run).

## Key files

- `backend/app/api/v1/endpoints/assets_cleanup.py` (new) — composition root over Asset/Project/BatchItem/VideoComposeJob
- `backend/app/api/v1/router.py` — route registration
- `frontend/src/api/asset.ts`, `frontend/src/pages/AssetLibraryPage.tsx`

## Non-obvious decisions

- **Composition root, not the asset module.** Deciding "is this project
  finished" needs Project + BatchItem + VideoComposeJob — same join
  `produced_videos.py` / `dashboard.py` already do outside the modules.
- **Project id comes from the file path** (`_voice|_motion|_audio|_imagegen/project_<id>/`),
  not a DB link — these assets have no project FK (module isolation).
  Unparseable paths are skipped, never guessed.
- **Beat rows are left untouched** — a stale `narration_asset_id` is
  harmless: with `narration.wav` gone the Voice stage's fingerprint check
  misses and it re-synthesizes from scratch.

## Verification

New `tests/api/test_assets_cleanup.py` (9 tests: eligibility gating,
dry-run, delete_files=False, batch-rendered projects, AI-image opt-in,
unknown source, unparseable path). `pytest tests/modules/asset
tests/api/test_assets_cleanup.py tests/api/test_produced_videos.py` green
(120). `npx tsc -b --noEmit` clean. Not yet exercised against the live
running app (needs a backend restart to pick up the new route).
