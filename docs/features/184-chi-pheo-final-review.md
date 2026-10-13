# 184 — Chí Phèo ep01: final editorial review, 14:06 verified

Final review pass on `content-prompts/literature_vi/episodes/chi-pheo-ep01/` per channel-owner request: hook no
longer spoils "tao muốn làm người lương thiện" (moved to its real place at the climax); trimmed the faction
roll-call (kept Năm Thọ/binh Chức and Đội Tảo in full, cut the untracked "tư Đạm/bát Tùng" names); removed two
sloganistic/symmetric commentary lines; merged 3 repetitive closing paragraphs into 1 progressive argument (kept
the "cầm dao" counter-reading and the lò gạch callback); fixed one real error ("ngẩn ngơ", not in the text, replaced
with Nam Cao's actual word "dở hơi") and one omission (the "váy đụp" detail at Chí's birth).

Re-verified all 23 sources against the real `excerpt()` function, not just against `claims` labels as requested.
Found and fixed the same needle-spans-two-sentences bug documented in feature 183/MAPPING.md in 6 sources
(`open`, `bakien`, `factions`, `drunk`, `thino`, `awake`) — each was silently duplicating/bloating its excerpt.
Added missing needles for details that were real but previously unbacked by any source excerpt: the two rival
theories for why Chí was jailed, "một cái tát... đấm đá" at the gate, the aunt's stated age (năm mươi tuổi), and
Tự Lãng's backstory (wife dead 7-8 years, daughter pregnant out of wedlock and gone). No claim needed demoting to
disputed/interpretation — everything flagged as suspect turned out to be real once the right needle was found.

Verified by running `episode_builder.py create` twice against scratch backends (ports 8081, 8082; SQLite + library
dir under temp, torn down after both times): script review OK both times. Measured real audio independently with
`edge-tts` (`vi-VN-NamMinhNeural`) + `ffprobe`: the trimmed script first measured 13:46, under the channel's 14 min
floor, so added back one real detail (Chí's "vô cùng hể hả" after leaving Bá Kiến's, verbatim and already sourced)
plus one short commentary line sharpening the "Chí doesn't realize he's been bought" point the owner asked to keep
— both grounded in text, not padding. Final: 58 paragraphs / 2,921 words -> 845.8s = **14:06**.
