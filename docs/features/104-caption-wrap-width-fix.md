# 104. Fix: Captions Not Wrapping to a Second Line

**Commit:** `70e87c4`

Real user report: subtitles were too long and ran off the edge of the
screen instead of wrapping to a second line ("phần subtitle bị dài quá
không tự động xuống dòng mà đang bị lẹm chữ").

## Root cause

`app/modules/caption/ass_writer.py`'s `build_ass_content()` computes a
per-line character budget for its own word-boundary line-balancer
(`_wrap_balanced`):

```python
max_chars_per_line = max(10, max_chars // max(1, max_lines - 1) if max_lines > 1 else max_chars)
```

For the app's actual defaults (`max_chars=42`, `max_lines=2`), this divides
by `max_lines - 1 == 1`, giving `max_chars_per_line == 42` -- the same as
the *whole chunk's* character budget (chunks are already capped at
`max_chars` by `segmentation.py` before reaching here). `_wrap_balanced`'s
own "already fits on one line" check (`len(text) <= max_chars_per_line`)
was therefore true for essentially every chunk, so a real second line was
never produced. The ASS file sets `WrapStyle: 2`, which disables libass's
own automatic wrapping entirely (relying only on this function's explicit
`\N` breaks) -- so a too-long single line had nowhere else to go but past
`PlayResX`, i.e. off the edge of the video frame.

This is the ASS writer used by every project's actual render: the Factory
pipeline's `GENERATING_CAPTIONS` stage (`caption_generate.py`) calls this
function and passes the resulting `.ass` file straight to the composition
render as `captions_ass_path` -- it is not just an unused alternate path.

## Fix

Divide the total character budget across `max_lines` instead of
`max_lines - 1`: `max_chars // max_lines` (21 for the default 42/2),
floored at 10. A chunk longer than that now correctly triggers
`_wrap_balanced`'s existing word-boundary balanced split into a real
second line via `\N`.

## Verification

`tests/modules/caption/test_ass_writer.py`: added
`test_a_full_length_chunk_actually_wraps_to_a_second_line` (asserts a
default-budget chunk produces a `\N` break); updated 4 pre-existing tests
that happened to assert the old *unwrapped* single-line output for short
fixture text that now correctly wraps
(`test_big_statement_uppercases_text`, the 3 Unicode round-trip tests) to
be wrap-tolerant instead of asserting no wrapping occurred. Full
`tests/modules/caption/` (54 tests) and `tests/api/test_caption_stage.py`
(19 tests) pass.

Real, non-mocked verification: ran the actual chunking
(`segmentation.split_text_into_chunks`) + wrapping (`build_ass_content`)
pipeline together against a realistic long Vietnamese sentence and
confirmed each resulting Dialogue line now balances across two `\N`-joined
lines instead of running long on one.
