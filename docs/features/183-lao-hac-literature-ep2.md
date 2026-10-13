# 183 — Lão Hạc (literature_vi episode 2), 14–16 min standard

Second work on the literature channel (each episode = one standalone work, not a serialized story):
`content-prompts/literature_vi/episodes/lao-hac-ep02/` (spec.json, script.md, characters.md, README.md).
29 sources / 36 claims fetched and verified from `vi.wikisource.org` ("Lão Hạc", Nam Cao, 1943); 62-paragraph
script across all 7 required `kind`s, 6 `GÓC NHÌN NHÂN VẬT` beats, `cause_interpretation` claim marked `disputed`
(the text never states outright that Lão Hạc poisoned himself — it only juxtaposes the dog-poison request with
"only I and Binh Tư understand").

Verified by running `episode_builder.py create` against a scratch backend (port 8079, SQLite + library dir under
temp, torn down after): script review OK both times. Measured real audio independently with `edge-tts`
(`vi-VN-NamMinhNeural`, per-paragraph, retried on the known random `NoAudioReceived`, summed with `ffprobe`,
0 segments unresolved): first draft (49 paragraphs / 2,226 words) measured only ~10 min — short of the channel's
14–16 min standard — so the script was expanded with real unused material from the same text (the garden's origin,
the father's saving plan, village-economy detail, a fuller physical description of Lão Hạc crying, the sweet-potato
comfort scene) plus deeper sourced analysis, not padding. Final: 62 paragraphs / 3,149 words → **843.3s = 14 min
05s**, ≈224 words/min.

Bug caught and fixed: `episode_builder.py`'s `excerpt()` splits sentences on literal `". "`; a needle that itself
spans two sentences has no single split-piece containing it, so the function silently falls back to the *entire*
enclosing paragraph, causing duplicated/bloated excerpts when another needle targets the same paragraph. Fixed by
keeping every needle to one sentence; documented in `content-prompts/literature_vi/MAPPING.md` as a reusable
lesson for future episodes.
