# 17. Karaoke captions: highlight box instead of color change

Video Composer's burned-in karaoke subtitles used to change the spoken
word's *text color* (`\k` fill from white to a random color). Trending
short-form video captions instead keep the text white throughout and show a
colored rounded box that slides behind whichever word is currently being
spoken.

## What changed

`backend/app/modules/video_composer/service.py`, `_write_subtitles`:

- Text is always plain white (`Style` `PrimaryColour`/`SecondaryColour` both
  white); no more `\k`/`\1c` color-fill tags.
- Each word gets its own timed `Dialogue` event (Layer 0, drawn behind)
  containing only a filled rounded-rect drawn with `\p` vector commands,
  positioned with `\pos` at that word's real pixel offset and sized to the
  word's rendered width. The line's text is a separate `Dialogue` (Layer 1,
  drawn on top) spanning the whole line.
- Word pixel widths are measured with Pillow (`ImageFont`) using the same
  bold Arial TTF the ASS style renders with (`Bold=1`) -- mismatched
  weight/regular metrics caused the box to drift off the word.
- Lines are further re-split by measured width (`_split_line_for_width`) so
  a "line" handed to the layout code always fits on one unwrapped row;
  `WrapStyle` changed from `0` to `2` (no auto-wrap) so libass can't
  silently re-flow text onto a row the box math didn't account for.

Added `pillow` to `backend/requirements.txt`.

## Why the extra width-splitting logic

The original line grouping (`_group_words_into_lines`) only considered word
count/gap/duration, not rendered pixel width, because the old color-fill
effect didn't care which row a word landed on. The new box needs an actual
x/y position per word, so a line that silently wraps to a second row breaks
the box math -- verified this by rendering real frames with ffmpeg/libass:
the first attempt (bold-metrics + wrap bugs) put the box over the wrong
word entirely.

## Verification

Generated a synthetic `.ass` file and burned it onto a blank frame with
ffmpeg (`ass=...` filter) at each word's timestamp; visually confirmed the
box tightly tracks the active word only, text stays white, and rows split
correctly at the video's safe width.
