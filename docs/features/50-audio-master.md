# 50 — Audio Master: Narration + Local BGM → Ducking → Final Audio

**Commit:** `TBD`

Adds a new `GENERATING_AUDIO` FactoryRun stage (after `GENERATING_MOTION`,
before `QUALITY_CHECK`) that mixes narration with optional local BGM into
one lossless `audio_master.wav`:

```
narration.wav (Task 22) + optional local BGM -> ducking (sidechaincompress) -> loudnorm -> audio_master.wav
```

Purely local — no AI music generation, no cloud music/audio API.

## Key pieces

- `app/modules/audio/` (new, pure, no cross-module imports): `renderer.py`
  (the mixing engine — duplicates `VideoComposerService._mix_audio`'s own
  proven `sidechaincompress`-based ducking recipe, not imported, per this
  codebase's established module-boundary convention; adds a final
  `loudnorm=I=-14:TP=-1.0:LRA=11` normalization stage), `service.py`
  (`select_bgm` — deterministic tone-tag matching + seeded rotation, no AI
  call), `schemas.py` (`AudioMixPlan`, error codes).
- `app/api/v1/endpoints/audio_generate.py` (new composition root): the
  idempotent stage function, BGM resolution (manual > auto > off), a
  cache fingerprint keyed by narration identity + BGM selection + mix
  config + `MIX_VERSION` ("audio-mix-v1"), sidecar `audio_master.meta.json`.
- `AudioProjectConfig` gained `bgm_mode` (AUTO/MANUAL), `bgm_asset_id`,
  `ducking_ratio`, `fade_in_sec`, `fade_out_sec`, `bgm_missing_policy`
  (OFF/NEEDS_REVIEW). BGM tracks are ordinary `Asset` rows (`type="audio"`,
  matched by `tags`) — no new asset type, no separate music database.

Deliberately produces a standalone artifact and does **not** touch
`composition_render.py`/`video_composer`'s own existing, separate
narration+music mix at final-render time — final video composition is a
later task (per the pipeline diagram, a future COMPOSITE stage is what
would consume this artifact).

## BGM

**Automatic**: deterministic tone-tag matching (`ContentProjectConfig.tone`
against BGM `Asset.tags`, e.g. "warm and reflective" → tracks tagged
piano/soft/emotional) with seeded rotation (`project_id % len(matches)`)
when multiple tracks match or none do — the same project always picks the
same track on retry; consecutive projects visibly rotate through the
library. **Manual**: `bgm_mode="MANUAL"` + `bgm_asset_id` always wins,
never overridden by auto-selection. **Off**: `music_enabled=false` → pure
narration, no silent placeholder track. **Loop/trim**: `-stream_loop -1`
on the BGM input + a hard `-t <narration_duration>` on the whole mix
handles both directions with no separate branch. **Missing BGM**: AUTO
finding nothing suitable never blocks the factory (`bgm_missing_policy`
defaults to `OFF`) — proceeds narration-only, same "near-$0, never block"
principle as every other stage.

## Ducking

`ffmpeg sidechaincompress` (BGM as main input, narration as the sidechain
trigger) — `threshold=0.05, attack=5, release=300` (matching
`_mix_audio`'s own proven values), `ratio` exposed as `ducking_ratio`
(default 8.0). Verified with a real signal-level test: BGM's own frequency
band measured ~7dB louder while narration is silent than while it's
speaking.

## Audio output

WAV, `pcm_s16le`, 48kHz, stereo. Loudness target -14 LUFS, true peak
ceiling -1 dBTP via single-pass `loudnorm` (a practical target, not a
claimed measured broadcast-grade compliance — single-pass loudnorm is an
approximation). Duration always matches narration duration within a
150ms tolerance (enforced by `validate_audio_master`, `AUDIO_DURATION_MISMATCH`
otherwise).

## Cache

SHA-256 over narration file identity (mtime+size) + BGM asset identity
(content-hash or path) + volumes + ducking + fades + `MIX_VERSION`, sidecar
`audio_master.meta.json`. Reused outright when unchanged; any real input
change invalidates Audio → Quality → Render, never Script/Beat/Visual/
Motion/Voice (verified directly: changing BGM leaves `Beat.asset_id`
untouched).

## Recovery

`GENERATING_AUDIO` is a plain `FACTORY_STAGES` value — Task 19's generic
checkpoint/retry/reconcile machinery covers it automatically (verified: a
run stuck at `GENERATING_AUDIO` reconciles to `FAILED`/`FACTORY_INTERRUPTED`
on restart). Quality Gate extension mirrors Task 23's own Motion pattern
exactly: only flags a stale/missing Audio Master (`AUDIO_MASTER_MISSING`,
warning) when a prior run actually claimed to have produced one — never
penalizes a project that simply hasn't run this stage yet.

## Real bug found and fixed during this task

`check_project_quality`'s own `settings: Settings = Depends(get_settings)`
parameter was never actually *read* by any code before this task (Motion's
own per-beat check short-circuits before touching it whenever a beat has
no `asset_id` — true for every zero-beat-project test fixture). Audio's
own check is project-level and always runs, so it was the first caller to
actually dereference `settings.library_dir` — crashing an existing test
that called the route handler directly (bypassing FastAPI's dependency
injection) without a real `Settings` object. Fixed by passing one explicitly.

## Tests

40 new: `tests/modules/audio/test_service.py` (7 — deterministic
selection/rotation), `tests/modules/audio/test_renderer.py` (18 — command
structure, BGM loop/trim/off, real signal-level ducking verification,
clipping/silence detection, duration mismatch), `tests/api/test_audio_stage.py`
(15 — manual/auto/off BGM, idempotency, invalidation, crash recovery,
pipeline integration, a real 5-project batch). Full suite: 770/770 passing
(one pre-existing Windows tempdir flake, unrelated, confirmed by rerun).

## Manual verification

Live server against an isolated scratch database (never the real
`data/library.db`): 5 real projects with 2 beats each, AUTO BGM mode,
completed end-to-end producing 5 valid, correctly-timed `audio_master.wav`
files, all deterministically selecting the one tone-matching track;
FFmpeg process count never exceeded 1 concurrent process. Separately
verified manual BGM override (explicit asset always used, ignoring a
better tone match) and BGM-off (narration-only, `bgm_artifact: null`).

## Cost

External TTS: $0 (local SAPI5, Task 22). External music: $0 (local Asset
Library). External audio mixing: $0 (local FFmpeg). External video
generation: $0.

## Problems

Frontend has no dedicated BGM-mode selector — the existing "Choose Music"
picker does double duty (a picked library track = manual BGM for both the
classic render and the new Factory stage; nothing picked = automatic
selection), which is honest but means a hand-typed music path (not picked
from the library) can't be referenced by the Factory stage and silently
falls back to automatic selection — a small UI label now explains this
rather than leaving it silent.

## Next task

Task 25 — Caption Engine: Script/Timing → Styled Captions → ASS.
