from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_download_engine
from app.models.download_task import DownloadTask
from app.schemas.download import DownloadTaskOut, EnqueueRequest
from app.schemas.video import VideoOut
from app.services.download.engine import ACTIVE_STATUSES, DownloadEngine
from app.services.library import catalog

router = APIRouter()


def _get_task_or_404(db: Session, task_id: int) -> DownloadTask:
    task = db.get(DownloadTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Download task not found")
    return task


@router.post("/downloads", response_model=DownloadTaskOut, status_code=201)
def create_download(
    payload: EnqueueRequest,
    response: Response,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    meta = payload.metadata
    video = catalog.find_video(db, meta.platform, meta.video_id)

    if video is not None and video.is_downloaded:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Video already downloaded",
                "video": VideoOut.model_validate(video).model_dump(mode="json"),
            },
        )

    if video is not None:
        active_task = (
            db.query(DownloadTask)
            .filter(DownloadTask.video_id == video.id)
            .filter(DownloadTask.status.in_(ACTIVE_STATUSES + ("paused",)))
            .order_by(DownloadTask.id.desc())
            .first()
        )
        if active_task is not None:
            response.status_code = 200
            return active_task

    if video is None:
        video = catalog.create_video(
            db,
            catalog.VideoMetadataIn(
                platform=meta.platform,
                external_id=meta.video_id,
                channel_name=meta.channel_name,
                title=meta.title,
                original_url=meta.original_url or str(payload.url),
                thumbnail_url=meta.thumbnail_url,
                views=meta.views,
                likes=meta.likes,
                duration_sec=meta.duration_sec,
                upload_date=meta.upload_date,
                # meta.tags intentionally not wired yet -- proper Tag/VideoTag
                # persistence lands in Sprint V8 Milestone 2 (Backend APIs).
            ),
        )

    if meta.playlist:
        catalog.link_playlist(
            db,
            video,
            meta.platform,
            catalog.PlaylistMetadataIn(external_id=meta.playlist.external_id, title=meta.playlist.title),
        )

    task_id = engine.enqueue(str(payload.url), video_id=video.id)
    return _get_task_or_404(db, task_id)


@router.get("/downloads", response_model=list[DownloadTaskOut])
def list_downloads(db: Session = Depends(get_db)):
    return db.query(DownloadTask).order_by(DownloadTask.id).all()


@router.get("/downloads/{task_id}", response_model=DownloadTaskOut)
def get_download(task_id: int, db: Session = Depends(get_db)):
    return _get_task_or_404(db, task_id)


@router.post("/downloads/{task_id}/pause", response_model=DownloadTaskOut)
def pause_download(
    task_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_task_or_404(db, task_id)
    engine.pause(task_id)
    db.expire_all()
    return _get_task_or_404(db, task_id)


@router.post("/downloads/{task_id}/resume", response_model=DownloadTaskOut)
def resume_download(
    task_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_task_or_404(db, task_id)
    if not engine.resume(task_id):
        raise HTTPException(status_code=409, detail="Task is not paused")
    db.expire_all()
    return _get_task_or_404(db, task_id)


@router.post("/downloads/{task_id}/retry", response_model=DownloadTaskOut)
def retry_download(
    task_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_task_or_404(db, task_id)
    if not engine.retry(task_id):
        raise HTTPException(status_code=409, detail="Task is not failed/cancelled")
    db.expire_all()
    return _get_task_or_404(db, task_id)


@router.post("/downloads/{task_id}/cancel", response_model=DownloadTaskOut)
def cancel_download(
    task_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_task_or_404(db, task_id)
    engine.cancel(task_id)
    db.expire_all()
    return _get_task_or_404(db, task_id)
