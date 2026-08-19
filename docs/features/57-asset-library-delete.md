# 57 — Asset Library: Delete Action

**Commit:** _(fill in after commit)_

The backend `DELETE /assets/{id}` endpoint already existed
(`app/modules/asset/service.py`'s `delete()`) but had no frontend UI at
all — the Asset Library page had no way to remove an asset.

## What it does

A "Delete" button in the asset detail panel (opened by clicking a tile),
with a confirm dialog explaining the real behavior: it only unregisters
the asset from the library's database — the actual file on disk is never
touched (`AssetService.delete()` only does `db.delete(asset)`), so it's
safe/reversible by re-importing. Any beat currently referencing the
deleted asset will show a broken/missing reference, same as an asset
whose file was moved or deleted externally.

## Files

`frontend/src/api/asset.ts` (new `deleteAsset()`),
`frontend/src/pages/AssetLibraryPage.tsx` (`AssetDetailPanel` gained the
button + confirm/error handling, refreshes the grid on success).

## Cleanup done alongside this

Removed 120 synthetic test-fixture images (`proposal_ring_engagement.jpg`,
`ocean_waves_beach.jpg`, etc.) left over from earlier tasks' manual
verification, at the user's request — via the same DELETE endpoint, not a
DB script. Video/audio assets (auto-generated render/motion clips) were
left untouched, matching the requested scope.
