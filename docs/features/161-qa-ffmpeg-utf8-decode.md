# 161. Final QA: ffmpeg output decoded as UTF-8

Rendering the new Dai Quan Gia Shorts failed 4 times in a row at FINAL_QA with
`expected string or bytes-like object, got 'NoneType'`, although the video itself
rendered fine. On Windows `subprocess.run(..., text=True)` decodes with cp1252, and
ffmpeg's stderr contained UTF-8 (Vietnamese title/path), so the reader thread died on
an undefined byte (0x90) and `result.stderr` came back `None` -- then `re.search` crashed
in `probe_audio_levels`.

Fix: `encoding="utf-8", errors="replace"` on the two ffmpeg/ffprobe calls in
`backend/app/modules/postqa/renderer.py`. Verified: 84 final_qa/postqa tests pass, and the
two failed runs were retried from FINAL_QA and completed with QA PASS 100.

Not fixed (same pattern, no reported failure yet): other `text=True` subprocess calls in
`composition_render.py`, `asset/ingest.py`, `audio/renderer.py`, `motion/renderer.py`,
`ai/transcribe_client.py`, `voice_test.py`.

Also: `tools/manhua_recap/recap.py build` now accepts `"folder/pNNN.jpg"` panel refs so one
script can reuse already-cut panels from several chapter folders (used by the 3 Short + 1 Long
format in `manhua-series/dai-quan-gia-la-ma-hoang/PLAN_10CH.md`).
