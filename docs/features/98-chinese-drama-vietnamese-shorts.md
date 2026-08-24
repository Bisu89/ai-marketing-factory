# 98. Chinese Drama → Vietnamese Shorts (new Video Composer mode)

**Commit:** `aeafa3e`

Real user request, specified in detail (flow + config + validation +
test list) and given as a "reuse existing architecture, don't rewrite"
instruction. Given a single uploaded Chinese-language video clip: transcribe
it (ASR), translate + write a title + a short hook via LLM, dub with
Vietnamese TTS (real word timing, not estimated), burn synced Vietnamese
captions, show the hook as a 0-3s overlay, output a vertical short.

## Investigation first

Planned in Plan Mode after 4 Explore passes across the codebase (per the
user's own explicit "read the architecture before implementing" instruction).
Key findings:

- No "processing mode" concept exists on Project/Template -- the Beat/
  Factory pipeline structurally assumes a text script driving AI-generated/
  library visuals per beat, not "one pre-existing video file is the
  content." The plain **Video Composer upload flow**
  (`app/modules/video_composer/`) fits instead: it already accepts an
  uploaded clip + a script, and its `narration_mode="tts"` path already
  runs edge-tts with real WordBoundary timing feeding its own caption
  burner -- exactly what the spec's dubbing/subtitle requirements need,
  unmodified.
- No ASR/transcription existed anywhere. The installed `openai==3.3.0` SDK
  already supports `client.audio.transcriptions.create(model="gpt-4o-transcribe", language="zh", ...)`.
- No LLM translation pattern existed -- built on the existing
  `call_structured()` JSON-schema convention and `beat_generate.py`'s
  bounded repair-retry loop (1 retry, error appended to the system prompt).
- **Face detection/tracking does not exist at all** (confirmed via
  dependency + code search). Per explicit user decision, v1 uses a fixed
  center cover-crop instead (the exact pattern already proven in
  `motion/renderer.py`'s static branch) rather than adding a new CV
  dependency.
- Single-clip Video Composer jobs previously **skipped scaling/cropping
  entirely** (existing behavior, unchanged for every other job) -- Chinese
  Drama mode needed a new cover-crop step (gated on the new
  `source_language` column) to actually turn 16:9 source footage vertical.

## Design

- `video_composer/service.py` gains a `DubGenerator` callable, injected at
  construction exactly the way `BeatRenderer` already is -- the real
  implementation (ASR + LLM) lives in the new composition root
  `app/api/v1/endpoints/chinese_drama_dub.py`, the one place allowed to
  import both `app.modules.ai` and `app.modules.video_composer` (module
  isolation).
- Two new `VideoComposeJob` statuses, `"transcribing"`/`"translating"`,
  entered before every other phase whenever `source_language` is set.
  `_run_dub_generation_phase` writes the real translated
  `title`/`script_text`/`hook_text` back onto the job once the callback
  succeeds -- the rest of `_run_job` (TTS, captions, mix, finalize) runs
  completely unmodified from that point on.
- **No re-billing on retry, with zero new caching infrastructure**:
  `retry_job()`'s eligibility was extended to also accept jobs with real
  on-disk clips (not just Factory jobs with a stored
  `composition_request_json`), copying the clip + the already-translated
  `title`/`script_text`/`hook_text` onto the new job.
  `_run_dub_generation_phase` only runs when `hook_text is None`, so a
  retried job (which already has real `hook_text` copied over) skips ASR/
  LLM entirely -- verified directly (see Verification).
- New `hook_text` overlay in `_finalize`: a `drawtext` filter with
  `enable='between(t,0,3)'`, using the fuller 4-character escaping from
  `outro/renderer.py::_escape_drawtext` (duplicated, not imported) since
  AI-written text is less predictable than the existing fixed title block.
- New `narration_rate` column (edge-tts's own signed-percentage string,
  e.g. `"+5%"`) -- a real gap found mid-implementation: the classic Video
  Composer's own `_run_narration` never had a speed/rate knob at all
  (unlike `app.modules.voice.providers.EdgeTTSProvider`'s separate
  float-multiplier `speed`, which this simpler pipeline never used).

## Real bugs caught during verification

- **Cover-crop didn't resample fps** -- a real end-to-end test (10fps
  mandelbrot source, SOCIAL_VERTICAL target profile expecting 30fps) failed
  `_validate_final_output` with `fps 10.0 does not match expected 30.0`.
  ffmpeg's `scale`/`crop` never touch frame rate; fixed by appending an
  explicit `fps={fps}` stage to the cover-crop filter chain (matching
  `_merge_clips_with_transitions`'s own existing convention).
- **3 existing test files' `_fake_run_narration` mocks broke** (`test_batch_render.py`,
  `test_composition_render.py`, `test_golden_sample_render.py`) once
  `_run_narration` gained its new `rate` parameter -- all three fixtures
  hardcoded a 3-argument signature. Fixed by adding `rate: str = "+0%"` to
  each (the real call site always passes it positionally now).
- **`gpt-4o-transcribe` rejects `response_format="verbose_json"`** -- found
  via a real (billed) smoke test through the actual running app (a real
  ffmpeg-generated landscape clip with real synthetic Chinese TTS speech
  as its audio track, uploaded through the new endpoint): OpenAI returned
  `400 unsupported_value` ("Use 'json' or 'text' instead"). Fixed by
  switching to `response_format="json"`; `segments` is consequently always
  empty for this model (kept on `TranscriptionResult` for shape fidelity
  to the spec, not because this model ever populates it -- there is no
  real per-segment timing available from gpt-4o-transcribe today).
- **`_run_narration`'s single edge-tts call had no retry** -- the same real
  smoke test then hit an intermittent `NoAudioReceived` failure from
  Microsoft's unofficial edge-tts service 3 times in a row inside the
  actual job worker (while isolated reproductions of the exact same call
  succeeded immediately) -- an already-diagnosed, already-mitigated issue
  elsewhere in this codebase (`app.modules.voice.providers.EdgeTTSProvider`'s
  own docstring: "real testing showed an intermittent NoAudioReceived
  failure roughly every few consecutive calls, unrelated to the text
  content"). `video_composer/service.py`'s own separate `_run_narration`
  never had this mitigation since it previously only ever made one edge-tts
  call per job with no other consumer stressing it this way. Fixed by
  duplicating the same bounded-retry shape (4 attempts, 1.5s×attempt
  backoff) -- benefits every `narration_mode="tts"` job, not just Chinese
  Drama mode, with no behavior change on the (now more reliable) happy path.

## Key files

- `app/modules/ai/transcribe_client.py` (new) -- OpenAI transcription API wrapper, mirrors `image_client.py`
- `app/api/v1/endpoints/chinese_drama_dub.py` (new) -- the composition root: ASR + translate/title/hook, retry loop, validation
- `app/modules/video_composer/models.py` -- new statuses, `source_language`/`hook_text`/`narration_rate` columns
- `app/modules/video_composer/service.py` -- `DubGenerator`, `_run_dub_generation_phase`, cover-crop step, hook overlay, `retry_job` extension
- `app/modules/video_composer/router.py` -- `POST /video-compose-jobs/from-chinese-drama`
- `app/main.py` -- `dub_generator=` wiring
- `frontend/src/pages/VideoComposerPage.tsx` -- Standard/Chinese Drama mode toggle

## Verification

New `tests/api/test_chinese_drama_dub.py` (15 tests, AI provider always
mocked): config constants, title/hook validation boundaries, repair-retry,
ASR called with the correct model/language. New
`tests/modules/video_composer/test_chinese_drama_pipeline.py` (3 tests,
real ffmpeg + real edge-tts, only ASR/LLM mocked): full pipeline produces
translated metadata and a real 1080x1920 vertical output from a 1280x720
source; a retry does not re-call the dub generator; a classic
(`source_language=None`) job's behavior is completely unchanged. Full
backend suite (1091 tests) green after fixing the 3 narration-mock
regressions above. `npx tsc -b --noEmit` clean.

**Real, end-to-end, billed verification** through the actual running app
(not just mocked tests): built a real landscape (1280x720) test video with
real synthetic Chinese speech (edge-tts `zh-CN-XiaoxiaoNeural`, thematically
matching a real user project from earlier in this session) as its audio
track, uploaded it through `POST /video-compose-jobs/from-chinese-drama`,
and let it run to `completed` for real -- caught the two real bugs above
along the way, fixed both, then confirmed a clean full run: real
`gpt-4o-transcribe` transcript → real LLM translation ("Anh chưa từng phản
bội cô, cũng chưa bao giờ đánh cô...") → title ("Chưa từng phản bội, vì
sao cô vẫn không yên lòng?") and hook ("Anh làm đủ mọi thứ, nhưng vẫn chưa
đủ?") both within their length constraints → real Vietnamese TTS + word
timing → a real 1080×1920@30fps output with the cover-cropped mandelbrot
source, the hook burned in with a black backdrop, and real burned karaoke
captions synced to the dubbed audio (visually confirmed via extracted
frames). Also confirmed a `retry` on an ASR/LLM-already-succeeded job
reused the stored title/script_text/hook_text rather than re-calling
OpenAI (visible directly in the job's own fields after retry). All
throwaway jobs/files/DB rows from this verification were deleted
afterward.

**Known limitation (not fixed, out of this task's scope):** the title/hook
`drawtext` overlays can overflow the frame's left/right edges for longer
text -- confirmed visually in the real run above. This is pre-existing
behavior for the title field (unchanged by this task) and the hook field
mirrors it; neither this module's `_finalize` has the auto-shrink-to-fit
logic `outro/renderer.py`'s own `_fit_text` already does for the separate
Outro Card feature. A natural, separate follow-up if it turns out to
matter in practice.
