# 41 — Local Asset Ingestion + Smart Library Preparation

**Commit:** _(fill in after commit)_

Lets a user import a whole folder of local images/videos into the existing
`app.modules.asset` library in one action: dedup by SHA-256 content hash
(not filename), real metadata extraction (dimensions, EXIF-aware
orientation, duration/fps/codec for video), a generated thumbnail per
asset, and filename/folder-derived tags + category/emotion inference —
all $0, no external API. Runs as a background job with real progress,
cancel, and an import report; one corrupt file never stops the rest.

## Key finding: Task 14 doesn't exist

This task's brief assumes a `VisualIntent`/`AssetMatcher`/`AssetSuggestion`
system ("Task 14") already exists and repeatedly asks to "run the Task 14
matcher" for verification. A full-repo search turned up nothing — no such
module, no such doc (`docs/features/` stopped at this session's Task 13).
Per the user's own direction after this was flagged, this task shipped
ingestion only; verification substitutes the closest real thing —
`AssetService.search()`'s keyword scoring (Task 20) — which the new
ingestion metadata directly improves without any matcher-side changes.
**Task 14 should be built before Task 16.**

## Non-obvious decisions

- **Reference, don't copy.** `Asset.path` was already documented as "a
  reference to a file the user picked, not something this app owns a copy
  of" (Task 20). Ingestion follows that existing convention rather than
  copying files into a managed `library/assets/` folder.
- **New columns on the existing `Asset` table** (`content_hash`,
  `orientation`, `category`, `emotion`, `status`, `thumbnail_path`), not a
  second asset table — `Base.metadata.create_all()` only creates missing
  tables, so a new `app/db/migrate.py` does one idempotent `ALTER TABLE
  ... ADD COLUMN` per new column against the real, already-populated dev
  DB (the first time this app has needed a column-level migration, not
  just a new table).
- **Category/emotion reuse the real, existing catalogs** (`app/db/seed.py`:
  categories are `Couple/Family/Military/Proposal/Transformation/Comedy/Other`;
  emotions are Vietnamese — `Vui/Cảm động/Hài hước/Buồn/Kịch tính/Trung
  tính`) as plain string values (no FK — `app.modules.asset` still imports
  nothing from `app.models`), not the brief's own illustrative
  English/generic examples, which don't match this app's real catalogs.
- **Cancellation is in-memory** (`threading.Event`, mirroring
  `VideoComposerService._cancel_events`), not a DB flag re-queried from
  inside the import thread's own session — a real bug was found and fixed
  during testing where polling a `cancel_requested` DB column from inside
  a long-running SQLite transaction never observed another session's
  commit, and separately where the cancel *request* itself could block for
  the entire import's duration on SQLite's single-writer lock.
- **Per-file SAVEPOINTs** (`db.begin_nested()`) around each asset insert —
  found and fixed a real bug where one corrupt file's rollback was wiping
  out every *other* successfully-imported-but-not-yet-committed file in
  the same progress-commit batch.
- Import runs as a background thread spawned on demand (matching Task 13's
  batch beat-generation pattern), not a second persistent queue/worker.

## Tests

491 backend tests passing (up from 490): 41 for `ingest.py` (metadata,
EXIF orientation, thumbnails, tokenization, category/emotion inference,
hashing), 18 for `import_service.py` (100-file bulk import with
duplicates/invalid, dedup, cancel, rescan, plus a regression test for a
real bug found in manual verification below), 12 router tests
(import/cancel/rescan/thumbnail/filters), and 2 integration tests proving
Ingestion → Library → the existing `search()` scoring ranks relevant
assets above unrelated ones for real. Frontend `tsc --noEmit`: 0 errors.

## Manual verification (real, not simulated)

Real backend+frontend dev servers, driven with Playwright, against the
real dev DB (which already had 20 pre-existing assets from Task 13). Built
a real 110-file fixture folder (100 unique images across
`couples/family/emotional/military/proposal/misc` subfolders, 5 exact
duplicates, 5 corrupt files) and imported it via the real "Add Assets →
Import Folder" UI: **result was exactly 100 imported / 5 duplicates / 5
failed in 3.3s**, with the first failure's real error message shown.
Searched `woman,gift,surprise` and confirmed the real ranking (the one
asset with all three exact tags ranked first, unrelated assets excluded).
Opened the detail panel and confirmed real dimensions (1080×1920), real
`PORTRAIT` orientation, real "Excellent for 9:16" suitability, real
inferred tags/category/`Family`/emotion. Deleted a real imported file from
disk and ran Re-scan: correctly reported it `MISSING` with a broken-image
tile in the grid. Re-scan also touched the 20 pre-existing legacy assets
(never checked before) and caught a **real bug live**: 6 real, healthy
`.mp3` assets got marked `INVALID` because re-scan force-probed every
non-image asset as video (no video stream in an audio file → ffprobe
failure). Fixed in `import_service.py`, added a regression test, verified
against the live server that a second re-scan correctly restored all 6 to
`ACTIVE`.

## Cost

External API calls: 0. External cost: $0. Hashing (`hashlib`), metadata
extraction (Pillow + ffprobe, both already-vendored/bundled), thumbnails
(Pillow + ffmpeg), and tagging (pure lexical rules) are all local.

## Problems

- Task 14 doesn't exist (see above) — the biggest open item.
- The existing render pipeline (`app.modules.motion.renderer`) doesn't
  read EXIF orientation at all; ingestion now reports the *visually*
  correct orientation/dimensions for Library filtering, but a phone photo
  with EXIF rotation could still render sideways until that renderer gap
  is separately addressed (out of this task's scope — noted, not fixed).
- "Used in N Beats" (section 36) was not built: Beat→Asset usage lives
  inside `beats.json`/`Project.beat_plan_json` blobs, not an indexed
  column, so a real count would mean scanning every project's JSON rather
  than "a simple query" as the brief assumed.

## Architecture

Existing `app.modules.asset.Asset` table reused (no second asset model),
existing `AssetService.search()` reused as the de facto matcher (no
`AssetMatcher` built), existing Category/Emotion *values* reused (no
schema coupling). No vector DB, no embeddings, no CLIP, no AI image
classification, no second import queue, no Redis/Celery, no
module-to-module imports — `app.modules.asset` still imports nothing from
any other module.

## Next task

Task 14 — Asset Automation: Beat → Visual Asset Assignment with
Local-First Strategy (recommended ahead of Task 16, since Task 16 —
Content Intelligence: Beat Quality Gate + Visual Coverage Score — would
also depend on matching infrastructure that doesn't exist yet).
