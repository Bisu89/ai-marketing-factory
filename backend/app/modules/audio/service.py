"""Deterministic BGM selection (Task 24 sections 7/36/37) -- no AI call,
ever. Pure and deterministic: the same (candidates, tone, seed) always
selects the same BgmCandidate, with no randomness, no I/O, and no external
state (mirrors app.modules.motion.service's own select_auto_motion, same
reasoning).

Deliberately contains no ffmpeg/subprocess/rendering/database code of any
kind -- this module only *selects*; a future composition root resolves
real Asset rows into BgmCandidate and applies the result. See renderer.py
for the actual mixing engine.
"""

from app.modules.audio.schemas import BgmCandidate

# Section 7's own example table -- checked as substring keywords against a
# lowercased content tone/style string, first match wins. Deliberately
# small and reviewable, matching app.modules.motion.service's own
# _INTENT_RULES shape for the identical reasoning (no ML classifier).
_TONE_RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("emotional", "reflective", "intimate", "tender"), ("piano", "soft", "emotional")),
    (("dramatic", "tense", "cinematic"), ("cinematic", "dramatic", "epic")),
    (("happy", "fun", "upbeat", "playful"), ("upbeat", "happy", "acoustic")),
    (("documentary", "explainer", "informative"), ("ambient", "subtle", "documentary")),
]


def _tag_overlap_score(candidate: BgmCandidate, wanted_tags: tuple[str, ...]) -> int:
    candidate_tags = {tag.lower() for tag in candidate.tags}
    return sum(1 for tag in wanted_tags if tag in candidate_tags)


def select_bgm(candidates: list[BgmCandidate], content_tone: str | None, seed: int) -> BgmCandidate | None:
    """Section 7 (tone-tag matching) + section 36/37 (deterministic
    rotation, no true randomness). `seed` is normally the project id
    directly (section 37's own "use batch/project seed") -- the same
    project always selects the same candidate from an unchanged candidate
    list, so a retry never silently switches tracks, and consecutive
    projects visibly rotate through the library (section 36's own worked
    example: project 01/02/03/04 -> piano_01/02/03/01).

    Returns None when `candidates` is empty -- the caller (composition
    root) decides what that means (section 33/34: OFF vs NEEDS_REVIEW),
    this function never invents a fallback asset.
    """
    if not candidates:
        return None

    ordered = sorted(candidates, key=lambda c: c.asset_id)  # stable, deterministic base ordering

    tone = (content_tone or "").lower()
    for keywords, wanted_tags in _TONE_RULES:
        if not any(keyword in tone for keyword in keywords):
            continue
        scored = [(c, _tag_overlap_score(c, wanted_tags)) for c in ordered]
        matched = [c for c, score in scored if score > 0]
        if matched:
            # Multiple equally-tagged tracks still rotate deterministically
            # by seed (section 36's own "do not use the same BGM blindly
            # for every project when multiple suitable tracks exist").
            return matched[seed % len(matched)]

    # No tone match (or no BGM tagged for the matched mood) -- rotate
    # through every candidate instead of always picking the same one.
    return ordered[seed % len(ordered)]
