# 96. Thumbnail Headline: Shrink the Oversized Black Band

**Commit:** `256a024`

Real user report: the auto-generated thumbnail's headline looked cheap --
big text sitting on a black band that covered too much of the frame
("nền đen cũng lớn khá lởm" -- the black background area is large,
looks tacky).

## Root cause

`_draw_headline` (`app/modules/thumbnail/renderer.py`) sized the font at
8.5% of frame height and padded the band around it generously. For the
common 2-line headline case, the compounded band height worked out to
~31% of the frame -- nearly a third of the thumbnail was solid black.

Frame *selection* itself was already fine (real brightness/contrast/edge
scoring across multiple candidates, not random -- `scoring.py`), so the
fix is scoped entirely to the text/band sizing in `_draw_headline`.

## Fix

Introduced three named ratios (`_HEADLINE_FONT_SIZE_RATIO=0.055`,
`_BAND_PADDING_RATIO=0.4`, `_BAND_BOTTOM_MARGIN_RATIO=0.015`, down from
implicit `0.085`/`0.5`/`0.02`) so the band now covers ~19% of frame
height for a 2-line headline and ~13% for a 1-line one. The band stays
full-width and fully opaque (unchanged) -- that was a deliberate earlier
fix for burned-in captions ghosting through a translucent/narrower band,
not part of this complaint.

## Verification

Rendered a real thumbnail (mandelbrot test video, matching the existing
test suite's own fixture style) with a real 2-line and 1-line headline,
measured the actual opaque band height in pixels (sampled near the frame
edge to avoid the white text pixels), and visually inspected the result:
2-line band 19.1% (was ~31%), 1-line band 12.5% (was ~21%). `pytest
tests/modules/thumbnail/` (35 tests) passes unchanged.
