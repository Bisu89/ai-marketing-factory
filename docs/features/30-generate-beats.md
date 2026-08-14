# 30 — Generate Beats from Script

**Commit:** _(fill in after commit)_

## What it does

Wires the Video Factory's "Generate beats" button to a real AI call:
`Script -> Claude -> BeatPlan`. A narration script is sent to a new
backend endpoint, which reuses the existing `app.modules.ai.claude_client`
Anthropic infrastructure (the same shared client story/hook/caption already
use) to produce structured JSON, validates it against the `Beat`/`BeatPlan`
domain contract ([29](29-beat-domain-contract-v2.md)), and returns it. The
frontend replaces its current beats with the result and selects the first
one.

## Key files

`backend/app/api/v1/endpoints/beat_generate.py` (new), `backend/app/api/v1/router.py`
(+1 route), `backend/tests/api/test_beat_generate.py` (new, 12 tests, AI
client fully mocked), `frontend/src/api/beat.ts` (new),
`frontend/src/types/videoFactory.ts` (`BeatType` now matches the backend's
7-value enum exactly; added `GeneratedBeat`/`GeneratedBeatPlan` and
`WorkingBeat.visualHint`), `frontend/src/pages/VideoFactoryPage.tsx` (+`.css`)
(`handleGenerateBeats` now calls the API instead of a local sentence-split
heuristic, which is deleted).

## Architecture

`app.modules.beat` still has zero routes and still never imports
`app.modules.ai` (or vice versa) -- per `app/modules/README.md`'s isolation
rule, something has to call Claude *and* validate against `BeatPlan`, and
per this codebase's established "composition root" precedent
(`composition_render.py`), that adapter lives at `app/api/v1/endpoints/`,
which is HTTP-layer infrastructure, not a module. No new Claude client, no
new AI config, no `VideoFactoryService`.

Unlike story/hook/caption, this endpoint persists nothing (no Job/Version
table, no `video_id`) -- a Beat plan here isn't tied to a Library video, and
per this task's own scope the frontend just keeps it in local state.

**Design choice:** the model is only asked for `type`, `narration`,
`duration`, `visual_hint` per beat -- `id` and `order` are assigned
deterministically by the endpoint itself (`beat_01`, `beat_02`, ...) rather
than trusted from the LLM. Those two fields are mechanical, not creative,
so this removes an entire class of validation failure (duplicate/gapped
ids or order) before it can happen, leaving the bounded repair-retry
(1 retry, see `generate_beat_plan`) to handle genuine content problems
(bad `type`, out-of-range `duration`, blank `narration`/`visual_hint`).

## Tests

Backend: `backend/tests/api/test_beat_generate.py`, 12 tests -- valid
response, empty/whitespace script rejected, refusal fails without retry,
malformed JSON triggers one repair retry and succeeds, invalid
duration/type are rejected by `Beat`'s own validators (not duplicated
logic), exhausted retries raise a clean `ExternalServiceError`. The
Anthropic client is mocked throughout; no test calls the real API.
`python -m unittest discover -s tests` -- **240 tests, all passing**
(228 prior + 12 new).

Frontend: no test framework exists in this repo (`frontend/package.json`
has no test runner) -- per this task's own "do not introduce a new testing
framework" instruction, verified manually instead (see below).

## Manual verification

Real Playwright run against the running dev servers, `/video-factory`:
"Generate beats" is disabled with an empty script, enables once text is
typed, shows a loading state while the request is in flight, and -- since
this dev environment has no Anthropic API key configured in `backend/.env`
-- correctly surfaces the real backend error ("Anthropic API key not
configured...") in an inline alert without crashing or silently advancing
to Step 2. "Add beat manually" is unaffected. The happy path (a real
Claude call producing beats) is covered by the mocked backend tests above,
not by an unauthenticated manual call.

## Next task

Task 3 -- Beat Editor CRUD / persistence.
