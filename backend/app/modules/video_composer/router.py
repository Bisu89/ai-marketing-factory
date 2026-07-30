import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import FileOperationError, NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.schemas import VideoComposeJobOut, job_to_out
from app.modules.video_composer.service import VideoComposerService

router = APIRouter()


def get_video_composer_service(request: Request) -> VideoComposerService:
    return request.app.state.video_composer_service


def _get_job_or_404(db: Session, job_id: int) -> VideoComposeJob:
    job = (
        db.query(VideoComposeJob)
        .options(selectinload(VideoComposeJob.clips))
        .filter(VideoComposeJob.id == job_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Video compose job", job_id)
    return job


@router.post("/video-compose-jobs", response_model=VideoComposeJobOut, status_code=201)
def create_video_compose_job(
    title: str = Form(...),
    script: str = Form(...),
    voice: str = Form("es-ES-AlvaroNeural"),
    music_volume: float = Form(0.15),
    transition_duration: float = Form(0.5),
    burn_subtitles: bool = Form(True),
    files: list[UploadFile] = File(...),
    music: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
):
    if not files:
        raise ValidationError("Cần ít nhất 1 video để ghép")
    if not script.strip():
        raise ValidationError("Kịch bản không được để trống")

    job_id = service.create_job(
        title=title,
        script_text=script,
        voice=voice,
        music_volume=music_volume,
        transition_duration=transition_duration,
        burn_subtitles=burn_subtitles,
    )

    # Order matters here: `files` arrives in the exact order the frontend
    # appended them to the FormData, which is the user's chosen merge order
    # after drag/reorder -- position is derived purely from array index.
    service.save_input_clips(job_id, [(f.filename or "clip.mp4", f.file) for f in files])
    if music is not None:
        service.save_music(job_id, music.filename or "music.mp3", music.file)

    service.enqueue(job_id)
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


@router.get("/video-compose-jobs", response_model=list[VideoComposeJobOut])
def list_video_compose_jobs(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    jobs = (
        db.query(VideoComposeJob)
        .options(selectinload(VideoComposeJob.clips))
        .order_by(VideoComposeJob.id.desc())
        .all()
    )
    return [job_to_out(job, Path(settings.library_dir)) for job in jobs]


@router.get("/video-compose-jobs/{job_id}", response_model=VideoComposeJobOut)
def get_video_compose_job(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


@router.post("/video-compose-jobs/{job_id}/open-folder", status_code=204)
def open_video_compose_job_folder(job_id: int, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    if not job.output_path:
        raise FileOperationError("Tác vụ chưa hoàn tất, chưa có video kết quả")

    folder = Path(job.output_path).parent
    if not folder.exists():
        raise FileOperationError(f"Không tìm thấy thư mục: {folder}")

    try:
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 -- path is server-controlled (from DB), not client input
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except OSError as exc:
        raise FileOperationError(f"Could not open folder {folder}: {exc}") from exc
