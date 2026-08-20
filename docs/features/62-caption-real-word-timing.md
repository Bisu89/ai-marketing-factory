# 62 — Captions Use Real Word Timing Instead of an Estimate

**Commit:** `TBD`

Found via a real user report: captions could visibly disappear *before*
their own words had even started being spoken, with the drift growing
worse through a beat (confirmed against real edge_tts word-boundary data
— a caption's window ended almost exactly when its real audio began,
roughly 1-2s late by the end of a several-clause beat).

## Root cause

The Voice stage (Task 22) already captures real, measured per-word
timestamps from edge_tts (used to settle each Beat's own overall
start/end), but discarded them once that was done. The Caption Engine
(Task 25) never had access to them, so it positioned captions *within* a
Beat using a generic weighted-text-length estimate (word count +
punctuation-pause weight) assuming a uniform speaking pace — real speech
never actually keeps that pace (natural pauses at commas/sentence-ends
run longer than the model assumes), so the estimate compounds into real,
user-visible drift for any beat with several short clauses.

## Fix

- `voice_generate.py` now persists `word_timestamps` (absolute seconds,
  same timeline as `Beat.start`/`end`) in `narration.meta.json` whenever a
  provider actually supplies them (edge_tts only — the default "local"
  SAPI5 engine has no word-boundary data, unaffected); a new public
  `load_word_timestamps()` lets another composition root read them back.
  A cache-hit run (no resynthesis) carries the existing value forward
  rather than clobbering it with an empty one.
- `caption/segmentation.py`'s `split_beat_into_segments` gained an
  optional `words` param: when supplied and its word count matches the
  chunk text exactly, each segment is positioned using its own real first/
  last word timing (gapless-stitched between chunks, capped at
  `max_duration_sec`) instead of the weighted estimate. Falls back to the
  original estimate whenever real timing isn't available or doesn't line
  up (same trust check `voice.timing._timing_from_word_timestamps` already
  applies at the whole-Beat level, applied here one level down).
- `caption_generate.py` loads and per-Beat-slices real timestamps (a
  half-open `[beat.start, beat.end)` filter), and folds them into the
  cache fingerprint so newly-available real timing invalidates a stale
  estimate-based artifact.

Verified against the real, reported project: a real edge_tts synthesis +
caption regeneration now produces segment boundaries matching the actual
word-boundary data, not the old estimate.
