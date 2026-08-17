# 48 — Voice Factory: Local TTS → Beat Timing → Narration Track

**Commit:** `09b3f87`

Adds a new `GENERATING_VOICE` FactoryRun stage (between `ASSIGNING_ASSETS`
and `QUALITY_CHECK`) that turns the project's script into a real narration
track and real per-beat timing:

```
Script -> Local TTS (SAPI5, offline) -> narration.wav -> per-beat timing -> narration_asset_id/start/end on each Beat
```

## Key pieces

- `app/modules/voice/` (new, pure, no cross-module imports): `providers.py`
  (`TTSProvider` abstraction — `LocalTTSProvider` via `pyttsx3`/SAPI5,
  genuinely offline and the default; `EdgeTTSProvider` as an explicit
  opt-in, reusing the existing `edge_tts` dependency), `timing.py`
  (word-count + punctuation-weighted beat timing normalized to real
  measured audio duration, with minimum-duration rebalancing and gapless
  stitching — never equal division, never deletes a beat), `audio_analysis.py`
  (ffmpeg-based normalize/cut/probe/validate, rejects silent or
  zero-duration audio).
- `app/api/v1/endpoints/voice_generate.py` (new composition root): the
  idempotent stage function, content-hash voice fingerprint cache
  (sidecar `narration.meta.json`, not SQLite), per-beat segments
  registered as ordinary local `Asset` rows assigned to the existing
  `Beat.narration_asset_id` field — the render pipeline needed zero
  changes to consume this.
- `Beat` gained `start`/`end` (optional, additive precision on top of the
  existing `duration`). `ProjectConfig` gained `VoiceProjectConfig`
  (provider/voice_id/language/speed/pitch).

## Real bug found and fixed: SAPI5 deadlocks under concurrent threads

`pyttsx3`/SAPI5 hangs indefinitely — not just races — when two threads call
`pyttsx3.init()`/`runAndWait()` at close to the same moment, even with a
fresh COM apartment and a `threading.Lock()` around the call. Reproduced
directly with 2+ concurrent threads. Fixed by routing every synth/list-voices
call through one dedicated worker thread + `queue.Queue`, mirroring
`VideoComposerService`'s own existing single-worker pattern for FFmpeg —
SAPI5 is now only ever touched by one thread for the life of the process.
This matters because the Factory Batch Engine (Task 20) runs multiple
projects' Voice stages concurrently via `ThreadPoolExecutor`.

Also found: the test harness never patched `voice_generate.SessionLocal`,
so an early test run wrote real rows into the live dev database instead of
the isolated test DB — fixed by adding the missing patch (matching every
other module's own patch entry), and the leaked rows were deleted.

## Tests

35 new: `tests/modules/voice/test_timing.py` (16 — weighted estimate,
gapless stitching, minimum-duration rebalancing, word-timestamp alignment
and its fallback), `tests/modules/voice/test_audio_analysis.py` (9 —
silence/format validation), `tests/api/test_voice_stage.py` (11 — real
`pyttsx3` synthesis, idempotency, invalidation, crash recovery, stage-error
translation, full-pipeline integration). Full suite: 646/646 passing
(pre-existing Windows tempdir flake, unrelated).

## Problems

Frontend has a Voice Factory settings section (provider/voice/speed) on
`VideoFactoryPage.tsx` but no "Preview Voice" playback or "Regenerate
Voice" button wired up yet — the `POST /projects/{id}/regenerate-voice`
endpoint exists and is tested, just not called from the UI.

## Next task

Task 23 — Local Motion Engine: Beat Visual → Animated Clip → FFmpeg.
