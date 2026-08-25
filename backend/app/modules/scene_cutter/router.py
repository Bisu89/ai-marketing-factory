import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import FileOperationError, NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.scene_cutter.models import SceneCutJob
from app.modules.scene_cutter.schemas import (
    PickFolderOut,
    ScenePreviewOut,
    SceneCutJobCreateIn,
    SceneCutJobOut,
    job_to_out,
    scenes_to_preview_out,
)
from app.modules.scene_cutter.service import SceneCutterService

router = APIRouter()


@router.post("/scene-jobs/pick-folder", response_model=PickFolderOut)
def pick_output_folder():
    """Opens a native OS folder-picker dialog and returns the chosen path.

    Only meaningful because this is a desktop-local app where the backend
    and the user sit on the same machine -- a plain web app has no way to
    get a real filesystem path out of a browser folder picker (the File
    System Access API deliberately never exposes one, for security). Runs
    server-side via tkinter instead, same rationale as os.startfile for
    open-folder elsewhere in this module.
    """
    if sys.platform != "win32":
        raise ValidationError("Folder picker is only supported on Windows")

    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(title="Chọn thư mục lưu cảnh đã cắt")
    finally:
        root.destroy()

    return PickFolderOut(path=selected or None)


def get_scene_cutter_service(request: Request) -> SceneCutterService:
    return request.app.state.scene_cutter_service


def _get_job_or_404(db: Session, job_id: int) -> SceneCutJob:
    job = (
        db.query(SceneCutJob)
        .options(selectinload(SceneCutJob.scenes))
        .filter(SceneCutJob.id == job_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Scene cut job", job_id)
    return job


@router.post("/scene-jobs", response_model=SceneCutJobOut, status_code=201)
def create_scene_job(
    payload: SceneCutJobCreateIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: SceneCutterService = Depends(get_scene_cutter_service),
):
    job_id = service.enqueue(
        video_id=payload.video_id,
        source_path=payload.source_path,
        threshold=payload.threshold,
        min_scene_len_sec=payload.min_scene_len_sec,
        trim_sec=payload.trim_sec,
        requested_output_dir=payload.output_dir,
    )
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


@router.post("/scene-jobs/upload", response_model=SceneCutJobOut, status_code=201)
def upload_scene_job(
    file: UploadFile = File(...),
    threshold: float = Form(60.0),
    min_scene_len_sec: float = Form(1.2),
    trim_sec: float = Form(0.0),
    output_dir: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: SceneCutterService = Depends(get_scene_cutter_service),
):
    staged_path = service.save_uploaded_file(file.filename or "upload.mp4", file.file)
    job_id = service.enqueue(
        video_id=None,
        source_path=str(staged_path),
        threshold=threshold,
        min_scene_len_sec=min_scene_len_sec,
        trim_sec=trim_sec,
        requested_output_dir=output_dir,
    )
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


# Real user follow-up (docs/features/107-scene-cutter-false-split-fix.md):
# no single threshold works for every video, and finding the right one by
# repeatedly running a real cut (waiting for ffmpeg to write files each
# time) was slow and frustrating. These two mirror create_scene_job/
# upload_scene_job's own JSON-vs-multipart split exactly, but call
# service.preview_scenes (detection only) instead of service.enqueue --
# fast, no job row, no files written, so the user can try several
# threshold values back to back before committing to a real cut.
@router.post("/scene-jobs/preview", response_model=ScenePreviewOut)
def preview_scene_job(
    payload: SceneCutJobCreateIn,
    service: SceneCutterService = Depends(get_scene_cutter_service),
):
    try:
        scenes = service.preview_scenes(
            video_id=payload.video_id,
            source_path=payload.source_path,
            threshold=payload.threshold,
            min_scene_len_sec=payload.min_scene_len_sec,
            trim_sec=payload.trim_sec,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return scenes_to_preview_out(scenes)


@router.post("/scene-jobs/preview/upload", response_model=ScenePreviewOut)
def preview_scene_job_upload(
    file: UploadFile = File(...),
    threshold: float = Form(60.0),
    min_scene_len_sec: float = Form(1.2),
    trim_sec: float = Form(0.0),
    service: SceneCutterService = Depends(get_scene_cutter_service),
):
    staged_path = service.save_uploaded_file(file.filename or "upload.mp4", file.file)
    try:
        scenes = service.preview_scenes(
            video_id=None,
            source_path=str(staged_path),
            threshold=threshold,
            min_scene_len_sec=min_scene_len_sec,
            trim_sec=trim_sec,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return scenes_to_preview_out(scenes)


@router.get("/scene-jobs", response_model=list[SceneCutJobOut])
def list_scene_jobs(
    video_id: int | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    query = db.query(SceneCutJob).options(selectinload(SceneCutJob.scenes))
    if video_id is not None:
        query = query.filter(SceneCutJob.video_id == video_id)
    jobs = query.order_by(SceneCutJob.id.desc()).all()
    return [job_to_out(job, Path(settings.library_dir)) for job in jobs]


@router.get("/scene-jobs/{job_id}", response_model=SceneCutJobOut)
def get_scene_job(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


@router.post("/scene-jobs/{job_id}/open-folder", status_code=204)
def open_scene_job_folder(job_id: int, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    if not job.output_dir:
        raise FileOperationError("Tác vụ chưa hoàn tất, chưa có thư mục kết quả")

    folder = Path(job.output_dir)
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
