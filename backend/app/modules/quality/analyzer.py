"""Pure, deterministic Quality Gate analysis (Task 16 -- see
docs/features/42-content-quality-gate.md). No FFmpeg, no AI/LLM/embedding
calls, no DB, no filesystem access -- every function here takes already-
resolved app.modules.quality.schemas input and returns a QualityReport (or
a piece of one). Mirrors app.modules.composition.service's own "thin,
pure, no cross-module orchestration" shape.

Three conceptual analyzers (section 3), implemented as plain functions
rather than classes (matching this codebase's existing preference for
functions over service objects when there's no state/session to hold --
see app.modules.batch.schemas.parse_scripts, app.modules.asset.ingest.*):

- analyze_narrative / analyze_pacing  -> BeatPlanQualityAnalyzer
- analyze_visual                      -> VisualCoverageAnalyzer
- analyze_motion / analyze_audio / analyze_captions + evaluate_readiness -> ReadinessEvaluator
"""

import math
import re
import statistics
from collections import Counter

from app.modules.quality.schemas import (
    BeatAnalysisInput,
    ProjectAudioConfigInput,
    ProjectCaptionConfigInput,
    QualityAnalysisInput,
    QualityDimensions,
    QualityIssue,
    QualityReport,
    VisualCoverageMetrics,
)

# -- Configurable, documented constants (section 8: "deterministic,
# explainable, configurable") ----------------------------------------------

# A beat more than this many times the project's mean duration (or less
# than 1/this) counts as a pacing outlier. 2.3 is the smallest round value
# that still catches section 7's own literal example (durations 2.0, 4.2,
# 2.1, 2.0, 9.8 -- mean 4.02s, the 9.8s beat is 2.44x the mean).
PACING_OUTLIER_RATIO = 2.3
# Real user report (docs/features/109-quality-gate-long-form.md): a real
# 7.5-minute, 21-beat Story-to-Scene Analysis project (see
# docs/features/103-story-to-scene-analysis.md) got flagged on a punchy
# ~5s hook against a ~21s project average (a 4x+ ratio) and a brief ~8s
# transitional aside -- both deliberate, normal editorial pacing for a
# longer, multi-topic video, not defects. Section 7's own calibration
# example was a 5-beat short video; applying that same fixed ratio
# uniformly regardless of video length produces false positives as beat
# count grows, since more beats naturally means more legitimate pacing
# variety (a short hook is a *smaller* fraction of a 21-beat video than of
# a 5-beat one). PACING_OUTLIER_BASE_BEAT_COUNT keeps every project at or
# under it (covers this app's own typical short-form range, see
# beat_generate.py's own MIN_BEATS/MAX_BEATS=3-18) at exactly the original
# 2.3x ratio -- no existing short-form behavior changes -- and loosens
# gradually, capped, only past that.
PACING_OUTLIER_BASE_BEAT_COUNT = 8
PACING_OUTLIER_RATIO_STEP = 0.1  # per beat past the base count
PACING_OUTLIER_MAX_RATIO = 4.5
# 3+ consecutive beats sharing the same narrative purpose is flagged
# (section 10's own literal example, a 4-beat plan -- see
# test_three_consecutive_same_purpose_flags_duplication). Same long-form
# false-positive as above -- 3 consecutive BUILD beats while a video
# explains one topic after another (e.g. 3 different methods in a row) is
# normal structure, not repetitive pacing; see _consecutive_purpose_threshold
# below, same "unchanged at short-form beat counts" guarantee. 0.22 was
# picked (not the pacing ratio's own step-based approach) against the
# actual real 15-beat project this was reported against -- see
# docs/features/109-quality-gate-long-form.md -- where 3 consecutive BUILD
# beats correctly should NOT flag but 4 still should.
CONSECUTIVE_PURPOSE_WARNING_THRESHOLD = 3
CONSECUTIVE_PURPOSE_RATIO = 0.22
# unique_purposes / total_beats at or below this (with >=3 beats) is "very
# low diversity" (section 9's own literal example: 5x HOOK = 1/5 = 0.20).
LOW_PURPOSE_DIVERSITY_RATIO = 0.34
# ...but the ratio alone punishes long-form: a genuinely well-structured
# 30-beat documentary with all 6 BeatTypes present is 6/30 = 0.20, flagged.
# So the warning also requires the *absolute* distinct-purpose count to be
# below this floor -- 4+ distinct narrative purposes is real structural
# variety regardless of length. Same long-form-false-positive fix as
# _consecutive_purpose_threshold / _pacing_outlier_ratio (feature 109).
LOW_PURPOSE_DIVERSITY_MIN_UNIQUE = 4

_CONFIDENCE_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}
_SUITABILITY_WEIGHT = {"EXCELLENT": 1.0, "GOOD": 0.9, "CROP_REQUIRED": 0.75, "LOW_RESOLUTION": 0.5}
# Visual is weighted highest -- a missing/wrong asset is the single most
# visible defect in a finished video; confidence and resolution are softer,
# secondary signals about *how good* an already-present asset is.
_VISUAL_WEIGHTS = {"coverage": 0.6, "confidence": 0.25, "suitability": 0.15}

# Overall score = weighted sum of the 6 dimensions (sections 23-24) -- sums
# to 1.0. Visual carries the most weight (the thing a viewer notices
# first); pacing/captions the least (already-bounded, rarely catastrophic).
DIMENSION_WEIGHTS = {
    "narrative": 0.20,
    "pacing": 0.15,
    "visual": 0.30,
    "motion": 0.10,
    "audio": 0.15,
    "captions": 0.10,
}

READY_THRESHOLD = 90
NEEDS_REVIEW_THRESHOLD = 70


def _beat_label(beat: BeatAnalysisInput) -> str:
    return f"Beat {beat.order:02d}"


def _pacing_outlier_ratio(beat_count: int) -> float:
    if beat_count <= PACING_OUTLIER_BASE_BEAT_COUNT:
        return PACING_OUTLIER_RATIO
    extra = beat_count - PACING_OUTLIER_BASE_BEAT_COUNT
    return min(PACING_OUTLIER_MAX_RATIO, PACING_OUTLIER_RATIO + extra * PACING_OUTLIER_RATIO_STEP)


def _consecutive_purpose_threshold(beat_count: int) -> int:
    return max(CONSECUTIVE_PURPOSE_WARNING_THRESHOLD, math.ceil(beat_count * CONSECUTIVE_PURPOSE_RATIO))


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _normalize_narration(text: str) -> str:
    """lowercase + strip punctuation + collapse whitespace (section 12) --
    no embeddings, no fuzzy similarity model, just exact-after-normalization
    matching (section 12's own "do NOT add embeddings").
    """
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


# -- BeatPlanQualityAnalyzer: narrative structure + pacing -----------------


def analyze_narrative(beats: list[BeatAnalysisInput]) -> tuple[int, list[QualityIssue]]:
    if not beats:
        return 0, [QualityIssue(code="NO_BEATS", severity="error", message="This project has no beats yet.")]

    issues: list[QualityIssue] = []
    score = 100.0

    purposes = [beat.type for beat in beats]
    if len(purposes) >= 3:
        unique_ratio = len(set(purposes)) / len(purposes)
        if unique_ratio <= LOW_PURPOSE_DIVERSITY_RATIO and len(set(purposes)) < LOW_PURPOSE_DIVERSITY_MIN_UNIQUE:
            issues.append(
                QualityIssue(
                    code="LOW_PURPOSE_DIVERSITY",
                    severity="warning",
                    message=(
                        f"Narrative purpose diversity is very low "
                        f"({len(set(purposes))} unique purpose(s) across {len(purposes)} beats)."
                    ),
                )
            )
            score -= 15

    # Consecutive-run detection (section 10) -- every run of
    # _consecutive_purpose_threshold(len(purposes))+ identical, adjacent
    # purposes (see that function's own docstring/the module-level
    # CONSECUTIVE_PURPOSE_RATIO comment for why this scales with beat count).
    consecutive_threshold = _consecutive_purpose_threshold(len(purposes))
    run_start = 0
    for i in range(1, len(purposes) + 1):
        if i == len(purposes) or purposes[i] != purposes[run_start]:
            run_length = i - run_start
            if run_length >= consecutive_threshold:
                issues.append(
                    QualityIssue(
                        code="PURPOSE_DUPLICATION",
                        severity="warning",
                        beat_id=beats[run_start].id,
                        message=f"{run_length} consecutive {purposes[run_start]} beats starting at {_beat_label(beats[run_start])}.",
                    )
                )
                score -= 10
            run_start = i

    # Duplicate narration (sections 11-12) -- exact match after normalization.
    groups: dict[str, list[BeatAnalysisInput]] = {}
    for beat in beats:
        if beat.narration and beat.narration.strip():
            groups.setdefault(_normalize_narration(beat.narration), []).append(beat)
    for group in groups.values():
        if len(group) > 1:
            labels = ", ".join(_beat_label(beat) for beat in group)
            issues.append(
                QualityIssue(
                    code="DUPLICATE_NARRATION",
                    severity="warning",
                    beat_id=group[0].id,
                    message=f"Repeated narration detected across {labels}.",
                )
            )
            score -= 10

    return _clamp(score), issues


def analyze_pacing(beats: list[BeatAnalysisInput]) -> tuple[int, list[QualityIssue], dict]:
    if not beats:
        return 0, [], {}

    durations = [beat.duration for beat in beats]
    mean = statistics.fmean(durations)
    stdev = statistics.pstdev(durations) if len(durations) > 1 else 0.0
    coefficient_of_variation = (stdev / mean) if mean > 0 else 0.0

    issues: list[QualityIssue] = []
    outlier_count = 0
    ratio = _pacing_outlier_ratio(len(beats))
    for beat in beats:
        if mean <= 0:
            continue
        too_long = beat.duration > mean * ratio
        # A HOOK/ENDING beat being short relative to the project average is
        # deliberate pacing (a punchy open/close), not a defect -- only
        # flag one of these two types for running unusually *long*, never
        # for being short. Every other type still checks both directions.
        too_short = beat.duration < mean / ratio and beat.type not in ("HOOK", "ENDING")
        if too_long or too_short:
            outlier_count += 1
            issues.append(
                QualityIssue(
                    code="PACING_OUTLIER",
                    severity="warning",
                    beat_id=beat.id,
                    message=(
                        f"{_beat_label(beat)} ({beat.duration:.1f}s) is significantly different from "
                        f"the project average ({mean:.1f}s)."
                    ),
                )
            )

    score = 100.0 - min(50, outlier_count * 15) - min(30, coefficient_of_variation * 40)
    metrics = {
        "average": round(mean, 2),
        "minimum": round(min(durations), 2),
        "maximum": round(max(durations), 2),
        "stdev": round(stdev, 2),
        "coefficient_of_variation": round(coefficient_of_variation, 3),
    }
    return _clamp(score), issues, metrics


# -- VisualCoverageAnalyzer --------------------------------------------------


def analyze_visual(beats: list[BeatAnalysisInput]) -> tuple[int, list[QualityIssue], VisualCoverageMetrics]:
    if not beats:
        return 0, [], VisualCoverageMetrics(coverage=0.0)

    issues: list[QualityIssue] = []
    valid_count = high = medium = low = missing = 0
    confidence_scores: list[float] = []
    suitability_scores: list[float] = []

    for beat in beats:
        info = beat.asset
        if not info.has_asset:
            missing += 1
            issues.append(
                QualityIssue(
                    code="MISSING_VISUAL_ASSET",
                    severity="error",
                    beat_id=beat.id,
                    message=f"{_beat_label(beat)} has no assigned visual asset.",
                )
            )
            continue
        if not info.asset_valid:
            missing += 1
            issues.append(
                QualityIssue(
                    code="MISSING_VISUAL_FILE",
                    severity="error",
                    beat_id=beat.id,
                    message=f"{_beat_label(beat)}'s visual asset file is missing or invalid.",
                )
            )
            continue

        valid_count += 1
        confidence_scores.append(_CONFIDENCE_WEIGHT.get(info.asset_confidence or "MEDIUM", 0.7))
        if info.asset_confidence == "LOW":
            low += 1
            issues.append(
                QualityIssue(
                    code="LOW_VISUAL_CONFIDENCE",
                    severity="warning",
                    beat_id=beat.id,
                    message=f"{_beat_label(beat)} has a weak visual match for its visual intent.",
                )
            )
        elif info.asset_confidence == "MEDIUM":
            medium += 1
        else:
            high += 1

        if info.portrait_suitability:
            suitability_scores.append(_SUITABILITY_WEIGHT.get(info.portrait_suitability, 0.8))
            if info.portrait_suitability == "LOW_RESOLUTION":
                issues.append(
                    QualityIssue(
                        code="LOW_RESOLUTION_ASSET",
                        severity="warning",
                        beat_id=beat.id,
                        message=f"{_beat_label(beat)}'s visual asset is low resolution for this project's render profile.",
                    )
                )

    coverage = valid_count / len(beats)
    avg_confidence = statistics.fmean(confidence_scores) if confidence_scores else 0.0
    # No penalty when suitability is simply unknown (e.g. a legacy asset
    # with no recorded width/height) -- absence of data isn't a defect.
    avg_suitability = statistics.fmean(suitability_scores) if suitability_scores else 1.0

    score = (
        coverage * 100 * _VISUAL_WEIGHTS["coverage"]
        + avg_confidence * 100 * _VISUAL_WEIGHTS["confidence"]
        + avg_suitability * 100 * _VISUAL_WEIGHTS["suitability"]
    )
    metrics = VisualCoverageMetrics(
        coverage=round(coverage, 3), high_confidence=high, medium_confidence=medium, low_confidence=low, missing=missing
    )
    return _clamp(score), issues, metrics


# -- ReadinessEvaluator: motion / audio / captions + final decision --------


def analyze_motion(beats: list[BeatAnalysisInput], default_motion_preset: str | None) -> tuple[int, list[QualityIssue]]:
    if not beats:
        return 0, []
    issues: list[QualityIssue] = []
    unresolved = 0
    artifact_missing = 0
    for beat in beats:
        effective = beat.motion_preset or default_motion_preset
        if not effective:
            unresolved += 1
            issues.append(
                QualityIssue(
                    code="MISSING_MOTION",
                    severity="error",
                    beat_id=beat.id,
                    message=f"{_beat_label(beat)} has no motion preset and no project default is configured.",
                )
            )
        # Task 23 section 55 -- a real Beat/asset combination this GATE
        # actually checked for a pre-rendered clip (motion_artifact_checked
        # is only True when a real project_id was available, see
        # quality_gate.py's build_quality_input) and found missing/invalid.
        # A warning, not an error: the final render still falls back to
        # rendering the clip on demand (composition_render.py's own
        # render_beats_for_job), so a missing cache is slower, not broken.
        elif beat.motion_artifact_checked and not beat.motion_artifact_valid and beat.asset.has_asset and beat.asset.asset_valid:
            artifact_missing += 1
            issues.append(
                QualityIssue(
                    code="MOTION_ARTIFACT_MISSING",
                    severity="warning",
                    beat_id=beat.id,
                    message=f"{_beat_label(beat)} has no valid pre-rendered motion clip yet (will render on demand).",
                )
            )
    if unresolved == 0 and artifact_missing == 0:
        return 100, issues
    return _clamp(100 * (len(beats) - unresolved - artifact_missing) / len(beats)), issues


def analyze_audio(beats: list[BeatAnalysisInput], config: ProjectAudioConfigInput) -> tuple[int, list[QualityIssue]]:
    if not config.narration_enabled:
        # Silent beats are explicitly supported at the project level (Task
        # 12's own AudioProjectConfig.narration_enabled) -- section 13's
        # "if silent Beats are supported, respect it."
        return 100, []
    if not beats:
        return 0, []

    missing = [beat for beat in beats if not (beat.narration and beat.narration.strip())]
    issues: list[QualityIssue] = []
    if len(missing) == len(beats):
        issues.append(
            QualityIssue(
                code="INVALID_AUDIO_CONFIG",
                severity="error",
                message="Narration is enabled for this project, but no beat has any narration text.",
            )
        )
    for beat in missing:
        issues.append(
            QualityIssue(
                code="MISSING_NARRATION",
                severity="error",
                beat_id=beat.id,
                message=f"{_beat_label(beat)} has no narration text, but narration is enabled for this project.",
            )
        )
    score = _clamp(100 * (len(beats) - len(missing)) / len(beats))

    # Task 24 section 55/62 -- a real, previously-attempted Audio Master
    # (audio_master_checked is only True when a real project_id was
    # available, see quality_gate.py's build_quality_input) that's now
    # missing/invalid. A warning, not an error: this dimension's score
    # already reflects narration readiness on its own merits; a stale
    # Audio Master is a reconciliation signal (section 62), not proof the
    # project itself is unready.
    if config.audio_master_checked and not config.audio_master_valid:
        issues.append(
            QualityIssue(
                code="AUDIO_MASTER_MISSING",
                severity="warning",
                message="This project's Audio Master is missing or stale and will need to be regenerated.",
            )
        )

    return score, issues


def analyze_captions(
    beats: list[BeatAnalysisInput], config: ProjectCaptionConfigInput
) -> tuple[int, list[QualityIssue]]:
    if not config.enabled:
        return 100, []
    if not config.preset_valid:
        return 0, [QualityIssue(code="INVALID_CAPTION_CONFIG", severity="error", message="Caption preset is invalid.")]
    if not any(beat.narration and beat.narration.strip() for beat in beats):
        return 0, [
            QualityIssue(
                code="INVALID_CAPTION_CONFIG",
                severity="error",
                message="Captions are enabled, but there is no narration text anywhere to caption.",
            )
        ]

    issues: list[QualityIssue] = []
    # Task 25 section 55/62 -- same "only a warning, only when a real
    # project_id was available and a prior run actually claimed this
    # artifact" reasoning as analyze_audio's own AUDIO_MASTER_MISSING check
    # above (captions_artifact_checked is only True in that circumstance,
    # see quality_gate.py's build_quality_input).
    if config.captions_artifact_checked and not config.captions_artifact_valid:
        issues.append(
            QualityIssue(
                code="CAPTIONS_ARTIFACT_MISSING",
                severity="warning",
                message="This project's captions.ass is missing or stale and will need to be regenerated.",
            )
        )
    return 100, issues


def evaluate_readiness(analysis_input: QualityAnalysisInput) -> QualityReport:
    """The final combination step (section 25): blocking issues always
    override the numeric score -- a 95 with a missing asset is still
    BLOCKED, never READY. In STRICT mode, NEEDS_REVIEW is not
    override-able (section 28: "serious warnings can prevent render") --
    it becomes BLOCKED outright rather than something "Render Anyway" can
    bypass.
    """
    beats = analysis_input.beats

    narrative_score, narrative_issues = analyze_narrative(beats)
    pacing_score, pacing_issues, pacing_metrics = analyze_pacing(beats)
    visual_score, visual_issues, visual_metrics = analyze_visual(beats)
    motion_score, motion_issues = analyze_motion(beats, analysis_input.default_motion_preset)
    audio_score, audio_issues = analyze_audio(beats, analysis_input.audio)
    caption_score, caption_issues = analyze_captions(beats, analysis_input.captions)

    all_issues = narrative_issues + pacing_issues + visual_issues + motion_issues + audio_issues + caption_issues
    errors = [issue for issue in all_issues if issue.severity == "error"]
    warnings = [issue for issue in all_issues if issue.severity == "warning"]

    dimensions = QualityDimensions(
        narrative=narrative_score,
        pacing=pacing_score,
        visual=visual_score,
        motion=motion_score,
        audio=audio_score,
        captions=caption_score,
    )
    overall = _clamp(sum(getattr(dimensions, key) * weight for key, weight in DIMENSION_WEIGHTS.items()))

    if errors:
        status = "BLOCKED"
    elif overall < NEEDS_REVIEW_THRESHOLD:
        status = "BLOCKED"
    elif warnings or overall < READY_THRESHOLD:
        # READY requires a *clean* plan (score >= 90 AND zero warnings), not
        # just a high score -- with several beats, a single real, human-
        # noticeable problem (one weak visual match, one duplicate line of
        # narration) barely moves a weighted average built from 6
        # dimensions, so a pure score threshold would silently let a real,
        # known issue slide through as READY. A single flagged beat should
        # always surface for a look, even if its score impact rounds away
        # to nothing -- never silently swallowed into a 99/100.
        status = "NEEDS_REVIEW"
    else:
        status = "READY"

    if status == "NEEDS_REVIEW" and analysis_input.mode == "STRICT":
        status = "BLOCKED"

    return QualityReport(
        status=status,
        score=overall,
        dimensions=dimensions,
        issues=errors,
        warnings=warnings,
        visual=visual_metrics,
        metrics={"pacing": pacing_metrics, "purpose_distribution": dict(Counter(beat.type for beat in beats))},
    )
