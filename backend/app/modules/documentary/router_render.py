"""Render jobs, preview/final video, quality report. Mounted by router.py."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.modules.documentary.render import RenderService, tools
from app.modules.documentary.render_plan import RenderParams
from app.modules.documentary.schemas import ReviewOut
from app.modules.documentary.service import DocumentaryService

router = APIRouter()


class RenderIn(BaseModel):
    kind: Literal["preview", "final"] = "preview"
    scale: float | None = Field(default=None, ge=0.2, le=1.0)
    seconds: float | None = Field(default=None, gt=0, le=3600)
    burn_subtitles: bool = True
    grayscale: bool = True
    normalize_audio: bool = True


class RenderJobOut(BaseModel):
    id: int
    kind: str
    status: str
    phase: str | None
    progress: float
    params: dict
    error: str | None
    duration_sec: float | None
    qc: dict | None
    has_output: bool
    created_at: str
    finished_at: str | None
    reused: bool = False


def _out(job, reused: bool = False) -> RenderJobOut:
    return RenderJobOut(
        id=job.id, kind=job.kind, status=job.status, phase=job.phase, progress=job.progress, params=job.params, error=job.error,
        duration_sec=job.duration_sec, qc=job.qc, has_output=bool(job.output_path and Path(job.output_path).is_file()),
        created_at=job.created_at.isoformat(), finished_at=job.finished_at.isoformat() if job.finished_at else None, reused=reused,
    )


def _svc(db: Session, settings: Settings) -> tuple[DocumentaryService, RenderService]:
    root = Path(settings.library_dir)
    return DocumentaryService(db, library_root=root), RenderService(db, root)


@router.get("/render-tools")
def render_tools():
    return {k: bool(v) for k, v in tools().items()}


@router.get("/projects/{project_id}/render/preflight", response_model=ReviewOut)
def render_preflight(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    p = svc.get(project_id)
    issues = render.preflight(project_id)
    if "narration_timing" not in svc.valid_gates(p):
        from app.modules.documentary.schemas import ReviewIssue

        issues = [ReviewIssue(code="gate4", message="Cần duyệt cổng 4 (narration & timing) trước khi render.")] + issues
    return ReviewOut(ok=not issues, issues=issues)


@router.post("/projects/{project_id}/render", response_model=RenderJobOut, status_code=202)
def start_render(project_id: int, body: RenderIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, _ = _svc(db, settings)
    scale = body.scale if body.scale is not None else (1.0 if body.kind == "final" else 0.5)
    params = RenderParams(
        kind=body.kind, scale=scale, seconds=body.seconds, burn_subtitles=body.burn_subtitles,
        grayscale=body.grayscale, normalize_audio=body.normalize_audio,
    )
    job, reused = svc.start_render(project_id, params)
    return _out(job, reused)


@router.get("/projects/{project_id}/render/jobs", response_model=list[RenderJobOut])
def list_jobs(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    svc.get(project_id)
    return [_out(j) for j in render.list(project_id)]


@router.get("/projects/{project_id}/render/jobs/{job_id}", response_model=RenderJobOut)
def get_job(project_id: int, job_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    svc.get(project_id)
    return _out(render.get(project_id, job_id))


@router.post("/projects/{project_id}/render/jobs/{job_id}/cancel", response_model=RenderJobOut)
def cancel_job(project_id: int, job_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    svc.get(project_id)
    return _out(render.cancel(project_id, job_id))


@router.get("/projects/{project_id}/render/jobs/{job_id}/log")
def job_log(project_id: int, job_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    svc.get(project_id)
    return Response(content=render.log_tail(render.get(project_id, job_id)), media_type="text/plain; charset=utf-8")


@router.get("/projects/{project_id}/render/review", response_model=ReviewOut)
def render_review(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    svc, render = _svc(db, settings)
    svc.get(project_id)
    return render.final_review(project_id)


_CHUNK = 1024 * 512


@router.get("/projects/{project_id}/render/jobs/{job_id}/video")
def job_video(project_id: int, job_id: int, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """MP4 with HTTP Range support (needed for seeking in the browser player)."""
    svc, render = _svc(db, settings)
    svc.get(project_id)
    job = render.get(project_id, job_id)
    if not job.output_path or not Path(job.output_path).is_file():
        raise NotFoundError("render output", job_id)
    path = Path(job.output_path)
    size = path.stat().st_size
    start, end = 0, size - 1
    status = 200
    rng = request.headers.get("range", "")
    if rng.startswith("bytes="):
        a, _, b = rng[6:].partition("-")
        try:
            start = int(a) if a else max(0, size - int(b))
            end = int(b) if (a and b) else size - 1
        except ValueError:
            start, end = 0, size - 1
        if start > end or start >= size:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        end = min(end, size - 1)
        status = 206

    def chunks():
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                data = f.read(min(_CHUNK, left))
                if not data:
                    break
                left -= len(data)
                yield data

    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(chunks(), status_code=status, media_type="video/mp4", headers=headers)
