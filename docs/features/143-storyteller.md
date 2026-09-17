# 143. Kể Truyện (Storyteller): paste/upload script -> narrated video

Long-form "đọc truyện" (audiobook-style) video production. No AI call
anywhere in this module -- the script is written externally (ChatGPT, a
translated novel, anything) and pasted or uploaded as plain `.txt`; the
app only does TTS + local ffmpeg compositing. Real cost per episode:
narration is free (Edge TTS), render is free (local ffmpeg) -- $0 per
video, matching the niche's actual economics (discussed, not built,
until the user asked for the paste-text input path directly).

**Key files**
- `backend/app/modules/storyteller/` — `models.py` (`StorytellerEpisode`,
  `StorytellerAsset`), `service.py` (chunking, edge_tts narration with
  retry, word-timed ASS captions, ffmpeg compositing with background
  loop + colour-keyed avatar overlay, own queue/worker thread), `router.py`,
  `schemas.py`.
- `backend/alembic/versions/0003_storyteller.py`
- `frontend/src/pages/StorytellerPage.tsx` (+ `/storyteller` route,
  sidebar link, `api/storyteller.ts`, `types/storyteller.ts`)

**Pipeline per episode:** script_text -> split into TTS-safe chunks
(paragraph -> sentence -> hard word-boundary fallback, so a chunk never
exceeds the target size even with zero punctuation) -> edge_tts each chunk
(word-boundary timestamps) -> concat into one narration track -> optional
word-timed ASS captions -> composite: background loop (uploaded clip,
scaled/cropped to 1920x1080, or a generated solid colour if none given) +
optional avatar clip overlaid via ffmpeg's `colorkey` filter (background
colour auto-sampled from the clip's corner pixel at upload time) + burned
captions -> `final.mp4`.

**Non-obvious decisions**
- **Own tables, no reuse of `app.modules.asset`.** Background/avatar clips
  are a tiny self-contained `StorytellerAsset` table, not the Video
  Factory's Asset Library — per the module-isolation rule ("a module may
  never import another module"), and this module's needs (loop clips,
  colour-key metadata) don't match Asset's shape anyway.
- **Auto colour-key, not a fixed green-screen requirement.** The uploaded
  avatar clip's own background colour is sampled automatically (1 frame ->
  corner pixel) at upload time and stored on the asset, so any solid-colour
  background works, not just green screen.
- **Hard word-boundary chunk fallback.** A text chunker that only splits on
  punctuation can silently produce a chunk far over the target size for
  text with long unpunctuated runs — caught by a real test failure during
  verification, fixed with a last-resort whitespace split.
- **Own duplicated ffmpeg/narration helpers**, not imports from
  `app.modules.video_composer` — same "duplicate, don't import across
  modules" convention already established for `caption.ass_writer` /
  `audio.renderer` vs `video_composer`.

**Verified:** 21 unit/integration tests (chunking edge cases incl. the
punctuation-free fallback, caption grouping, real-ffmpeg composite in 4
shapes — generated background, file background, avatar colour-key +
captions together, exact duration trim) + a full real HTTP round-trip
(`TestClient` -> real edge_tts -> real ffmpeg -> `completed` -> file
download) on an isolated temp DB/library dir.
