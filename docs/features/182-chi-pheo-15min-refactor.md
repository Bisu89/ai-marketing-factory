# 182 — Chí Phèo ep01 refactored to ~15 min; literature_vi templates updated to the new 14–16 min standard

Rewrote `content-prompts/literature_vi/episodes/chi-pheo-ep01/script.md` + `spec.json` from the ~9 min/36-paragraph
draft into a ~15 min/60-paragraph version: 5 editorial parts mapped onto the system's 7 fixed `kind`s (Phần 3 splits
`timeline`+`evidence`, Phần 5 splits `consequences`+`conclusion`). Added real verbatim material fetched fresh from
`vi.wikisource.org` (not in the old draft): Bá Kiến's succession of enforcers Năm Thọ → binh Chức → Chí Phèo, the
village-faction/"quần ngư tranh thực" mechanism, Bá Kiến's calm handling at the gate, the riverbank meeting scene,
Chí's flashback to bà ba during the porridge scene, Đội Tảo's "tre già măng mọc" line, and the disputed
pregnancy-hint at the very end (kept `status: disputed`, not asserted). 6 `GÓC NHÌN NHÂN VẬT` beats placed at the
return, self-recognition, sobering-up, the porridge, hope, and the rejection.
Updated `SCRIPT_TEMPLATE.md` (6–9 min → 14–16 min standard for all future episodes, 5-group↔7-kind mapping table,
independent edge-tts+ffprobe measurement procedure), `MAPPING.md` (clarified `cards_by_phrase` lives in
`episode_builder.py`'s `cmd_storyboard`, not a separate `resolve_cards.py`; corrected the wikisource-`lang` item from
"proposal" to "already working"), `VISUAL.md` (image count scales with real storyboard scene count, not a fixed
number tied to the old runtime).
Verified by actually running `episode_builder.py create` against a scratch backend (SQLite + library dir under a
temp dir, port 8077, torn down after): 23 sources / 39 claims, every needle matched the real fetched Wikisource
text, `script review: OK`. Measured real audio independently with `edge_tts` (not through the app, no gates
touched), `vi-VN-NamMinhNeural`, per-paragraph with retries on the known random `NoAudioReceived` error, summed with
`ffprobe` on all 60 segments in one run, 0 failures: 2,929 words / 854.3s → **14 min 14 s**, measured rate ≈ 205.7
words/min (faster than the old 130–150 wpm assumption), inside the new 14–16 min target.
Bug caught: several needles failed on first try because the cached Wikisource HTML has stray zero-width spaces and
non-breaking spaces (`\xa0`) around guillemets/mid-word at paragraph-wrap points; fixed by picking needles that
don't straddle those positions, verified programmatically against the cached text before writing them into the spec.
`image_prompts.csv`/`.md` (24 images, old scene numbering) are now stale and flagged in `image_prompts.md`; real
image count needs a real `storyboard` run, which requires gate 1–2 approval (not done — that's the channel owner's
call, not something to approve automatically).
