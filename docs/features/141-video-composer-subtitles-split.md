# 141. Video Composer refactor (P2, slice 1): extract `subtitles.py`

Pure refactor, no behaviour change. First cut of splitting the 2382-line
`video_composer/service.py` (review finding: single biggest complexity
hotspot).

**Landed in:** _branch `refactor/p2-split-video-composer`_

**What moved:** all word-timed caption rendering — `CAPTION_PRESET_CONFIG`,
the 5 preset layouts (`_ass_events_*`), `group_words_into_lines`,
`write_subtitles`, the ASS/SRT time formatters, `_rounded_rect_drawing`,
`_split_line_for_width`, `HIGHLIGHT_COLORS`, `FONT_PATH`/`FONT_PATH_BOLD` —
from `VideoComposerService` into a new `app/modules/video_composer/subtitles.py`
(~360 lines out of `service.py`).

`service.py` now calls `subtitles.group_words_into_lines()` /
`subtitles.write_subtitles()` and re-exports `FONT_PATH`/`FONT_PATH_BOLD`
(still used by `_finalize` and `composition_render.py`).

**Non-obvious:** this is `video_composer`'s own copy;
`app.modules.caption.ass_writer` is the separate Factory-pipeline
implementation and the two deliberately stay independent (the codebase's
"duplicate, don't import across modules" rule). The extraction is
in-module, not a shared cross-module lib.

**Verified:** `tests/modules/video_composer`, `test_caption_stage`,
`test_composition_render`, `test_batch_render`, `test_final_composer`,
`tests/modules/caption` + a standalone 6-preset render check.
