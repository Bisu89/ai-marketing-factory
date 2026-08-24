import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.modules.video_composer.models import COARSE_STATUS, RENDER_PHASE, VideoComposeJob


def _to_media_url(file_path: str, library_dir: Path) -> str | None:
    try:
        rel = Path(file_path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


def _read_render_metadata(output_path: str | None) -> dict:
    """render_metadata.json (see VideoComposerService._write_render_metadata)
    is written as a sidecar file, not a DB column -- reading it back here is
    what actually surfaces render time/duration/resolution to API clients.
    Missing/corrupt/pre-Task-34 (no width/height/fps/clip_count yet)
    metadata all degrade to an empty dict rather than raising, so a job
    from before this field existed just reports those fields as null
    instead of failing to serialize.
    """
    if not output_path:
        return {}
    metadata_path = Path(output_path).with_name("render_metadata.json")
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_render_report(library_dir: Path, job_id: int) -> dict:
    """`.render/job_<id>/report.json` (see
    VideoComposerService._write_render_report, Task 10 -- see
    docs/features/37-e2e-pipeline-hardening.md) carries the fields
    render_metadata.json doesn't: external API accounting and per-phase
    timing, for both completed AND failed jobs. Same "missing/corrupt
    degrades to empty dict" tolerance as _read_render_metadata -- a job
    from before this report existed just reports these fields as null.
    """
    report_path = library_dir / ".render" / f"job_{job_id}" / "report.json"
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class VideoComposeJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    voice: str
    music_volume: float
    narration_volume: float
    music_ducking_ratio: float
    fade_in_sec: float
    fade_out_sec: float
    caption_preset: str
    transition_duration: float
    burn_subtitles: bool
    requested_output_dir: str | None
    # Task 26 -- see docs/features/52-final-composer.md. True only for a
    # Factory-driven "Final Composer" job (narration_mode="precomposed");
    # every plain upload-based Video Composer job is always False.
    watermark_enabled: bool = False
    status: str
    # Task 11 coarse status/phase (see app.modules.video_composer.models.
    # COARSE_STATUS/RENDER_PHASE) -- `status` above remains the detailed,
    # persisted source of truth; these two are a derived, API-facing view:
    # job_status is always exactly one of QUEUED/RUNNING/COMPLETED/FAILED/
    # CANCELLED, phase is one of the 7-value RENDER_PHASE vocabulary (None
    # outside RENDER_BEATS..VALIDATE_OUTPUT, e.g. while QUEUED or once
    # terminal -- PREFLIGHT itself never appears here, see
    # docs/features/38-render-job-hardening.md).
    job_status: str = "QUEUED"
    phase: str | None = None
    # Live progress during RENDER_BEATS only -- both null otherwise, and
    # only ever real, known counts (never a guessed percentage).
    progress_current: int | None = None
    progress_total: int | None = None
    previous_job_id: int | None = None
    # Chinese Drama -> Vietnamese Shorts. None for every other job.
    source_language: str | None = None
    hook_text: str | None = None
    estimated_cost_usd: float | None = None
    clip_count: int
    output_path: str | None
    output_media_url: str | None = None
    # From render_metadata.json (see _read_render_metadata above) -- null
    # until the job completes, or if that sidecar is missing/unreadable.
    render_duration_sec: float | None = None
    render_width: int | None = None
    render_height: int | None = None
    render_fps: float | None = None
    render_time_seconds: float | None = None
    output_size_mb: float | None = None
    # From .render/job_<id>/report.json (Task 10 -- see
    # _read_render_report above). Null until the job completes/fails, or
    # for a job rendered before this report existed.
    external_api_calls: int | None = None
    external_api_cost_estimate: float | None = None
    error_code: str | None = None
    failed_phase: str | None = None
    timing: dict | None = None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


def job_to_out(job: VideoComposeJob, library_dir: Path) -> VideoComposeJobOut:
    base = VideoComposeJobOut.model_validate(job)
    output_media_url = _to_media_url(job.output_path, library_dir) if job.output_path else None
    metadata = _read_render_metadata(job.output_path)
    report = _read_render_report(library_dir, job.id)
    return base.model_copy(
        update={
            "output_media_url": output_media_url,
            "render_duration_sec": metadata.get("duration"),
            "render_width": metadata.get("width"),
            "render_height": metadata.get("height"),
            "render_fps": metadata.get("fps"),
            "render_time_seconds": metadata.get("render_time_seconds"),
            "output_size_mb": metadata.get("output_size_mb"),
            "external_api_calls": report.get("external_api_calls"),
            "external_api_cost_estimate": report.get("external_api_cost_estimate"),
            "error_code": report.get("error_code"),
            "failed_phase": report.get("failed_phase"),
            "timing": report.get("timing"),
            "job_status": COARSE_STATUS.get(job.status, "QUEUED"),
            "phase": RENDER_PHASE.get(job.status),
            "progress_current": job.render_progress_current,
            "progress_total": job.render_progress_total,
            "previous_job_id": job.previous_job_id,
        }
    )


class PickFolderOut(BaseModel):
    path: str | None
