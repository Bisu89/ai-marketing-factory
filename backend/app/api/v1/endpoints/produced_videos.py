"""Read-only browse of every finished Factory / Video Composer render --
the "manage my produced videos" screen this app never had. The Dashboard
only ever showed a short "Recent Videos" strip and Video Factory is
strictly per-project, so there was no one place to see, filter and play
back everything that has been produced.

Composition root (same shape as dashboard.py): reads app.modules.video_composer
(VideoComposeJob) and app.modules.beat (Project) -- neither imports the
other -- and joins them here.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.beat.models import Project
from app.modules.documentary.models import DocumentaryProject, DocumentaryRenderJob
from app.modules.documentary.render import ensure_thumbnail
from app.modules.video_composer.models import COARSE_STATUS, VideoComposeJob
from app.modules.video_composer.schemas import job_to_out

router = APIRouter()


class ProducedVideoOut(BaseModel):
    render_job_id: int
    job_status: str  # COMPLETED / FAILED / RUNNING / QUEUED / CANCELLED
    title: str
    description: str | None = None
    hashtags: list[str] = []
    project_id: int | None = None
    project_name: str | None = None
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    output_size_mb: float | None = None
    render_time_seconds: float | None = None
    output_path: str | None = None
    output_media_url: str | None = None
    thumbnail_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    # "factory" = Video Factory / Composer render; "documentary" = a final render of a documentary
    # project. render_job_id is the id in THAT source's own table, so pair it with `source`.
    source: str = "factory"
    documentary_project_id: int | None = None


class ProducedVideoListOut(BaseModel):
    total: int
    items: list[ProducedVideoOut]


def _package_metadata(output_path: str | None) -> dict:
    """The Packaging stage's own `metadata.json` sidecar (title/description/
    hashtags -- distinct from `render_metadata.json`'s resolution/timing,
    which job_to_out already surfaces). Same "missing/corrupt -> {}" tolerance
    every other sidecar reader in this codebase uses."""
    if not output_path:
        return {}
    path = Path(output_path).with_name("metadata.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _thumbnail_url(output_media_url: str | None) -> str | None:
    """thumbnail.jpg always sits next to the final video (see the Packaging
    stage), so the media URL is just the video's URL with the filename
    swapped -- no second path-to-URL resolver needed."""
    if not output_media_url or "/" not in output_media_url:
        return None
    return output_media_url.rsplit("/", 1)[0] + "/thumbnail.jpg"


_DOC_STATUS = {"succeeded": "COMPLETED", "failed": "FAILED", "queued": "QUEUED", "running": "RUNNING", "cancelled": "CANCELLED"}


def _documentary_rows(db: Session, library_dir: Path, status: str) -> list[ProducedVideoOut]:
    """Final renders of documentary projects. Only the newest successful final per project is
    listed (older ones were superseded); previews are never listed."""
    from app.api.v1.endpoints.documentary_media import media_url  # local helper, see below

    titles = {p.id: p.title for p in db.query(DocumentaryProject).all()}
    finals = db.query(DocumentaryRenderJob).filter(DocumentaryRenderJob.kind == "final").order_by(DocumentaryRenderJob.id.desc()).all()
    seen_ok: set[int] = set()
    rows: list[ProducedVideoOut] = []
    for job in finals:
        coarse = _DOC_STATUS.get(job.status, "QUEUED")
        if job.status == "succeeded":
            if job.project_id in seen_ok:
                continue
            seen_ok.add(job.project_id)
        if status == "COMPLETED" and coarse != "COMPLETED":
            continue
        if status == "FAILED" and coarse != "FAILED":
            continue
        out = Path(job.output_path) if job.output_path else None
        has_file = bool(out and out.is_file())
        qc = job.qc or {}
        thumb = ensure_thumbnail(out) if (has_file and job.status == "succeeded") else None
        url = media_url(out, library_dir) if has_file else None
        rows.append(ProducedVideoOut(
            render_job_id=job.id, job_status=coarse, title=titles.get(job.project_id, f"Phim tài liệu #{job.project_id}"),
            description=None, hashtags=[], project_id=None, project_name=None,
            duration_sec=job.duration_sec, width=qc.get("width"), height=qc.get("height"),
            output_size_mb=round(out.stat().st_size / (1024 * 1024), 2) if has_file else None,
            render_time_seconds=(job.finished_at - job.created_at).total_seconds() if job.finished_at else None,
            output_path=str(out.resolve()) if has_file else job.output_path,
            output_media_url=url, thumbnail_url=media_url(thumb, library_dir) if thumb else None,
            created_at=job.created_at, completed_at=job.finished_at, source="documentary", documentary_project_id=job.project_id,
        ))
    return rows


@router.get("/produced-videos", response_model=ProducedVideoListOut)
def list_produced_videos(
    status: str = "COMPLETED",
    q: str | None = None,
    limit: int = 48,
    offset: int = 0,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProducedVideoListOut:
    library_dir = Path(settings.library_dir)
    status = status.upper() if status.upper() in ("COMPLETED", "FAILED", "ALL") else "COMPLETED"
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    jobs = db.query(VideoComposeJob).order_by(VideoComposeJob.id.desc()).all()

    project_by_job = {p.render_job_id: p for p in db.query(Project).all() if p.render_job_id is not None}

    rows: list[ProducedVideoOut] = []
    for job in jobs:
        coarse = COARSE_STATUS.get(job.status, "QUEUED")
        if status == "COMPLETED" and coarse != "COMPLETED":
            continue
        if status == "FAILED" and coarse != "FAILED":
            continue

        project = project_by_job.get(job.id)

        meta = _package_metadata(job.output_path)
        out = job_to_out(job, library_dir)
        title = (project.name if project else None) or meta.get("title") or job.title

        rows.append(ProducedVideoOut(
            render_job_id=job.id,
            job_status=coarse,
            title=title,
            description=meta.get("description"),
            hashtags=meta.get("hashtags") or [],
            project_id=project.id if project else None,
            project_name=project.name if project else None,
            duration_sec=out.render_duration_sec,
            width=out.render_width,
            height=out.render_height,
            output_size_mb=out.output_size_mb,
            render_time_seconds=out.render_time_seconds,
            output_path=job.output_path,
            output_media_url=out.output_media_url,
            thumbnail_url=_thumbnail_url(out.output_media_url),
            created_at=job.created_at,
            completed_at=job.completed_at,
        ))

    rows.extend(_documentary_rows(db, library_dir, status))
    rows.sort(key=lambda r: r.created_at, reverse=True)

    filtered = [
        row for row in rows
        if not q or q.strip().lower() in f"{row.title} {row.description or ''}".lower()
    ]

    return ProducedVideoListOut(
        total=len(filtered),
        items=filtered[offset:offset + limit],
    )


@router.post("/produced-videos/{render_job_id}/open-folder", status_code=204)
def open_produced_video_folder(
    render_job_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Reveal the finished video's output folder in the OS file manager --
    same server-resolved-path, desktop-only pattern as
    videos.open_folder / downloads.open-folder (never opens a client-supplied
    path). No-op-safe: a job with no output yet is a 400, not a crash."""
    job = db.get(VideoComposeJob, render_job_id)
    if job is None:
        raise NotFoundError("VideoComposeJob", render_job_id)
    if not job.output_path:
        raise ValidationError("This video has no rendered output to open.")
    folder = Path(job.output_path).resolve().parent
    if not folder.is_dir():
        raise ValidationError(f"Output folder no longer exists: {folder}")
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606 -- server-resolved from DB, never client input
    elif sys.platform == "darwin":
        os.system(f'open "{folder}"')  # noqa: S605
    else:
        os.system(f'xdg-open "{folder}"')  # noqa: S605


@router.post("/produced-videos/documentary/{job_id}/open-folder", status_code=204)
def open_documentary_video_folder(job_id: int, db: Session = Depends(get_db)) -> None:
    """Same server-resolved-path pattern as open_produced_video_folder, for a documentary render."""
    job = db.get(DocumentaryRenderJob, job_id)
    if job is None or job.kind != "final":
        raise NotFoundError("DocumentaryRenderJob", job_id)
    if not job.output_path:
        raise ValidationError("This video has no rendered output to open.")
    folder = Path(job.output_path).resolve().parent
    if not folder.is_dir():
        raise ValidationError(f"Output folder no longer exists: {folder}")
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606 -- server-resolved from DB, never client input
    elif sys.platform == "darwin":
        os.system(f'open "{folder}"')  # noqa: S605
    else:
        os.system(f'xdg-open "{folder}"')  # noqa: S605
