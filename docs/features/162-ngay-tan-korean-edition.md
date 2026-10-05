# 162 — Ngày Tàn: Korean edition + intro/outro voices

Why: the series owner tried the earlier zombie series in Korean and Vietnamese; Korean got views immediately, Vietnamese got none, so production now focuses on Korean. Each episode also gets a short intro and outro read by a second voice of the opposite gender (KO: female narrator + male bookends; VI: male narrator + female bookends).

Commit: "feat: ngay_tan_ko template + intro/outro voices in the voice test bench".

What changed:
- New built-in template `ngay_tan_ko` (Korean, `ko-KR-SunHiNeural` @1.0, same library-mode visuals/prompt as `ngay_tan`). Built-ins 16 → 17.
- Voice test bench (`voice_test.py` + page): a pasted script may contain `## GIỚI THIỆU` / `## TRUYỆN` / `## KẾT` header lines; intro/outro sections are read with a second voice ("auto" = opposite gender in the same language, or "same", or a chosen voice) and joined via the existing `synthesize_voice_runs`. Other `##` lines stay notes. Without headers behavior is unchanged.
- Scripts under `content-prompts/zombie_ngay_tan_the/scripts/`: Ep1 v3 / Ep2 v1 now carry VI intro/outro sections; Korean intro/outro lines for Ep1–2 in `ko_bookends_check.txt` (written via the numbered check-file method and re-read to rule out Hangul corruption).

Design note: the real Voice Factory stage already supports a per-beat voice (`Beat.voice_id`), so in a produced video the intro/outro beats just set `voice_id` to the bookend voice; no new template field was added.

Key files: `backend/app/modules/beat/schemas.py`, `backend/app/api/v1/endpoints/voice_test.py`, `frontend/src/pages/VoiceTestPage.tsx`, `backend/tests/api/test_voice_test.py`.

Verified: unit tests for section split / voice choice (7), template tests (55 total pass), a real 3-section synthesis (VI male body + auto female bookends) produced one valid MP3; `npx tsc -b --noEmit` clean.

Korean Ep1 (`scripts/ep1_ko.md`, 80 paragraphs, ~1,190 words, built from the numbered check file `ko_ep1_check.txt` by script; corruption scan found only the Vietnamese section-header letters) is the first KO script; a short real run (male intro/outro + female body) synthesized fine in the test bench.
