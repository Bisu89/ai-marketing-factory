# 95. Outro Text: Auto-Shrink to Fit Instead of a Hard 80-Char Cap

**Commit:** (pending)

Real user report: the outro CTA text field felt needlessly limited (80
chars), and asked why longer text couldn't just wrap onto more lines
automatically -- with an implied "sometimes it overflows the screen" for
longer text.

## Root cause

`render_outro_clip`'s word-wrap (`_wrap_lines`, real Pillow glyph
measurement) only ever checked *horizontal* fit against the frame width.
Longer text wraps onto more lines, but nothing checked whether the whole
wrapped block's *height* still fit inside the frame -- a long enough CTA
could genuinely run past the top/bottom edge. The 80-char cap was really
papering over that gap, not a deliberate design choice.

## Fix

New `_fit_text()`: shrinks the font size (in `_FONT_SIZE_STEP` steps,
never below `_MIN_FONT_SIZE=22`) and re-wraps at each size until the
wrapped block's total height fits within `_MAX_TEXT_HEIGHT_RATIO` (60%)
of the frame height -- the same technique many "fit text to box" tools
use. Raised `MAX_OUTRO_TEXT_LENGTH` from 80 to 200 now that overflow is
no longer a real risk (still bounded -- one ffmpeg `drawtext` filter per
revealed character, and a multi-paragraph CTA stops being a quick CTA
regardless). Also grew both outro textareas (`VideoFactoryPage.tsx`,
`NewVideoModal.tsx`) from 2 to 3 rows to match.

## Verification

Rendered a real 5-line, near-the-new-limit Vietnamese CTA and extracted
the fully-revealed final frame: auto-shrunk to a smaller readable font,
comfortably centered with real margin top/bottom, no overflow.
`tests/api/test_final_composer.py::OutroCardTests` and the beat schema
suite still pass. Full backend suite green. `npx tsc -b --noEmit` clean.
