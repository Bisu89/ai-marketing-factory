# 140. Video Composer refactor (P2): split `service.py`

Pure refactor, no behaviour change. Cuts the 2382-line
`video_composer/service.py` (review finding: single biggest complexity
hotspot) down to **1788 lines** by extracting four focused modules.

**Landed in:** _branch `refactor/p2-split-video-composer`_ (commits
`a56cde5` subtitles, + this batch)

| New module | Lines | What moved |
|---|---|---|
| `subtitles.py` | 330 | word-timed captions: 5 preset layouts, `CAPTION_PRESET_CONFIG`, `group_words_into_lines`, `write_subtitles`, ASS/SRT formatters, row-wrapping, font paths |
| `narration.py` | 127 | `run_narration` (edge_tts + retry), `build_narration_timeline` (per-beat local track) |
| `audio_mix.py` | 94 | `mix_audio` — narration + ducked music (`sidechaincompress`) + SFX + fades |
| `ffmpeg_ops.py` | 54 | `run_ffmpeg`, `probe_duration`, `probe_video_info`, `escape_for_ffmpeg_filter` |

`service.py` now calls `subtitles.*` / `narration.*` / `audio_mix.mix_audio`
/ `ffmpeg_ops.*` and re-exports `FONT_PATH`/`FONT_PATH_BOLD`.

**Non-obvious:** these are `video_composer`'s own copies;
`app.modules.caption.ass_writer` / `app.modules.audio.renderer` are the
separate Factory-pipeline implementations and stay independent (the
codebase's "duplicate, don't import across modules" rule). No shared
cross-module lib was created.

**Test changes:** `patch.object(self.service, "_run_narration"/"_run_ffmpeg")`
→ module-level `patch("app.modules.video_composer.narration.run_narration"
/ "...audio_mix.run_ffmpeg")`; `VideoComposerService._build_narration_timeline`
/ `._probe_duration` / `._mix_audio` / `._escape_for_ffmpeg_filter` call
sites → the new module functions. 6 test files touched, mechanical.

**Verified:** full `tests/modules/video_composer` + `test_caption_stage` +
`test_composition_render` + `test_batch_render` + `test_final_composer` +
`test_chinese_drama_dub` + `test_audio_stage` + `test_golden_sample_render`
+ `tests/modules/caption`. (Pre-existing unrelated failures: a
`test_batch_render` retry-timing test that fails on `main` too; the
real-ffmpeg cancellation test flakes only under parallel load.)
