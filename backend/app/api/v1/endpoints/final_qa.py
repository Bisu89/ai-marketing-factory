"""Final QA (Task 28 -- see docs/features/54-final-qa.md): the
composition-root adapter between app.modules.postqa (pure logic, see that
module's own docstring) and app.modules.beat/video_composer, reusing
package_generate.py/audio_generate.py/caption_generate.py/motion_generate.py's
own already-resolved artifact paths/validators (a composition-root file
importing another composition-root file is this codebase's own established
pattern -- see batch_render.py's own imports of composition_render.py and
beat_generate.py).

Read-only (section 38/39): never regenerates or repairs a single artifact.
A FAIL just reports the problem and names a `repair_stage` -- a human (or
a targeted stage retry) does the actual fixing. Cheap by construction
(section 48): one ffprobe call, one ffmpeg `volumedetect` pass, a few
already-produced sidecar-file reads -- never a second full render/frame
decode.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.audio_generate import audio_master_path
from app.api.v1.endpoints.caption_generate import captions_ass_path, captions_is_valid
from app.api.v1.endpoints.motion_generate import motion_artifact_for_beat, motion_was_attempted_for_beat
from app.api.v1.endpoints.package_generate import (
    METADATA_ENGINE_VERSION,
    PackageError,
    _completed_render_job,
    _load_cache,
    _read_render_metadata,
    metadata_path,
    thumbnail_path,
    validate_package,
)
from app.core.config import Settings, get_settings
from app.core.render_profile import get_render_profile
from app.modules.beat.project_service import get_project_draft
from app.modules.postqa.analyzer import evaluate_final_qa, overall_status, score_from_checks
from app.modules.postqa.schemas import (
    AudioLevelInfo,
    BeatCompletenessInfo,
    CaptionsInfo,
    DependencyFreshnessInfo,
    MetadataInfo,
    QAInput,
    QAReport,
    ThumbnailInfo,
    VersionInfo,
)
from app.modules.postqa.renderer import (
    parse_ass_captions,
    probe_audio_levels,
    probe_final_video,
    probe_thumbnail_dimensions,
    thumbnail_looks_low_quality,
)
from app.modules.video_composer.models import VideoComposeJob

logger = logging.getLogger(__name__)
router = APIRouter()

QA_REPORT_FILENAME = "qa_report.json"
PIPELINE_VERSION = "final-qa-v1"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def qa_report_path(job: VideoComposeJob) -> Path:
    return Path(job.output_path).parent / QA_REPORT_FILENAME


# -- Building QAInput from live application state (section 8/17/20/22/28/30/32) --


def _build_metadata_info(meta_path: Path) -> MetadataInfo:
    if not meta_path.exists():
        return MetadataInfo(exists=False, parses=False, title=None, description=None, hashtags=None, referenced_video=None, referenced_thumbnail=None)
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MetadataInfo(exists=True, parses=False, title=None, description=None, hashtags=None, referenced_video=None, referenced_thumbnail=None)
    return MetadataInfo(
        exists=True, parses=True, title=data.get("title"), description=data.get("description"),
        hashtags=data.get("hashtags"), referenced_video=data.get("video"), referenced_thumbnail=data.get("thumbnail"),
    )


def _build_captions_info(project_id: int, captions_enabled: bool, settings: Settings) -> CaptionsInfo:
    if not captions_enabled:
        return CaptionsInfo(enabled=False, exists=False, parses=False, dialogue_count=0, max_end_time=None)
    ass_path = captions_ass_path(project_id, settings.library_dir)
    if not ass_path.exists() or not captions_is_valid(project_id, settings):
        return CaptionsInfo(enabled=True, exists=ass_path.exists(), parses=False, dialogue_count=0, max_end_time=None)
    try:
        content = ass_path.read_text(encoding="utf-8")
    except OSError:
        return CaptionsInfo(enabled=True, exists=True, parses=False, dialogue_count=0, max_end_time=None)
    count, max_end = parse_ass_captions(content)
    return CaptionsInfo(enabled=True, exists=True, parses=True, dialogue_count=count, max_end_time=max_end)


def _build_beats_info(project_id: int, draft, settings: Settings, render_profile) -> BeatCompletenessInfo:
    """Section 30/31 -- by the time Final QA ever runs, final.mp4 already
    exists, which already proves every beat rendered *something*; this is
    mostly a "is the cache warm" reconciliation signal (WARN-only, see
    app.modules.postqa.analyzer.check_beat_completeness), not a genuine
    completeness question anymore.
    """
    beats = draft.beats
    total = len(beats)
    orders = sorted(b.order for b in beats)
    contiguous = orders == list(range(1, total + 1))
    with_artifact = 0
    for beat in beats:
        if beat.asset_id is None:
            continue
        if not motion_was_attempted_for_beat(project_id, beat.id, settings.library_dir):
            continue
        artifact = motion_artifact_for_beat(
            project_id, beat.id, settings.library_dir,
            beat.duration, render_profile.width, render_profile.height, render_profile.fps,
        )
        if artifact is not None:
            with_artifact += 1
    return BeatCompletenessInfo(total_beats=total, beats_with_motion_artifact=with_artifact, order_is_contiguous=contiguous)


def _build_dependency_info(project_id: int, captions_enabled: bool, settings: Settings, video_path: Path) -> DependencyFreshnessInfo:
    """Section 32/33 -- a real mtime comparison, not a fingerprint
    comparison (no fingerprint was ever recorded into render_metadata.json
    at render time -- see docs/features/52-final-composer.md's own
    "Problems" section on why the render step has no cache to compare
    against). `None` means "not applicable to this project," never
    conflated with "confirmed fresh."
    """
    audio_stale = None
    audio_path = audio_master_path(project_id, settings.library_dir)
    if audio_path.exists() and video_path.exists():
        audio_stale = audio_path.stat().st_mtime > video_path.stat().st_mtime

    captions_stale = None
    if captions_enabled:
        ass_path = captions_ass_path(project_id, settings.library_dir)
        if ass_path.exists() and video_path.exists():
            captions_stale = ass_path.stat().st_mtime > video_path.stat().st_mtime

    return DependencyFreshnessInfo(audio_master_is_newer_than_video=audio_stale, captions_is_newer_than_video=captions_stale)


def build_qa_input(project_id: int, settings: Settings) -> QAInput:
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    render_profile = get_render_profile(draft.config.render.profile)

    package_exists = True
    package_error_message = None
    try:
        validate_package(project_id, settings)
    except PackageError as exc:
        package_exists = False
        package_error_message = str(exc)

    if job is None:
        return QAInput(
            project_id=project_id, package_exists=False,
            package_error_message=package_error_message or "No completed render exists for this project yet.",
            video=None, expected_width=render_profile.width, expected_height=render_profile.height,
            expected_fps=render_profile.fps, expected_duration=None, audio_level=None,
            narration_enabled=draft.config.audio.narration_enabled,
            thumbnail=None, metadata=None,
            captions=CaptionsInfo(enabled=draft.config.captions.enabled, exists=False, parses=False, dialogue_count=0, max_end_time=None),
            beats=BeatCompletenessInfo(total_beats=len(draft.beats), beats_with_motion_artifact=0, order_is_contiguous=True),
            dependencies=DependencyFreshnessInfo(audio_master_is_newer_than_video=None, captions_is_newer_than_video=None),
            version=VersionInfo(package_engine_version=None, current_package_engine_version=METADATA_ENGINE_VERSION),
        )

    render_meta = _read_render_metadata(job)
    expected_width = int(render_meta.get("width") or render_profile.width)
    expected_height = int(render_meta.get("height") or render_profile.height)
    expected_fps = float(render_meta.get("fps") or render_profile.fps)

    video_path = Path(job.output_path)
    video_info = probe_final_video(video_path)

    # Section 15 -- Audio Master is the authoritative duration source
    # (the exact same source Task 26's own Final Composer already trims
    # its own output to -- see docs/features/52-final-composer.md).
    expected_duration = None
    audio_path = audio_master_path(project_id, settings.library_dir)
    if audio_path.exists():
        expected_duration = probe_final_video(audio_path).duration or None
    if not expected_duration:
        expected_duration = float(render_meta.get("duration") or 0.0) or None

    # Outro Card (docs/features/89-outro-card.md): Audio Master's own
    # duration only covers the main, narration-driven video -- a real bug
    # found during this feature's own live verification, where a real
    # render with a real outro appended got flagged FINAL_DURATION_MISMATCH
    # here even though the extra length was entirely expected (the outro
    # deliberately extends the video beyond narration's length). The
    # pre-outro hold (docs/features/94-outro-pre-hold.md,
    # video_composer/service.py's own _PRE_OUTRO_HOLD_SEC -- duplicated
    # here, not imported: module isolation) adds further real length on
    # top of the outro clip's own duration.
    _PRE_OUTRO_HOLD_SEC = 1.5
    if expected_duration is not None and job.outro_clip_path and Path(job.outro_clip_path).exists():
        outro_duration = probe_final_video(Path(job.outro_clip_path)).duration
        if outro_duration:
            expected_duration += outro_duration + _PRE_OUTRO_HOLD_SEC

    audio_level = probe_audio_levels(video_path) if video_info.file_exists else AudioLevelInfo(mean_volume_db=None, max_volume_db=None, probed=False)

    thumb_path = thumbnail_path(job)
    thumb_dims = probe_thumbnail_dimensions(thumb_path) if thumb_path.exists() else None
    thumbnail_info = ThumbnailInfo(
        exists=thumb_path.exists(),
        width=thumb_dims[0] if thumb_dims else None, height=thumb_dims[1] if thumb_dims else None,
        expected_width=expected_width, expected_height=expected_height,
        file_size=thumb_path.stat().st_size if thumb_path.exists() else 0,
        is_low_quality=thumbnail_looks_low_quality(thumb_path) if thumb_path.exists() else False,
    )

    metadata_info = _build_metadata_info(metadata_path(job))
    captions_info = _build_captions_info(project_id, draft.config.captions.enabled, settings)
    beats_info = _build_beats_info(project_id, draft, settings, render_profile)
    dependencies = _build_dependency_info(project_id, draft.config.captions.enabled, settings, video_path)

    cache = _load_cache(job)
    version_info = VersionInfo(
        package_engine_version=(cache or {}).get("engine_version"),
        current_package_engine_version=METADATA_ENGINE_VERSION,
    )

    return QAInput(
        project_id=project_id, package_exists=package_exists, package_error_message=package_error_message,
        video=video_info, expected_width=expected_width, expected_height=expected_height,
        expected_fps=expected_fps, expected_duration=expected_duration, audio_level=audio_level,
        narration_enabled=draft.config.audio.narration_enabled, thumbnail=thumbnail_info,
        metadata=metadata_info, captions=captions_info, beats=beats_info,
        dependencies=dependencies, version=version_info,
    )


# -- The stage itself (section 42/43/44) -----------------------------------


def _save_qa_report(job: VideoComposeJob, report: QAReport) -> None:
    path = qa_report_path(job)
    tmp_path = path.with_suffix(".tmp.json")
    tmp_path.write_text(json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def run_final_qa(project_id: int, settings: Settings) -> QAReport:
    """Section 38: idempotent AND read-only -- running this twice with
    nothing changed produces the exact same report (same checks, same
    status, same score), and never mutates final.mp4/thumbnail.jpg/
    metadata.json/captions.ass/audio_master.wav themselves. The one file
    this function DOES write is its own report artifact
    (qa_report.json, section 43) -- internal bookkeeping, not part of the
    postable package itself.
    """
    data = build_qa_input(project_id, settings)
    started = _utcnow_iso()
    checks = evaluate_final_qa(data)
    completed = _utcnow_iso()
    report = QAReport(
        status=overall_status(checks), score=score_from_checks(checks), checks=checks,
        project_id=project_id, pipeline_version=PIPELINE_VERSION, started_at=started, completed_at=completed,
    )

    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is not None:
        _save_qa_report(job, report)
    return report


def get_qa_report(project_id: int, settings: Settings) -> QAReport | None:
    """Reads back the last-persisted report without re-running any check
    -- used by the GET endpoint/frontend polling, so simply looking at a
    project's QA status is always free.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return None
    path = qa_report_path(job)
    if not path.exists():
        return None
    try:
        return QAReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# -- API ---------------------------------------------------------------


@router.get("/projects/{project_id}/final-qa", response_model=None)
def get_project_final_qa(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    report = get_qa_report(project_id, settings)
    if report is None:
        return {"project_id": project_id, "report": None}
    return {"project_id": project_id, "report": report.model_dump()}


@router.post("/projects/{project_id}/regenerate-final-qa", response_model=None)
def regenerate_final_qa(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- re-runs every check fresh (section 49's own
    "quick QA," a few seconds, cheap enough to always just re-run rather
    than cache-check first) and persists the new report, matching every
    earlier stage's own regenerate-* precedent.
    """
    report = run_final_qa(project_id, settings)
    return {"project_id": project_id, "report": report.model_dump()}
