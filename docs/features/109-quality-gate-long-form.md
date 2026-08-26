# 109. Quality Gate False Positives on Long-Form Video

**Commit:** _pending_

Real user report: producing the first real long-form episode (Series +
Story-to-Scene Analysis + landscape profile, see
[108](108-landscape-render-profile.md)) paused with 3 "issues" at a 91/100
score: a 3-consecutive-BUILD-beats warning, and two beats flagged as
"significantly different from the project average."

## Root cause

Both underlying Quality Gate heuristics in `app.modules.quality.analyzer`
were calibrated against literal short-form examples cited in their own
code comments -- `PACING_OUTLIER_RATIO`'s comment cites a 5-beat, ~4s-average
example; `CONSECUTIVE_PURPOSE_WARNING_THRESHOLD`'s a 4-beat one -- and
applied as fixed values regardless of how long the actual video is. Neither
was ever validated against a real multi-minute, 15+ beat project, because
that wasn't achievable before [108](108-landscape-render-profile.md) fixed
`target_duration`'s 120s cap.

For the real reported project (15 beats, ~7.5 min): a punchy 5.2s HOOK
beat against a 21.4s project average, and an 8.0s ENDING beat, both
deliberate pacing (a short open/close is *good* editing, not a defect) --
flagged anyway by a fixed 2.3x-of-mean ratio. Separately, 3 consecutive
BUILD beats (explaining 3 different MMO methods in a row, the actual
narrative content of that episode) flagged as "duplication" by a fixed
"3 in a row" threshold -- normal structure when a video covers several
sub-topics in sequence.

`evaluate_readiness`'s own "any warning always pauses for review, never
silently swallowed" policy (a deliberate, documented design -- see its own
docstring) is not the bug; the warnings themselves were false positives.

## Fix

Both thresholds now scale with beat count instead of applying the
short-form calibration uniformly:

- `PACING_OUTLIER_RATIO` (2.3x) is unchanged for any project at or under
  `PACING_OUTLIER_BASE_BEAT_COUNT` (8) beats -- every existing short-form
  test/behavior is untouched -- and loosens gradually (+0.1 per beat past
  8, capped at 4.5) for longer projects. A HOOK or ENDING beat is also
  now exempt from the "too short" side of the check specifically (never
  the "too long" side) -- a punchy open/close being brief is deliberate
  pacing by this app's own `BeatType` semantics, at any video length.
- `CONSECUTIVE_PURPOSE_WARNING_THRESHOLD` (3) similarly scales via
  `max(3, ceil(beat_count * 0.22))` -- unchanged for short plans, becomes
  4 starting at 14 beats. 0.22 was picked against the actual real 15-beat
  project this was reported against, not derived abstractly.

## Verification

`tests/modules/quality/test_analyzer.py`: new tests reproducing the exact
reported shape -- a short HOOK beat never flagged regardless of ratio, a
brief non-HOOK/ENDING aside within the new scaled ratio not flagged, a
genuine extreme outlier still flagged even in a long video, an unusually
*long* HOOK still flagged (the exemption only covers being short), 3
consecutive BUILD beats at 15 beats not flagged, 4 consecutive still
flagged. All pre-existing short-form calibration tests (the exact 4-beat/
5-beat literal examples the original constants cite) pass unchanged --
confirms the fix is purely additive for longer content. Full sweep --
`tests/modules/quality/`, `tests/api/test_quality_gate.py`,
`tests/api/test_dashboard.py`, `tests/api/test_factory_pipeline.py` -- 100
passed.

Real, non-mocked verification: re-ran the actual `POST /projects/{id}/quality-check`
endpoint against the real project from the user's own bug report, before
and after the fix. Before: `NEEDS_REVIEW`, score 91, all 3 original
warnings present. After (same project, same beats, no data changed): all
3 warnings gone, `status: "READY"`, score 97.
