# 04 — Library organizer (file layout + metadata.json)

**Commit:** `96dc53d` "Organize completed downloads into library/<platform>/<channel>/<video_id>/"

## What it does

Once a download completes, moves the file into a predictable, browsable
folder structure and writes a `metadata.json` alongside it -- so the library
is real files on disk, not just database rows.

```
library/<platform>/<channel_name>/<video_id>/
  video.mp4
  thumbnail.jpg      (best-effort; download failure doesn't fail the job)
  metadata.json
```

Every video gets its **own** `<video_id>` folder (not just `<channel_name>/`)
specifically so a channel with many videos never collides/overwrites --
confirmed with the user before building.

## Key file

`app/services/library/organizer.py`:
- `sanitize_path_segment()` strips filesystem-illegal characters from
  platform/channel/video-id before they become folder names
- `organize_completed_download()` (downloads): writes thumbnail +
  metadata.json **before** moving the video file, so if either write fails
  the video stays at its original staging path and the task's
  `destination_path` remains valid for a retry
- `organize_imported_file()` (manual imports, added in
  [08-library-backend-api.md](08-library-backend-api.md)): same folder
  layout, but **copies** rather than moves the source file, since an
  imported file is the user's pre-existing file elsewhere on disk

## `metadata.json` shape

```json
{
  "Title": "...", "Author": "...", "Platform": "...",
  "Views": 100, "Like": 5, "Duration": 60, "Upload Date": "2024-06-01",
  "Original URL": "...", "Downloaded Date": "2026-...", "Tags": ["..."]
}
```

Field names/casing match what was explicitly requested, not the internal
Python naming.
