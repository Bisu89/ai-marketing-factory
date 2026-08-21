# 92. Fix: Captions Drifting Ahead of Narration (Accumulating Toward the Middle/End)

**Commit:** `57c053a`

Real user report: captions ran ahead of the narration voice, worse in
the middle of longer videos -- correct at the start, increasingly out of
sync deeper into the video.

## Root cause

`app/modules/voice/timing.py`'s `compute_beat_timing` correctly computes
each Beat's real absolute `start`/`end` from real per-word timestamps
(`_timing_from_word_timestamps`) when a provider exposes them (edge_tts),
but then threw that position data away and kept only `.duration`.
`_stitch_contiguous` rebuilt `start`/`end` by cumulatively summing each
beat's own word-span duration from 0, with no term for the real ~0.35s+
silent gap Task 78 (Narration Sentence Pauses) puts between beats in the
real `narration.wav`. Each beat's assigned `start` ended up earlier than
its true first-word position by the sum of every prior gap --
`caption/segmentation.py`'s own `_real_word_boundaries` (Task 62, real
word timing) rescales the accurate real per-word timeline onto exactly
this window, so every caption after the first beat was placed too early,
worse deeper into the video.

## Fix, and a regression caught while verifying it

Made `_stitch_contiguous` use the real gap between consecutive beats'
own true positions (measured directly from the real timestamps, not
assumed to be a constant) so each beat's `start` lands on its own real
first word.

Verifying this against a real, running project surfaced a second real
bug: naively leaving each beat's `end` at its own real last word (gap
unassigned to any beat) broke video/audio duration matching --
`Beat.duration` drives Motion clip length, and a real render's video
ended up ~4.4s shorter than its own Audio Master
(`FINAL_DURATION_MISMATCH`). Fixed by having each non-last beat's `end`
extend through to the *next* beat's own real start -- its clip visually
holds through the pause, `sum(duration)` still equals the real narration
length exactly, and `start` (what captions rely on) is untouched.

A third attempted fix (making `caption/segmentation.py`'s rescale skip
stretching when a Beat's window is wider than its real content) was
tried and reverted -- it broke two already-established, deliberately
tested behaviors where a *wider* window legitimately should stretch
captions to fill it (min-duration rebalancing shrinking/widening a
beat's own official window a few ms away from its real audio). The
timing.py fix alone already eliminates the reported *accumulating*
drift; any residual stretch is now bounded to one beat's own trailing
gap (same category of already-tolerated imprecision as the rebalancing
case), never compounding across the video.

## Verification

New regression test (`tests/modules/voice/test_timing.py`'s
`test_real_inter_sentence_gaps_are_preserved_not_collapsed`) asserts
both invariants: each beat's `start` lands on its own real first word,
and `sum(duration) == total_duration` exactly. Full backend suite green.

Real end-to-end verification against the user's own actual project:
regenerated narration, confirmed real ~1-1.2s gaps at every beat
boundary via the raw word-timestamp metadata, triggered a real render --
completed with QA 100/100 (no more `FINAL_DURATION_MISMATCH`) -- and
every single beat-boundary caption in the real, rendered `captions.ass`
lands within 0.01s of the true beat-start position, all the way through
the last beat near the very end of the video (previously the exact
class of position that would have shown the worst accumulated drift).
