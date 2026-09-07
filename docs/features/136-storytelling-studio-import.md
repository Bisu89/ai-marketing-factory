# 136. AI Storytelling Studio — import a written story (skip the AI pipeline)

The planning pipeline (feature 133) makes 5+ paid LLM calls per story. A
content shop that already writes its stories in ChatGPT (a flat
subscription, no per-token API charge) shouldn't pay for that again. This
adds a paste-your-own path: the deterministic Scene Director + cost +
Produce steps are unchanged, only the LLM authoring is skipped.

## What it does

- **`POST /stories/{id}/import`** (`?replace=true` to overwrite) — takes a
  JSON package (`story_bible`, `style_bible`, `characters`, `locations`,
  `chapters` → each with `scenes`) and materialises it as real rows in one
  transaction:
  - character / location names in a scene are resolved to real row ids
    (unresolved names are reported, not fatal)
  - unknown `scene_type` → `BODY`; `duration_hint` clamped to 2–20 s
  - the story jumps straight to `status = "SCENES_READY"`
- **Frontend** — an "Import script" button on `/studio/:storyId` opens a
  modal with a one-click **"Copy the ChatGPT prompt"** (the prompt embeds
  the exact JSON schema) and a paste box; client-side `JSON.parse` guard
  before submit; a "replace existing" checkbox when the story already has
  content.

After import: **Re-run Scene Director → review → Produce**, exactly as a
pipeline-planned story. The only remaining cost is the AI images at
produce time (~$0.006 each, less with reuse) — $0 if the user supplies
their own images too.

## Key files

- **New:** `frontend/src/pages/StudioImportModal.tsx` (holds the ChatGPT
  prompt), `tests/modules/story/test_import.py`
- **Modified:** `app/modules/story/schemas.py` (`StoryImportIn` +
  `Import*` nested models, `extra="ignore"` so a slightly-off paste still
  imports), `app/modules/story/service.py`
  (`import_story_package`), `app/modules/story/router.py` (endpoint),
  `frontend/src/api/story.ts`, `StudioStoryPage.tsx`

## Non-obvious decisions

- **The importer lives in the `story` module, not a composition root** —
  it only touches `story`'s own tables (bible / characters / chapters /
  scenes), needs no `beat` / `ProjectConfig`, so it's plain module CRUD.
- **One session, all-or-nothing.** A malformed chapter partway through
  must not leave a half-imported story — the whole map runs in a single
  transaction and `db.flush()` per row is only to get the ids for
  name-resolution within the same transaction.
- **`extra="ignore"` on every import model.** ChatGPT reliably returns the
  right *shape* but often adds a stray key; rejecting the whole paste over
  one extra field would be hostile.

## Verification

6 import tests + 52 story-suite tests pass. HTTP smoke: create story →
`POST /import` a 2-scene package → 1 character / 1 location / 1 chapter / 2
scenes materialised, `status = SCENES_READY`; `POST /classify-scenes` then
runs the Scene Director on the imported scenes with **zero LLM calls**.
`npx tsc -b --noEmit` clean; `npm run build` succeeds.

## Landed in

`093d4bd`
