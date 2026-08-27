# 117. No Lone 1-Word Caption Cards

**Commit:** `6913f34`

Real user report on the Horror Shorts clips: *"đoạn subtitle vẫn chưa
smart lắm, nhiều đoạn có đúng 1 chữ"* — captions kept fragmenting into
1-word cards.

## Cause

Two compounding things:

1. `horror_shorts` shipped with `max_words=4, max_chars=24` caption caps.
   24 chars is tight enough that ordinary narration ("I found an old
   photograph") already blows past it, so the greedy walk in
   `caption/segmentation.py` split every few words.
2. That greedy walk closes a chunk the moment it hits a limit — so a
   sentence whose last word didn't fit alongside its phrase became its own
   card ("me.", "the", "face.").

## Fix

- **`_merge_orphan_chunks`** (new, runs at the end of
  `split_text_into_chunks`): a lone 1-word chunk is folded into a
  neighbour (previous first, else next) when the merged card still fits
  `max_chars` and is within 1 word of `max_words`. It only ever touches
  1-word chunks, so a deliberate multi-word short line ("Nobody was
  there.") is left alone.
- **`horror_shorts` caption caps** `4/24 → 6/38`.

## Key files

- `app/modules/caption/segmentation.py` — `_merge_orphan_chunks`
- `app/modules/beat/schemas.py` — `HORROR_SHORTS_TEMPLATE` caption caps
- `tests/modules/caption/test_segmentation.py` — 3 new tests

## Verification

`tests/modules/caption`, `test_caption_stage.py`, `tests/modules/beat`
green (109). Before → after on the real "The Photograph" script:
`"I found\Nan old" / "photograph\Nof my family" / … / "me." / … / "the" / …`
became `"I found an old photograph of" / "my family in a shoebox." /
"Everyone in it was smiling." / "Everyone except me." / …` — no orphans,
sentence boundaries respected.
