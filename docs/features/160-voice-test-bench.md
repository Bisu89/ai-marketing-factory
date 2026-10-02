# 160 — Voice test bench ("Thử giọng đọc")

New sidebar page: paste a story, pick a voice and speed, get an MP3 to play or download. Default voice is Vietnamese female (`vi-VN-HoaiMyNeural`), speed 0.5x–2.0x. Made to audition story narration without creating a project.

Commit: "feat: voice test bench page (paste story -> MP3)".

Key files: `backend/app/api/v1/endpoints/voice_test.py`, `frontend/src/pages/VoiceTestPage.tsx`, `frontend/src/api/voiceTest.ts`.

Design notes:
- Reuses `EdgeTTSProvider` (sentence splitting, retries, process-wide edge_tts semaphore) instead of one raw edge_tts call, because a long story in a single request hits the same flaky-WebSocket failures documented for Zombie System Ch8. The WAV it produces is encoded to MP3 with the bundled ffmpeg and saved under `<library_dir>/_voice_test/`.
- Synthesis of a ~2000-word story takes minutes, so POST starts a background thread and returns a job id; the page polls `GET /voice-test/jobs/{id}`. Jobs are in-memory (lost on restart; the MP3 files stay on disk).
- Lines starting with `##` (scene notes in the story scripts) are dropped, so a script file can be pasted as-is.

Verified: real synthesis of a short text at 1.2x returned a valid MP3 (ID3 header, `audio/mpeg`), `##` line stripped, empty text rejected; `npx tsc -b --noEmit` clean.
