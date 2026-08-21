# 94. Outro Card: 1.5s Hold Before the CTA Instead of a Hard Cut

**Commit:** (pending)

Real user report: narration ending and immediately hard-cutting to the
Outro Card's own black background felt jarring, no breathing room.

## Fix

`VideoComposerService._append_outro_clip` now holds the main video's own
last frame (silent, same scene -- freeze via ffmpeg's `tpad`/`apad`
filters, not a fade) for `_PRE_OUTRO_HOLD_SEC` (1.5s) before
concatenating with the Outro Card clip. Duration bookkeeping
(`_run_final_composition`'s own `audio_duration`, and `final_qa.py`'s
`expected_duration` -- see docs/features/89-outro-card.md's own
`FINAL_DURATION_MISMATCH` fix) updated to account for the extra 1.5s so
Final QA doesn't flag it as unexpected.

## Verification

Updated `OutroCardTests`' own duration assertion (`tests/api/
test_final_composer.py`) to expect `narration + 1.5s hold + outro`.
Full backend suite green.

Real end-to-end: rendered the user's own project, extracted real frames
at the exact narration-end (39.7s), mid-hold (40.5s, confirmed byte-for-
byte the same frozen scene), and just past the hold (41.5s, confirmed
the outro's typewriter text has begun) -- total real duration 47.28s
(39.818s narration + 1.5s hold + ~6.0s outro).
