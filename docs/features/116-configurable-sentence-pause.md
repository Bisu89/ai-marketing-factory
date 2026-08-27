# 116. Configurable Inter-Sentence Pause (Horror Shorts: 0.8s)

**Commit:** `7eb2b40`

Real user review of the Horror Shorts batch: *"các đoạn ngắt không có độ
trễ, gần như đọc liên tục, không có nhấn nhá horror"* — the narration ran
sentence-into-sentence with no dramatic beat between them.

## Cause

`app.modules.voice.providers` spliced a **hardcoded** `_INTER_SENTENCE_PAUSE_SEC
= 0.35` between sentences/beats — fine for a warm story read, too clipped
for horror pacing, and not tunable anywhere.

## Fix

- New `VoiceProjectConfig.sentence_pause_sec` (default `0.35` → every
  existing template unchanged), 0–2.0s, folded into `voice_fingerprint`
  so a change re-synthesizes.
- `TTSProvider.synthesize(...)` (both `LocalTTSProvider` / `EdgeTTSProvider`
  and the `_TTSWorker` proxy) takes `sentence_pause_sec`, defaulting to
  the old constant so non-Factory callers are untouched. `voice_generate`
  passes the project's value through.
- `horror_shorts` template → `sentence_pause_sec=0.8`.

Beat timing stays correct automatically: `compute_beat_timing` works off
the *measured* narration duration + real edge_tts word timestamps, both
of which already reflect the longer gaps.

## Key files

- `app/modules/beat/schemas.py` — `VoiceProjectConfig.sentence_pause_sec`, template
- `app/modules/voice/providers.py` — threaded through both providers + worker
- `app/api/v1/endpoints/voice_generate.py` — fingerprint + synthesize call
- `tests/api/test_voice_stage.py` — fingerprint-invalidation test + fake provider signature

## Verification

`tests/modules/beat`, `test_voice_stage.py`, `tests/modules/voice` green (131).
