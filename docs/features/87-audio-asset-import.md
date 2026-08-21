# 87. Add Support for Importing Audio (Music) Assets

**Commit:** (pending)

Real user report: no way to import a music track for background music at
all. Asset already treats `type="audio"` as first-class (narration/audio
master are both registered this way, and `AssetLibraryPage`'s tile
already had a dedicated Music-icon branch for it), but the Asset
Library's own "Add Assets" import (folder scan or pasted file paths)
only ever recognized image (`.jpg/.jpeg/.png/.webp`) and video
(`.mp4/.mov/.webm`) extensions -- every existing audio Asset in the
system had been registered programmatically (Voice Factory's own
narration/Audio Master), never by a user through the UI.

## Fix

Added `SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac",
".ogg"}` (`app/modules/asset/ingest.py`), folded into the existing
`SUPPORTED_EXTENSIONS` union the import folder-scan already filters
against. Added `extract_audio_metadata()`, mirroring
`extract_video_metadata()`'s own ffprobe shape minus the video-only
fields (duration + codec only -- width/height stay `None`, exactly like
every pre-existing audio row already has). `import_service.py`'s
`_process_one_file` gained a third branch alongside image/video: no
thumbnail generation for audio (matches the frontend's existing
Music-icon fallback for any asset with no `thumbnail_path`).

No frontend changes needed -- `AssetLibraryPage.tsx`'s tile rendering
and the "Add Assets" modal (folder or pasted-paths mode) were already
generic; only the backend's own allow-list was missing audio.

## Verification

New unit tests (`tests/modules/asset/test_ingest.py`):
`extract_audio_metadata` against a real ffmpeg-generated mp3 (duration/
codec extraction) and against a corrupt file (raises
`FileOperationError`). Real (non-mocked) Playwright run against the
actual running app: generated a real mp3 via ffmpeg, imported it through
the real "Add Assets -> Add Files" flow, confirmed "Import complete -- 1
imported, 0 duplicates, 0 failed" and the new tile rendering with the
Music icon in the live library -- then deleted the throwaway asset
afterward. Full backend suite green.
