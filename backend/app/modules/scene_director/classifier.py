"""Pure, deterministic AI Scene Director classification (Phase 0 -- see the
AI Storytelling Studio plan, section 14). No AI/LLM call, no I/O.

`classify_scene` scores one scene on four axes and picks a visual mode;
`classify_scenes` runs the batch and then applies the AI_VIDEO budget
(ratio + hard cap), demoting the lowest-scoring video candidates to
STILL_WITH_MOTION. Cost is deliberately NOT computed here -- that needs
pricing and belongs to app.modules.ai.cost_estimator, which consumes this
module's output.

Every threshold and word list below is documented and lives here, in one
place, matching app.modules.quality.analyzer's own "deterministic,
explainable, configurable" convention.
"""

import re

from app.modules.scene_director.schemas import (
    SceneAnalysisInput,
    SceneClassification,
    SceneDirectorConfig,
    SceneDirectorReport,
)

# -- Scoring inputs (all lowercase; matched as whole words against the
# normalized narration + a synthetic dialogue marker) --------------------

# Physical, on-screen motion -- the only thing that actually justifies an
# AI-video clip in an audio-first product. Emotional intensity alone does
# NOT (a tearful monologue is a great STILL close-up).
_MOVEMENT_VERBS = frozenset("""
run runs ran running sprint sprints sprinting rush rushes rushing chase chases chasing
flee flees fleeing escape escapes escaping fight fights fighting battle battles clash
charge charges charging storm storms march marches marching ride rides riding gallop
jump jumps jumping leap leaps fall falls falling collapse collapses collapsing crumble
throw throws throwing hurl grab grabs grabbing strike strikes striking punch hit hits
swing swings climbing climb climbs crash crashes crashing explode explodes exploding
burn burns burning shatter shatters dance dances dancing spin spins swirl drag drags
push pushes pull pulls kick kicks stab stabs slash draws sword arrow fired gunfire
""".split())

# Emotion label -> base emotion score. Anything not listed scores as
# medium-low (35). Punctuation density adds on top (see _emotion_score).
_EMOTION_INTENSITY = {
    "betrayal": 90, "rage": 88, "fury": 88, "terror": 88, "horror": 85, "despair": 85,
    "grief": 82, "ecstasy": 80, "panic": 80, "shame": 72, "dread": 78, "anguish": 82,
    "hatred": 80, "triumph": 75, "shock": 78, "heartbreak": 82, "desperation": 80,
    "anger": 62, "fear": 60, "sadness": 55, "joy": 52, "love": 55, "hope": 50,
    "tension": 58, "jealousy": 60, "guilt": 55, "longing": 48, "relief": 42,
    "calm": 20, "neutral": 15, "reflective": 25, "curious": 28, "wonder": 35, "nostalgia": 40,
}

# scene_type -> importance base (0-100). The Story engine's own type
# vocabulary; unknown types fall through to BODY.
_TYPE_IMPORTANCE = {
    "climax": 95, "reveal": 88, "twist": 90, "turning_point": 85, "confrontation": 78,
    "hook": 70, "reversal": 82, "revelation": 88, "decision": 65, "ending": 62,
    "setup": 35, "build": 45, "reaction": 40, "transition": 20, "body": 40, "aside": 22,
}

_DYNAMIC_CAMERA = frozenset({
    "tracking", "handheld", "whip", "dolly", "crane", "aerial", "drone",
    "pov", "point of view", "following", "chase", "orbit",
})

_WORD_RE = re.compile(r"[a-z']+")


def _words(text: str | None) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return int(round(max(low, min(high, value))))


def _importance_score(scene: SceneAnalysisInput) -> int:
    stype = (scene.scene_type or "body").strip().lower()
    base = _TYPE_IMPORTANCE.get(stype, 40)
    if scene.is_chapter_end:
        base += 12
    # A dialogue-heavy scene is doing narrative work (a confrontation, a
    # negotiation) -- bump it, capped so it can't outweigh a real climax.
    base += min(scene.dialogue_line_count * 4, 16)
    return _clamp(base)


def _movement_score(scene: SceneAnalysisInput) -> int:
    words = set(_words(scene.narration))
    hits = len(words & _MOVEMENT_VERBS)
    score = min(hits * 22, 80)  # 0 hits -> 0, 1 -> 22, 2 -> 44, 3 -> 66, 4+ -> 80
    cam = (scene.camera or "").lower()
    if any(k in cam for k in _DYNAMIC_CAMERA):
        score += 20
    return _clamp(score)


def _emotion_score(scene: SceneAnalysisInput) -> int:
    label = (scene.emotion or "neutral").strip().lower()
    base = _EMOTION_INTENSITY.get(label, 35)
    text = scene.narration or ""
    # Exclamation / question density is a cheap, deterministic proxy for
    # delivered intensity on top of the declared label.
    marks = text.count("!") + text.count("?")
    base += min(marks * 6, 18)
    return _clamp(base)


def _complexity_score(scene: SceneAnalysisInput) -> int:
    score = min(scene.character_count * 18, 54)  # 0,18,36,54(+)
    if not scene.same_location_as_prev:
        score += 22  # a location change is a fresh visual to establish
    if scene.dialogue_line_count >= 2:
        score += 10
    return _clamp(score)


def _density_bias(density: str) -> float:
    # Added to the composite before the STILL vs STILL_WITH_MOTION cut only
    # (never pushes a scene over video_threshold).
    return {"MINIMAL": -12.0, "BALANCED": 0.0, "CINEMATIC": +12.0}[density]


def _motion_hint(scene: SceneAnalysisInput, movement: int, emotion: int, mode: str) -> str:
    if mode == "STILL":
        return "STATIC" if emotion < 45 else "SLOW_PUSH_IN"
    # STILL_WITH_MOTION (AI_VIDEO scenes render as a real clip -- the hint
    # is only used as a fallback if the clip is missing, so still give one)
    cam = (scene.camera or "").lower()
    if "wide" in cam or "establish" in cam:
        return "SLOW_PULL_OUT"
    if "pan" in cam or movement >= 45:
        return "ZOOM_AND_PAN"
    if emotion >= 70:
        return "SLOW_PUSH_IN"
    return "SLOW_PUSH_IN"


def _priority(composite: int) -> str:
    if composite >= 66:
        return "high"
    if composite >= 38:
        return "medium"
    return "low"


def classify_scene(scene: SceneAnalysisInput, config: SceneDirectorConfig) -> SceneClassification:
    """Score one scene and pick a provisional visual mode. The AI_VIDEO
    budget (ratio / hard cap) is applied later, across the whole set, by
    classify_scenes -- a scene returned as AI_VIDEO here is a *candidate*,
    not final.
    """
    imp = _importance_score(scene)
    mov = _movement_score(scene)
    emo = _emotion_score(scene)
    cplx = _complexity_score(scene)

    composite_raw = (
        config.w_importance * imp
        + config.w_movement * mov
        + config.w_emotion * emo
        + config.w_complexity * cplx
    )
    composite = _clamp(composite_raw)

    if not config.enabled:
        mode, reason = "STILL_WITH_MOTION", "scene director disabled -- default motion"
    elif composite_raw >= config.video_threshold and mov >= config.min_movement_for_video:
        mode, reason = "AI_VIDEO", f"high impact ({composite}) with real on-screen movement ({mov})"
    elif composite_raw + _density_bias(config.visual_density) >= config.still_motion_threshold:
        mode, reason = "STILL_WITH_MOTION", f"composite {composite} above motion threshold"
    else:
        mode, reason = "STILL", f"low visual priority (composite {composite})"

    reuse = (
        mode == "STILL"
        and composite < 32
        and scene.same_location_as_prev
        and scene.same_characters_as_prev
    )
    if reuse:
        reason += " -- reuse previous scene's image ($0)"

    return SceneClassification(
        scene_id=scene.id,
        importance_score=imp,
        movement_score=mov,
        emotion_score=emo,
        complexity_score=cplx,
        composite_score=composite,
        visual_mode=mode,
        visual_priority=_priority(composite),
        motion_preset_hint=_motion_hint(scene, mov, emo, mode),
        reuse_existing_asset=reuse,
        estimated_duration=scene.duration_hint,
        reason=reason,
    )


def classify_scenes(
    scenes: list[SceneAnalysisInput], config: SceneDirectorConfig
) -> SceneDirectorReport:
    """Classify every scene, then enforce the AI_VIDEO budget: keep only
    the top `min(hard_cap, round(ratio * total))` AI_VIDEO candidates by
    composite score; demote the rest to STILL_WITH_MOTION. Deterministic:
    ties broken by scene order (the earlier scene wins its video slot).
    """
    results = [classify_scene(s, config) for s in scenes]
    order_by_id = {s.id: s.order for s in scenes}

    candidates = [r for r in results if r.visual_mode == "AI_VIDEO"]
    budget = min(config.ai_video_hard_cap, round(config.ai_video_max_ratio * len(scenes)))
    demoted: list[str] = []

    if len(candidates) > budget:
        ranked = sorted(
            candidates,
            key=lambda r: (-r.composite_score, order_by_id.get(r.scene_id, 0)),
        )
        keep = {r.scene_id for r in ranked[:budget]}
        for i, r in enumerate(results):
            if r.visual_mode == "AI_VIDEO" and r.scene_id not in keep:
                results[i] = r.model_copy(update={
                    "visual_mode": "STILL_WITH_MOTION",
                    "reason": r.reason + f" -- demoted to fit AI_VIDEO budget ({budget}/{len(scenes)})",
                })
                demoted.append(r.scene_id)

    return SceneDirectorReport(
        scenes=results,
        ai_video_count=sum(1 for r in results if r.visual_mode == "AI_VIDEO"),
        still_with_motion_count=sum(1 for r in results if r.visual_mode == "STILL_WITH_MOTION"),
        still_count=sum(1 for r in results if r.visual_mode == "STILL"),
        reuse_count=sum(1 for r in results if r.reuse_existing_asset),
        demoted_scene_ids=demoted,
    )
