# 82. Merge Short Adjacent Beats (Reduce AI Image Cost)

**Commit:** `fdfd7de`

Real user report: AI-generated Beats came out uneven -- e.g. Beat 4 =
3.1s, Beat 5 = 2.0s -- adjacent short beats instead of one longer one.
Since "Generate Full by AI" (Task 59) generates exactly one AI image per
Beat ($0.006 each) regardless of that beat's duration, this was pure
wasted cost with no visual benefit -- 8 short beats cost `8 × $0.006`
versus the same narration as 5 longer beats costing `5 × $0.006`.

Root cause confirmed by reading `beat_generate.py`'s own system prompt:
the AI was given a beat-*count* range ("roughly 4-8 beats") but **zero**
durational guidance at all -- no target length, no minimum, no
instruction to avoid short trailing beats. Beat count and duration were
entirely the model's own unguided judgment call, and no merge/rebalance
logic existed anywhere in the codebase to catch it afterward (the only
existing minimum-duration logic, `voice/timing.py`'s 0.8s floor, runs
much later on the real narration timeline, never changes beat *count*,
and has no awareness of image-generation cost).

## Fix (`app/api/v1/endpoints/beat_generate.py`)

Two layers, since prompt compliance alone isn't guaranteed:

1. **Prompt guidance** -- `SYSTEM_PROMPT` now states the actual reason
   ("each beat gets its own separately generated image") and a concrete
   target ("aim for roughly 4-7 seconds of narration per beat... combine
   short adjacent narration into a single beat instead of producing
   several beats under ~3 seconds each").
2. **Deterministic merge pass** -- `_merge_short_beats()` runs on the
   AI's raw response before `_beats_from_raw` builds `Beat` objects
   (so `id`/`order` stay purely mechanical, unaffected by merging).
   Merges a beat under 3.0s **backward** into its immediately preceding
   beat (never forward -- a short opening Hook is deliberately left
   alone, there's nothing before it to fold into), only when the
   combined duration stays under 9.0s and the plan doesn't collapse
   below 3 beats total (bails out to the original, unmerged list rather
   than risk an unnaturally sparse video). This guarantees the cost
   reduction even on a run where the model doesn't fully follow the
   prompt's own guidance.

## Verification

New `MergeShortBeatsTests` (6 tests) in `tests/api/test_beat_generate.py`:
the user's exact scenario (3.1s + 2.0s -> one 5.1s beat), no-op when
already balanced, a short opening beat never merges forward, merging
never collapses below 3 total beats, and a combined duration that would
exceed 9.0s stays unmerged -- plus an end-to-end test confirming
`generate_beat_plan()` itself produces the merged result with correctly
reassigned `id`s. Full suite (18 tests) green.

Real (non-mocked) `POST /beats/generate` call with a Vietnamese script
containing several short sentences: before this fix, produced 6 beats
including a 1.5s beat and a raw mid-sentence split (1.5s/3.0s/2.0s
trailing beats); after, 4 beats at 4.5s/4.5s/4.5s/5.5s -- no short
outliers, no mid-sentence splits, real story-editor-level image cost
`4 × $0.006` instead of `6 × $0.006` for the same narration.
