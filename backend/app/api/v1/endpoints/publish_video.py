"""YouTube publish composition root (see docs/features/127-youtube-publishing.md).

The one place allowed to import app.modules.publishing together with
app.modules.beat (Project -> render_job_id) and app.modules.video_composer
(VideoComposeJob -> output_path) -- same composition-root shape as
app/api/v1/endpoints/produced_videos.py.

The upload itself runs on a per-job daemon thread (uploads are infrequent
and independent; no shared queue needed) -- the same lightweight pattern
app/api/v1/endpoints/batch_render.py uses for "Generate Beats". A restart
mid-upload leaves the job 'interrupted' (service.reconcile_uploads_on_startup),
never silently retried.
"""

import json
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.beat.project_service import get_project_draft
from app.modules.publishing import service, youtube_client
from app.modules.publishing.schemas import UploadRequest, UploadResponse, YouTubeUploadJobOut
from app.modules.video_composer.models import VideoComposeJob

logger = logging.getLogger(__name__)
router = APIRouter()


def _upload_out(job) -> YouTubeUploadJobOut:
    out = YouTubeUploadJobOut.model_validate(job)
    out.channel_title = job.channel.title if job.channel is not None else None
    out.watch_url = job.watch_url
    return out


def _resolve_video_files(project_id: int, db: Session) -> tuple[int, Path, dict]:
    """(render_job_id, final_mp4_path, package_metadata) for a project whose
    Factory render has completed. Raises ValidationError otherwise.
    """
    draft = get_project_draft(project_id)
    if draft.render_job_id is None:
        raise ValidationError("This project has not been rendered yet.")
    job = db.get(VideoComposeJob, draft.render_job_id)
    if job is None or job.status != "completed" or not job.output_path:
        raise ValidationError("This project's render is not complete.")
    video_path = Path(job.output_path)
    if not video_path.exists():
        raise ValidationError(f"The rendered video file is missing: {video_path}")

    meta_path = video_path.with_name("metadata.json")
    metadata: dict = {}
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            metadata = {}
    return job.id, video_path, metadata


def _run_upload(job_id: int, channel_pk: int, video_path: str, metadata: dict, privacy: str, settings: Settings) -> None:
    service.set_upload_fields(job_id, status="uploading", error_message=None)
    try:
        access_token = service.get_fresh_access_token(channel_pk, settings)
        title = (metadata.get("title") or Path(video_path).stem)[:100]
        description = metadata.get("description") or ""
        tags = metadata.get("hashtags") or []

        video_id = youtube_client.upload_video(
            access_token, Path(video_path),
            title=title, description=description, tags=tags, privacy_status=privacy,
        )
        service.set_upload_fields(job_id, youtube_video_id=video_id)

        thumb = Path(video_path).with_name("thumbnail.jpg")
        if thumb.exists():
            try:
                youtube_client.set_thumbnail(access_token, video_id, thumb)
            except Exception:  # noqa: BLE001 -- thumbnail is best-effort, video is already up
                logger.warning("Thumbnail set failed for upload job %s (video %s)", job_id, video_id, exc_info=True)

        service.set_upload_fields(job_id, status="completed", error_message=None)
        logger.info("YouTube upload job %s completed: video %s", job_id, video_id)
    except Exception as exc:  # noqa: BLE001 -- every failure mode lands on the job row, never crashes the thread
        logger.exception("YouTube upload job %s failed", job_id)
        service.set_upload_fields(job_id, status="failed", error_message=str(exc)[:500])


def _start_upload_thread(job_id: int, channel_pk: int, video_path: str, metadata: dict, privacy: str, settings: Settings) -> None:
    threading.Thread(
        target=_run_upload, args=(job_id, channel_pk, video_path, metadata, privacy, settings), daemon=True
    ).start()


@router.post("/publishing/youtube/upload", response_model=UploadResponse, status_code=201)
def upload_to_youtube(
    payload: UploadRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> UploadResponse:
    channel = service.get_channel(payload.channel_id)  # 404s if unknown
    if not channel.enabled:
        raise ValidationError("This channel is disabled. Re-enable it in Publishing first.")

    existing = service.existing_upload(payload.channel_id, payload.project_id)
    if existing is not None:
        raise ValidationError(
            f'This project was already uploaded to "{channel.title}" '
            f'(status: {existing.status}). Retry that job if it failed.'
        )

    render_job_id, video_path, metadata = _resolve_video_files(payload.project_id, db)

    job_id = service.create_upload_job(
        channel_pk=payload.channel_id, project_id=payload.project_id, render_job_id=render_job_id,
        privacy=payload.privacy, title=(metadata.get("title") or "")[:100],
        description=metadata.get("description") or "", video_path=str(video_path),
    )
    _start_upload_thread(job_id, payload.channel_id, str(video_path), metadata, payload.privacy, settings)
    return UploadResponse(upload_job_id=job_id, status="pending")


@router.post("/publishing/youtube/uploads/{job_id}/retry", response_model=YouTubeUploadJobOut)
def retry_upload(
    job_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> YouTubeUploadJobOut:
    job = service.get_upload(job_id)
    if job.status in ("pending", "uploading"):
        raise ValidationError("This upload is still in progress.")
    if job.status == "completed":
        raise ValidationError("This video was already uploaded successfully.")

    render_job_id, video_path, metadata = _resolve_video_files(job.project_id, db)
    service.set_upload_fields(job_id, status="pending", error_message=None, render_job_id=render_job_id)
    _start_upload_thread(job_id, job.channel_pk, str(video_path), metadata, job.requested_privacy, settings)
    return _upload_out(service.get_upload(job_id))
