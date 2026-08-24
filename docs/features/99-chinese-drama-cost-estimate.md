# 99. Chinese Drama: Real Per-Video Cost Estimate

**Commit:** `df8d5a9`

Real user follow-up right after Chinese Drama mode shipped (doc 98):
"after it finishes, can I see an estimate of how much this cost?"
Chinese Drama mode is the first Video Composer job type with a genuinely
billed external call (ASR + LLM) -- every other job type's only external
call is edge-tts, which is free, so `external_api_cost_estimate` had never
needed a real number before.

## Design

`DubResult` (`chinese_drama_dub.py`) gains `estimated_cost_usd: float | None`,
computed as ASR cost + LLM cost:
- **ASR**: `app/modules/ai/transcribe_client.py`'s new
  `estimate_transcription_cost_usd(duration_seconds)`, a flat
  `$0.006/minute` estimate (unconfirmed -- OpenAI has no public per-minute
  price for `gpt-4o-transcribe`; ballparked against whisper-1's
  long-published rate, same "seed a labelled estimate rather than leave it
  null" convention `app.modules.ai.pricing`'s own module docstring already
  established). Audio duration is probed via `ffprobe` right after
  extraction.
- **LLM**: reuses the existing `app.modules.ai.pricing.call_cost_usd`
  (the same infra Package AI Metadata, doc 97, already uses) --
  **every** repair-retry attempt's cost is accumulated, not just the
  final successful one, since an invalid attempt still burns real tokens.

The estimate is written onto the job (`VideoComposeJob.estimated_cost_usd`,
new column) as soon as translation succeeds, alongside title/script_text/
hook_text -- so it's preserved across a retry (no ASR/LLM re-call means no
new cost to compute) exactly like those fields already are.
`_write_render_report`'s `external_api_cost_estimate` now reports this
real number for Chinese Drama jobs instead of always being `null`
(unchanged for every other job type, which still has no real cost to
report).

## Key files

- `app/modules/ai/transcribe_client.py` -- `TRANSCRIBE_PRICE_PER_MINUTE_USD`, `estimate_transcription_cost_usd`, `probe_audio_duration`
- `app/api/v1/endpoints/chinese_drama_dub.py` -- `DubResult.estimated_cost_usd`, cost accumulation across repair retries
- `app/modules/video_composer/models.py` -- new `estimated_cost_usd` column
- `app/modules/video_composer/service.py` -- threaded through `create_job`/`retry_job`/`_write_render_report`
- `frontend/src/pages/VideoComposerPage.tsx` -- shown on the job status line (`~$0.0029`)

## Verification

3 new tests in `tests/api/test_chinese_drama_dub.py` (mocked): a successful
run reports a positive cost, longer audio costs more, a repair-retry's
cost is included in the total (not dropped). Existing pipeline/lifecycle
tests updated for the new `DubResult.estimated_cost_usd` field. Real
(billed) end-to-end run through the actual app: a ~6s test video with real
synthetic Chinese speech produced `estimated_cost_usd: 0.002864`, matching
`external_api_cost_estimate` in the job's own API response exactly.
Cleaned up the throwaway job afterward.
