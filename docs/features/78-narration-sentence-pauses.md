# 78. Narration Sentence Pauses (Fix Monotone Voice)

**Commit:** `pending`

Real user report: narration ("giọng đọc") sounded flat/robotic
("đều đều không có hồn") regardless of voice choice. Root cause: both
`LocalTTSProvider` (SAPI5) and `EdgeTTSProvider` synthesized the entire
script as one unbroken pass at one constant rate -- no breath between
sentences at all, which is what a monotone track actually is
mechanically, independent of voice quality.

## Fix

`app/modules/voice/providers.py` only -- `voice_generate.py`/`timing.py`
untouched, since `TTSProvider.synthesize()`'s external contract didn't
change. Both providers now split narration into sentences
(`_split_sentences`, simple punctuation-based) and synthesize each one
separately, then splice the resulting WAV segments back together with a
real silent gap (`_INTER_SENTENCE_PAUSE_SEC = 0.35s`) via
`_concat_wav_with_pauses` (pure stdlib `wave`, no ffmpeg). Falls back to
the exact original one-shot path when there's only one sentence.

## Two real bugs found and fixed during verification (not theoretical)

1. **edge_tts pads each request's own trailing silence inconsistently**
   (confirmed by direct measurement: up to ~0.85s on one segment, ~0.1s
   on another, same voice/settings) -- stacking that on top of the
   inserted pause produced wildly inconsistent gaps (0.2s-1.3s) in an
   early build. Fixed by trimming each segment to its own real last
   `WordBoundary` end (+0.08s buffer) before splicing, so the actual gap
   is `_INTER_SENTENCE_PAUSE_SEC`, precisely, every time (SAPI5 has no
   word-boundary data, so its segments use their full un-trimmed length).
2. **SAPI5/pyttsx3's "save to file" driver mode hangs indefinitely on a
   second `runAndWait()` call**, even from a brand-new `pyttsx3.init()`
   engine instance in the same COM apartment -- reproduced directly with
   a guarded, timeout-wrapped script. Distinct from `_TTSWorker`'s
   already-documented multi-*thread* deadlock; that fix (one dedicated
   worker thread) does not by itself cover this single-thread bug. Fixed
   by a full `pythoncom.CoUninitialize()`/`CoInitialize()` cycle between
   every segment -- confirmed safe nested inside `_run()`'s own
   thread-lifetime `CoInitialize` (COM reference-counts these per
   thread).
3. edge_tts's free/unofficial WebSocket API is also intermittently flaky
   under back-to-back requests (`NoAudioReceived`, confirmed directly);
   splitting one call into N multiplies the exposure. Added a bounded
   retry-with-backoff (4 attempts) around each segment so this change
   doesn't make narration generation *less* reliable overall.

## Verification

Real synthesis end to end for both providers (no mocks): edge_tts
Vietnamese narration (`vi-VN-HoaiMyNeural`, 4 sentences) -- real detected
gaps of ~0.55s at all 3 sentence boundaries (0.35s configured + the
trim buffer + edge_tts's own small residual lead-in), consistent across
runs after the trim fix, versus 0.2s-1.3s before it. SAPI5 English
narration (4 sentences) -- real 9.0s WAV output, correct format, no
hang, run through the actual worker thread (not a bypass). Existing
suites re-run unchanged and green: `tests/modules/voice/test_timing.py`
(16), `test_audio_analysis.py` (9), `tests/api/test_voice_stage.py` (14,
includes real narration generation) -- confirms the change doesn't
regress per-beat timing, caption alignment, or the Factory pipeline's
own Voice stage.

`python -c "import app.main"` clean.
