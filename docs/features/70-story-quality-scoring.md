# 70. AI Story Quality Scoring

**Commit:** `pending`

Pre-render quality gate for a `StoryVersion`: scores it on 9 dimensions
(Hook, Curiosity, Emotion, Conflict, Twist, Ending, Shareability,
Originality, Commercial Fit; 0-10 each) before the expensive video
pipeline runs. No auto-regeneration -- scoring only, per this task's own
scope.

## Where it lives

`app/modules/ai/story/quality.py` (`StoryQualityService`) -- inside the
existing `ai/story` module, not a new module or composition root, since
it only ever touches this module's own `StoryVersion`/`StoryJob`. Uses
the existing `app.modules.ai.llm_client.call_structured` and
`app.modules.ai.history.record` exactly as story/hook generation already
do -- no new AI client, no global orchestrator.

## No new table

Considered and rejected in favor of 4 new nullable columns directly on
`StoryVersion` (`quality_score`, `quality_recommendation`,
`quality_breakdown` JSON, `quality_scored_at`) -- full reasoning in that
model's own docstring. Short version: nothing in this task needs more
than the *latest* score per version (re-scoring fully replaces the old
verdict, same "regeneration atomically replaces" convention already used
elsewhere in this codebase), and `ai_generation_history` is an
append-only audit log, not something meant to be queried for current
state. `quality_score`/`quality_recommendation` are real, filterable
columns; the 9 individual scores + reasoning + suggestions are bundled
into one JSON column, matching `Asset.extra_metadata`'s own
"structured-but-not-over-normalized" shape.

`total` is the sum of the 9 dimension scores (0-90 range), not an AI-
decided number -- computed in Python so the pass/fail line is consistent
across every call and provider. `pass`/`fail` is a deliberate, documented
threshold (`QUALITY_PASS_THRESHOLD = 60`, avg ~6.7/10) in
`story/models.py`, not something the model decides per-call.

## Cost optimization

- Prompt sends only the version's own `title`/`script_text` -- never the
  Video's title/topic/emotion/tags/notes that `StoryService.generate()`
  itself sends (none of that changes how good *this specific script*
  reads).
- `max_tokens=512` vs generation's own 2048-4096 (output is 9 small
  integers + a short reasoning + a few short suggestions).
- No cheaper model was substituted: `llm_client.py` hardcodes exactly one
  model per provider with no second tier wired into `call_structured()`
  to select from, and `OPENAI_MODEL` was only just changed by explicit
  user request one day before this task -- silently reintroducing a
  cheaper model here would second-guess a decision outside this task's
  scope. Documented as the one call site to switch first if a real cheap
  tier is ever added to `llm_client.py`.

## API

`POST /story-jobs/{job_id}/versions/{version_id}/score` → `StoryVersionOut`
(reuses the existing schema -- no parallel response type). Returns the
score breakdown, total, recommendation, and reasoning inline with the
version's own title/script_text.

## Verification

Real AI calls (this env's `.env` has real keys) for the two judgment-
quality tests; controlled fault injection (monkey-patching
`call_structured` at the module boundary, not a new provider) for the
failure-mode tests, since real infrastructure can't be reliably forced to
fail on demand:

1. **High quality story** (a genuinely well-constructed reunion story) →
   59/90 -- correctly identified real strengths (hook, emotion) and real
   weaknesses (predictable, thin conflict/twist); realistic, not
   rubber-stamped near-perfect.
2. **Weak story** (`"This is a video about something..."`) → 3/90,
   correctly flagged as having no premise/stakes/payoff.
3. **Malformed AI response** (garbage non-JSON text) → rejected,
   `ExternalServiceError`, previous score untouched.
4. **Provider failure** (simulated `AIProviderError`) → rejected, same.
5. **Timeout** (simulated `AIProviderTimeoutError`, a subclass already
   caught by the same handler) → rejected, same.
6. **Out-of-range score** (model returns `hook: 15`) → rejected as
   malformed, same.
7. **Safety refusal** → rejected, same.
8. **Retry**: after several simulated failures, a subsequent successful
   call fully replaces the score (54/90) -- proving retry-by-calling-again
   works and a failure never permanently blocks re-scoring.
9. `ai_generation_history`: 8 real rows across the run, 5 with
   `error_message` set -- every attempt (success or failure) is audited.
10. Nonexistent `version_id` → `NotFoundError` (404).

`python -c "import app.main"` clean throughout.
