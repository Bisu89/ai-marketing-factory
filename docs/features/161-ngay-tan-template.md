# 161 — Built-in "Ngày Tàn (Zombie Survival VI)" Template

New built-in template `ngay_tan` for the original zombie-survival series in `content-prompts/zombie_ngay_tan_the/` (bible, reusable image system, Ep1 scripts). Sibling of `zombie_system` but with no game System: grounded survival fiction, Vietnamese narration, all-adult cast.

Commit: "feat: ngay_tan built-in template + Ep1 audiobook script".

What it sets: 16:9 landscape, `vi`, ~10 min target, male narrator `vi-VN-NamMinhNeural` @ 1.10 (chosen by the series owner after auditioning in the voice test bench, see 160), no BGM, `library` visual mode against the reusable image pool, flat-cel manhwa style prompt reusing `zombie_system`'s drift-tested wording minus the school setting, plus an adult-cast clause.

Key files: `backend/app/modules/beat/schemas.py` (`NGAY_TAN_TEMPLATE`), `backend/tests/modules/beat/test_templates.py` / `test_router.py` (built-in id set and counts 15 → 16, plus one template test).

Built incrementally: only the fields settled so far; revisit as episodes get produced.
