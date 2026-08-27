# 115. Horror Shorts Template → edge_tts (captions lock to narration)

**Commit:** `0824049`

Real user report on the first Horror Shorts batch: *"chữ chạy lệch/giật so
với giọng"* — the word-by-word captions drift and jitter against the
voice, worse toward the end of a beat.

## Cause

The `horror_shorts` template used `provider="local"` (offline SAPI5). The
Caption Engine ([51](51-caption-engine.md)) segments and times captions
from **real per-word timestamps** when it has them ([62](62-caption-real-word-timing.md),
[92](92-caption-drift-fix.md)) — but only `edge_tts` emits `WordBoundary`
events. Local TTS gives none, so captions fall back to a weighted
text-length **estimate** that visibly drifts on these fast, 3–5s,
twist-driven cuts with a `word_highlight` preset.

## Fix

`horror_shorts` template `voice` → `edge_tts` / `en-US-GuyNeural`
(calm low male read, suits the deadpan tone), `version` 1 → 2. Still $0
(edge_tts needs internet, no API key). Local is still selectable per
project. Non-`horror_shorts` templates unchanged.

## Key files

- `app/modules/beat/schemas.py` — `HORROR_SHORTS_TEMPLATE.config.voice`, version bump

## Verification

`tests/modules/beat` green (90). Re-ran the two real test videos through
the Factory pipeline with the new voice (cached AI images reused, $0):
both `COMPLETED` / Quality READY / QA PASS, captions now segmented on
edge_tts's real word timings instead of the estimate.
