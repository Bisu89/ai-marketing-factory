# 126 — Package hashtags fix + long-form Quality-Gate false positive

**Commit:** `65b9fee`

Two bugs surfaced by rendering the first real 15-minute video
(`military_history` template, 30 beats, AI visuals):

## 1. `metadata.json` hashtags were unusable run-on tags

`derive_hashtags()` fed `ContentBrief.topic/angle/emotion/tone` — which
since Task 21 are **full sentences** — straight into `normalize_hashtag()`,
which CamelCases its entire input. Result on every Factory-produced video:

```
#TheBattleOfAgincourtOn25October1415WhereHenryVSExhaustedEnglishArmyUsedLongbows...
```

Fixes (`app/modules/metadata/service.py`, `app/api/v1/endpoints/package_generate.py`):
- `normalize_hashtag()` now returns `None` for anything over
  `_HASHTAG_MAX_WORDS` (5) or `_HASHTAG_MAX_CHARS` (40) — a hashtag is a
  tag, not a caption. The deterministic path degrades to a couple of
  short valid tags (from `emotion`/`tone`) instead of garbage.
- `_AI_METADATA_SCHEMA` gained a required `hashtags` array; the prompt
  asks for "4–6 SHORT hashtags, 1–2 words each". `AIMetadata` carries them
  (defaulted to `[]` so old caches still construct).
- `_generate_metadata()` now prefers the AI's own short hashtags when AI
  metadata is on (manual hashtags still win); only falls back to
  `derive_hashtags()` when neither is available.
- `AI_METADATA_ENGINE_VERSION` bumped `v2 → v3` (it's baked into the AI
  cache fingerprint): a pre-126 cache has no `hashtags`, so it misses and
  regenerates once with the hashtag-aware engine. `regenerate-metadata`
  still reuses a same-version cache — feature 97's "unchanged script never
  re-bills the AI call" contract is untouched. (A first attempt that wiped
  the cache in `regenerate-metadata` broke that contract and was reverted,
  commit `f38298d`.)

Verified on the real Agincourt video: `['#Agincourt', '#MedievalHistory',
'#MilitaryHistory', '#HenryV', '#Longbow']`.

## 2. `LOW_PURPOSE_DIVERSITY` false-positive on long-form

A well-structured 30-beat documentary with all 6 `BeatType`s present is
`6/30 = 0.20` unique-ratio → flagged (`NEEDS_REVIEW`, score −15). The
ratio alone punishes length. Added `LOW_PURPOSE_DIVERSITY_MIN_UNIQUE = 4`:
the warning now also requires the **absolute** distinct-purpose count to
be below 4. A video with 4+ narrative purposes has real structural
variety regardless of beat count; one that's all `BODY` still flags. Same
long-form-calibration approach as feature 109's `_consecutive_purpose_
threshold` / `_pacing_outlier_ratio`.

## Key files

- `backend/app/modules/metadata/service.py` — `normalize_hashtag` length guard
- `backend/app/api/v1/endpoints/package_generate.py` — AI hashtags in schema/prompt/`AIMetadata`, `_generate_metadata` preference order, `AI_METADATA_ENGINE_VERSION` v2→v3
- `backend/app/modules/quality/analyzer.py` — `LOW_PURPOSE_DIVERSITY_MIN_UNIQUE`

## Verification

`pytest tests/modules/metadata tests/api/test_package_stage.py` (55) and
`tests/modules/quality tests/api/test_quality_gate.py` (64) green. Real
regen of the finished 15-min Agincourt video produced clean title,
description and hashtags.
