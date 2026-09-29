# 155 — Story Remix pipeline + "isekai_system_vi" built-in template

**Commit:** `d182f91`

New niche: 1-3 trending "xuyên không"/"hệ thống" (transmigration/hidden-
System) storytelling videos on YouTube are transcribed, then an LLM
rewrites them into one genuinely new chapter -- new characters, new
setting, new ending -- before anything renders. Built at the user's
request to be YPP-monetization-safe from the start, since YouTube's
reused/duplicative-content policy (2025-07) targets exactly this
transcribe-and-reword shape.

## What it sets

- `POST /story-remix/transcribe` -- wraps the existing
  `ai/transcribe_client.py` (OpenAI `gpt-4o-transcribe`, already used by
  Chinese Drama dubbing) for one local source video.
- `POST /story-remix/rewrite` -- structured LLM call with a bounded
  repair-retry loop (same shape as `chinese_drama_dub.py`). Two hard
  gates, both enforced in code rather than left to the prompt (same
  precedent as `manhua_recap.py`'s mandatory host-commentary check):
  - `_check_transformation` -- the model must self-report renaming every
    character, using a new setting, changing the ending, and (with 2+
    sources) blending them; any missing axis is rejected and fed back for
    a repair attempt.
  - `_check_same_language_overlap` -- a 5-gram word-overlap ratio against
    each source transcript, enforced only when that source's language
    matches the output's language (a straight translation to a different
    language already drives raw overlap near zero regardless of real
    transformation, so checking it there would be meaningless).
- Built-in `Template` `isekai_system_vi` (`backend/app/modules/beat/schemas.py`)
  -- sibling to `zombie_system` (same webtoon art direction, System-UI
  narration beats), but the setting is whatever that episode's own script
  establishes, not fixed to zombie-apocalypse. `language="vi"` by
  default; Korean episodes override `content.language`/`voice` per
  project, same real-production pattern zombie_system already uses.
  `visual_generation.image_style_prompt` reuses zombie_system's
  already-hardened safety wording (black ichor not red blood, no
  painterly/photorealistic drift, no sexualized minors) verbatim.
- `tools/story_remix/remix.py` -- `fetch` (download via the existing
  Download API + transcribe) → `script` (AI rewrite, writes
  `_remix/script.json` for hand review) → `build` (creates the Project
  with `visual_generation_mode="ai_generated"`, PUTs the beat plan,
  starts the render), mirroring `tools/manhua_recap/recap.py`'s own
  fetch/script/build shape.

## Non-obvious design decisions

- **`POST /projects` defaults `visual_generation_mode` to `"library"`
  regardless of the chosen template's own config** (`CreateProjectRequest`
  in `beat/router.py`) -- this niche has no reused asset pool, so
  `remix.py build` must explicitly pass `"ai_generated"` or every beat
  would silently get no image.
- The overlap check is scoped to same-language source/target pairs only,
  not applied globally -- an early draft of this design checked overlap
  unconditionally, which would have made cross-language sourcing (e.g. a
  Korean source rewritten into Vietnamese) trivially pass the check no
  matter how little the plot itself changed. Restricting it to the
  same-language case keeps it meaningful for the common real case (a
  Vietnamese-narrated source rewritten into Vietnamese) without giving a
  false sense of protection elsewhere.
- Transformation is checked via the model's own structured self-report
  (booleans it must set true) plus a lexical fallback, not a single fuzzy
  similarity score -- mirrors `manhua_recap.py`'s established pattern of
  turning a structural claim into a deterministic, checkable field rather
  than trusting prose instructions alone.

## Key files

- `backend/app/api/v1/endpoints/story_remix.py` -- new composition root
- `backend/app/modules/beat/schemas.py` -- `ISEKAI_SYSTEM_VI_TEMPLATE`, added to `BUILTIN_TEMPLATES`
- `backend/app/api/v1/router.py` -- registers `story_remix.router`
- `tools/story_remix/remix.py`, `tools/story_remix/README.md` -- CLI tool
- `backend/tests/api/test_story_remix.py` -- transformation-gate and overlap-gate tests (11 cases)
- `backend/tests/modules/beat/test_templates.py`, `test_router.py` -- builtin id-set/count (13 → 14 builtins)

## Verification

`tests/modules/beat/` + `tests/api/` (580 tests) pass, including the 11
new story_remix tests exercising: the transformation gate rejecting and
repairing a missing axis, `blended_sources` only being required with 2+
sources, HOOK/ENDING beat-position checks, the same-language overlap gate
rejecting a near-verbatim paraphrase while a cross-language pair with
identical text is correctly left unchecked, and the give-up-after-retries
and no-provider-configured error paths. Not yet run end-to-end against a
real source video (needs a live OpenAI key + a real trending URL, per the
user) -- that first real run is the next step, not done as part of this
commit.
