# 61 — Quality Gate False Positives for AI-Generated Images

**Commit:** `ad769e8`

Found via a real user report: every "Generate Full by AI" (Task 59)
project got permanently stuck at NEEDS_REVIEW, unable to ever pass
"Continue Production" no matter how many times it was clicked.

Root cause: the pre-existing Quality Gate's two visual checks both assume
a *keyword-matched local photo*, and score every AI-generated image as a
defect:

- `compute_asset_confidence` compares the beat's `visual_hint` against the
  asset's tags/filename -- an AI-generated image has neither (see
  `imagegen_generate.py`'s own `AssetRegisterIn` call), so it always
  scored LOW, and `require_review_for_low_confidence`'s own policy count
  flagged it every time.
- `classify_portrait_suitability` flagged every one as `LOW_RESOLUTION`:
  `gpt-image-1-mini`'s portrait size (1024x1536) genuinely doesn't cover a
  1080x1920 render profile's frame without upscaling -- true, but a fixed,
  accepted property of the chosen model, not a variable curation problem.

Since *any* warning forces `NEEDS_REVIEW` (see `quality.analyzer`'s own
status logic) and neither of these could ever be resolved by a user
action (regenerating doesn't change either), the review pause was
permanent and unescapable for AI-generated projects specifically.

Fixed in `quality_gate.py`: `compute_asset_confidence` short-circuits to
`HIGH` for `asset.source == "ai_image_generator"` (the image was
generated *from* that beat's own intent -- a deliberate match, not an
absence of signal to penalize); `_resolve_beat_asset_info` skips the
resolution classification entirely for the same source (reuses the
analyzer's own existing "no data = no penalty" rule rather than
inventing a new one). A real project's `review_reason_count` dropped from
19 to 1 (a real, unrelated `PACING_OUTLIER` note) after this fix.

## A related trap, not fixed here

Manually widening a beat's `duration` to dodge a `PACING_OUTLIER` warning
broke audio/video sync (`FINAL_DURATION_MISMATCH`) once that beat already
has narration assigned -- the beat's own duration is downstream of the
narration's real, fixed timing, not an independent dial. The existing
"Render Anyway" button in the classic manual Render step (bypasses the
Quality Gate check entirely, unlike "Continue Production") is the real,
already-existing escape hatch for a warning that isn't worth fixing.
