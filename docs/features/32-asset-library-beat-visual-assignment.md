# 32 — Asset Library + Beat → Asset Assignment

**Commit:** _(fill in after commit)_

## What it does

Makes the Video Factory's Visual step (Step 3) functional: pick a local
image for a Beat from a searchable asset browser, preview it, remove it,
and have the choice persist through `beats.json`. Closes the gap between
Beat's existing `visual_hint` (a text description, Task 1) and an actual
picked image.

## Architecture: reused the existing Asset module, not the download Library

The brief warned against creating a second media library and asked me to
check whether "the existing Library" already covers this. This repo
actually has two candidate things named similarly:

1. **`app/services/library/` + `app/models/video.py`** -- the downloaded-
   video catalog (platform, channel, thumbnails from yt-dlp). Built for a
   completely different concept (a downloaded social video), not "an
   arbitrary local image the user wants as a Beat's background."
2. **`app/modules/asset/`** -- already built in an earlier task
   ([20](20-asset-module.md)) specifically as "a self-contained local asset
   library for the future Video Factory": register any local file by path,
   tag it, search it, `Asset.id` as a stable int PK. This is exactly the
   "one source of truth for local media assets" the brief asks for.

So the real decision wasn't "build a Library or reuse it" -- it was
confirming `app/modules/asset` (not the video-download Library) is the
right existing thing to extend, and not creating a third system. Only two
small additions were made to it: `AssetService.get_image()` (get + reject
non-image, one method, fully tested) and `GET /assets/{id}/file` (streams
the actual bytes -- needed because `Asset.path` can point anywhere on
disk, outside the `/media` static mount's `library_dir`, so the existing
metadata-only `GET /assets/{id}` can't serve a previewable image URL by
itself). No new module, no new table, no new generic AssetService.

## Beat contract change

`Beat` gained one field: `asset_id: int | None = None` (positive-int
validator, same pattern as duration bounds). Deliberately **flat**, not
nested under a `visual: {asset_id}` object as the brief's own illustrative
JSON showed -- Task 1 already established Beat as a flat-fields contract
(dropping the old nested `visual`/`motion`/`caption`/`audio` shape), and
reintroducing nesting for one field would be a bigger, less minimal change
than the brief's own "extend minimally, do not redesign the Beat schema"
asks for. `app.modules.beat` still does not import `app.modules.asset` --
`asset_id` is a bare int, resolved by whoever has both (the frontend, via
two small API calls).

## Visual flow

```
Beat (asset_id: null)
  -> Visual step: "Choose asset" opens AssetBrowserModal
  -> modal searches GET /assets?asset_type=image (existing endpoint,
     unchanged) and/or registers a new path via POST /assets (existing
     endpoint, unchanged)
  -> select a tile -> onChange({ assetId, assetPath, assetStatus: "registered" })
  -> WorkingBeat now carries assetId; Save serializes it as Beat.asset_id
  -> beats.json persists it
  -> reload: workingBeatFromDTO reads asset_id back, then
     resolveAssetReferences() batch-fetches GET /assets/{id} for every
     beat once, patching assetPath/assetStatus/assetError -- a missing or
     since-retyped-non-image asset becomes assetStatus:"error", rendered
     as "Asset unavailable" instead of crashing or silently dropping the
     reference
  -> preview image itself loads from GET /assets/{id}/file
```

`WorkingBeat.assetId/assetPath/assetStatus/assetError` are the same fields
Task 09's original manual-path flow already used for the render step's
`Scene.source_asset_id` -- reused as-is, so `buildCompositionPlan`/the
render step needed zero changes.

## Key files

`backend/app/modules/beat/schemas.py` (+`asset_id`), `backend/app/modules/asset/service.py`
(+`get_image`), `backend/app/modules/asset/router.py` (+`GET /assets/{id}/file`),
`backend/tests/modules/asset/{test_service,test_router}.py` (+8 tests),
`backend/tests/modules/beat/test_schemas.py` (+3 tests), `frontend/src/components/AssetBrowserModal.{tsx,css}`
(new -- mirrors the existing `FolderBrowserModal`'s overlay/modal
conventions), `frontend/src/api/asset.ts` (+`getAsset`, `+assetFileUrl`),
`frontend/src/pages/VideoFactoryPage.tsx` (+`.css`) (`VisualsEditor`
rewritten around the new modal; old manual path-input UI removed --
"register a new path" survives as a secondary affordance inside the
modal itself).

## Tests

Backend: 8 new tests (`GetImageTests` x4: valid image, missing asset,
video/audio rejected; `GetAssetFileTests` x4: success, missing asset,
non-image rejected, file-deleted-from-disk) plus 3 new `Beat.asset_id`
tests (valid/zero/negative) and an updated serialization test asserting
`asset_id` round-trips through `beats.json`. `python -m unittest discover
-s tests` -- **257 tests, all passing** (246 prior + 11 new).

Frontend: no test framework in this repo -- verified manually (below).

## Manual verification

Real Playwright run against the live dev servers, using two real (solid-
color placeholder) JPEGs: selected beat 1 → opened the asset browser →
registered+selected an image → preview rendered the real image → badge
appeared in the Beats list → repeated for beat 2 with a second image,
confirming both images are searchable/reusable → Save → full page reload
→ both assets restored correctly (image re-rendered, not "unavailable")
→ removed beat 1's asset → Save → reload again → confirmed the removal
also persisted (no stale reference, other beat unaffected). All 13 checks
passed, zero console errors, zero bugs found.

## Architecture confirmation

- No second media library was created; `app.modules.asset` (already
  existing) was extended by two small, well-tested methods.
- No module-to-module imports: `app.modules.beat` still doesn't import
  `app.modules.asset`; the frontend is what holds both an `asset_id` and
  the ability to resolve it, same pattern as `composition_render.py`'s
  adapter role for other cross-cutting concerns in this codebase.
- No unrelated refactor: only the Visual step's own UI and the two asset
  endpoints changed; Script/Beats/Audio/Render steps, motion, rendering,
  and the video-download Library are untouched.

## Next task

Task 5 -- Motion Presets + Beat → Motion Assignment.
