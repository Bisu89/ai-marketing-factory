"""Content Quality Gate (Task 16 -- see docs/features/42-content-quality-gate.md):
the composition root for turning a real BeatPlan + resolved Assets into an
app.modules.quality analysis. Per app/modules/README.md, app.modules.quality
itself must never import app.modules.beat or app.modules.asset -- this file
is the one place allowed to import both, exactly like
app/api/v1/endpoints/composition_render.py already does for building a
CompositionPlan out of a live BeatPlan + resolved Assets.

`run_quality_check` (plain function, not just an HTTP handler) is imported
directly by app/api/v1/endpoints/batch_render.py's render_batch() -- a
composition-root file importing another composition-root file is the
established, already-used pattern (batch_render.py already imports
render_composition from composition_render.py and generate_beat_plan from
beat_generate.py); the "a module may never import another module" rule is
about app/modules/*, not app/api/v1/endpoints/*.
"""

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.motion_generate import motion_artifact_for_beat, motion_was_attempted_for_beat
from app.core.config import Settings, get_settings
from app.core.render_profile import get_render_profile
from app.db.session import get_db
from app.modules.asset.ingest import classify_portrait_suitability, tokenize_filename
from app.modules.asset.models import Asset
from app.modules.asset.service import AssetService
from app.modules.beat.project_service import get_project_draft
from app.modules.beat.schemas import Beat, BeatPlan, ProjectConfig
from app.modules.quality.analyzer import evaluate_readiness
from app.modules.quality.schemas import (
    BeatAnalysisInput,
    BeatAssetInfo,
    ProjectAudioConfigInput,
    ProjectCaptionConfigInput,
    QualityAnalysisInput,
    QualityReport,
)

router = APIRouter()

# A visual_hint/narration with no lexical overlap with the assigned asset's
# own tags/filename at all still counts as "confident" once overlap ratio
# reaches this fraction of the hint's own tokens.
_HIGH_CONFIDENCE_OVERLAP_RATIO = 0.5
_PUNCTUATION_RE = re.compile(r"[^\w\s]")


def tokenize_prose(text: str) -> set[str]:
    """tokenize_filename (Task 15) is built for filenames -- it splits on
    _/-/space but never strips sentence punctuation, so "home." would never
    match a clean "home" tag. Narration/visual_hint is prose, not a
    filename, so punctuation is stripped first.
    """
    return set(tokenize_filename(_PUNCTUATION_RE.sub(" ", text), strip_stopwords=False))


def compute_asset_confidence(beat: Beat, asset: Asset) -> str:
    """A deterministic, explainable stand-in for "how well does this
    assigned asset match what this beat is supposed to show" -- there is no
    real AssetMatcher/VisualIntent system in this codebase to ask (see this
    task's own docs/features/42-content-quality-gate.md finding, and Task
    15's identical finding). Reuses Task 15's own filename tokenizer
    (app.modules.asset.ingest.tokenize_filename) against the beat's
    visual_hint vs. the asset's tags/filename -- the same deterministic
    keyword-overlap approach AssetService.search() already uses to rank
    assets, just run in the opposite direction (given one specific
    assignment, how good is it) instead of ranking many.

    Deliberately does NOT fall back to `narration` when visual_hint is
    absent: narration is what's *said* (story content), not what's *shown*
    -- most real beats never fill in a separate visual_hint at all, so
    treating narration prose as a visual-intent proxy would flag the
    ordinary, common case as a weak match far too often. No visual_hint at
    all -> HIGH: there is genuinely no stated visual intent to contradict
    the assignment, so it is not penalized for a gap in the beat's own
    authored text.

    Public (not `_`-prefixed), same reasoning as batch_render.py's own
    project_composition_plan promotion: Task 18's
    app/api/v1/endpoints/factory_pipeline.py -- another composition root --
    reuses this (and tokenize_prose below) directly for its own auto-assign
    stage's candidate search + confidence check, rather than a second
    implementation of the same keyword-overlap logic.
    """
    hint_tokens = tokenize_prose(beat.visual_hint) if beat.visual_hint else set()
    if not hint_tokens:
        return "HIGH"

    tag_tokens = {tag.lower() for tag in asset.tags}
    filename_tokens = set(tokenize_filename(asset.filename))
    overlap = hint_tokens & (tag_tokens | filename_tokens)
    ratio = len(overlap) / len(hint_tokens)

    if ratio >= _HIGH_CONFIDENCE_OVERLAP_RATIO:
        return "HIGH"
    if ratio > 0:
        return "MEDIUM"
    return "LOW"


def _resolve_beat_asset_info(beat: Beat, asset_service: AssetService) -> BeatAssetInfo:
    if beat.asset_id is None:
        return BeatAssetInfo(has_asset=False, asset_valid=False)

    try:
        asset = asset_service.get(beat.asset_id)
    except Exception:
        # NotFoundError -- the referenced Asset row is gone entirely (not
        # just its file). Same "not visually ready" verdict as a MISSING
        # file (section 18).
        return BeatAssetInfo(has_asset=True, asset_valid=False)

    if asset.effective_status != "ACTIVE":
        return BeatAssetInfo(has_asset=True, asset_valid=False)

    return BeatAssetInfo(
        has_asset=True,
        asset_valid=True,
        asset_confidence=compute_asset_confidence(beat, asset),
        portrait_suitability=classify_portrait_suitability(asset.width, asset.height),
    )


def _resolve_motion_artifact_flags(
    beat: Beat, config: ProjectConfig, project_id: int | None, settings: Settings | None,
) -> tuple[bool, bool]:
    """Task 23 section 55/62 -- (checked, valid). Only ever checks when a
    real project_id/settings pair is available (a saved Project, not an
    arbitrary in-editor BeatPlan -- see build_quality_input's own callers),
    the beat actually has a visual asset to have animated in the first
    place, AND a prior Motion stage run actually claimed to have rendered
    this beat (motion_was_attempted_for_beat) -- a project that never ran
    Motion at all has nothing stale to report; this is a *reconciliation*
    check (section 62), never a "you must pre-render motion" requirement.
    """
    if project_id is None or settings is None or beat.asset_id is None:
        return False, True
    if not motion_was_attempted_for_beat(project_id, beat.id, settings.library_dir):
        return False, True
    render_profile = get_render_profile(config.render.profile)
    artifact = motion_artifact_for_beat(
        project_id, beat.id, settings.library_dir,
        beat.duration, render_profile.width, render_profile.height, render_profile.fps,
    )
    return True, artifact is not None


def build_quality_input(
    beats: list[Beat], config: ProjectConfig, asset_service: AssetService, mode: str = "NORMAL",
    project_id: int | None = None, settings: Settings | None = None,
) -> QualityAnalysisInput:
    beats_input = []
    for beat in sorted(beats, key=lambda b: b.order):
        checked, valid = _resolve_motion_artifact_flags(beat, config, project_id, settings)
        beats_input.append(
            BeatAnalysisInput(
                id=beat.id,
                order=beat.order,
                type=beat.type.value,
                narration=beat.narration,
                duration=beat.duration,
                visual_hint=beat.visual_hint,
                motion_preset=beat.motion_preset.value if beat.motion_preset else None,
                asset=_resolve_beat_asset_info(beat, asset_service),
                motion_artifact_checked=checked,
                motion_artifact_valid=valid,
            )
        )
    return QualityAnalysisInput(
        beats=beats_input,
        default_motion_preset=config.motion.default_preset.value,
        audio=ProjectAudioConfigInput(narration_enabled=config.audio.narration_enabled),
        # CaptionsProjectConfig.preset is already Pydantic-validated against
        # the known preset set at load time -- if this config object exists
        # at all, its preset is valid by construction.
        captions=ProjectCaptionConfigInput(enabled=config.captions.enabled, preset_valid=True),
        mode=mode,
    )


def run_quality_check(
    beats: list[Beat], config: ProjectConfig, asset_service: AssetService, mode: str = "NORMAL",
    project_id: int | None = None, settings: Settings | None = None,
) -> QualityReport:
    return evaluate_readiness(build_quality_input(beats, config, asset_service, mode=mode, project_id=project_id, settings=settings))


class QualityCheckRequest(BaseModel):
    plan: BeatPlan
    mode: str = "NORMAL"


@router.post("/quality-check", response_model=QualityReport)
def check_plan_quality(payload: QualityCheckRequest, db: Session = Depends(get_db)) -> QualityReport:
    """Checks an arbitrary (possibly unsaved) BeatPlan -- used by the
    frontend's "Production Check" step to validate whatever is currently in
    the editor, including edits the user hasn't clicked Save on yet.
    """
    return run_quality_check(payload.plan.beats, payload.plan.config, AssetService(db), mode=payload.mode)


@router.post("/projects/{project_id}/quality-check", response_model=QualityReport)
def check_project_quality(
    project_id: int, mode: str = "NORMAL", db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> QualityReport:
    """Checks a Project's currently-*saved* BeatPlan (the lenient draft --
    zero beats is a real, valid pre-"Generate Beats" state, reported as
    NO_BEATS/BLOCKED rather than a 4xx)."""
    draft = get_project_draft(project_id)
    return run_quality_check(draft.beats, draft.config, AssetService(db), mode=mode, project_id=project_id, settings=settings)
