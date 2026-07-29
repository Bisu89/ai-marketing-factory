from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_download_engine
from app.models.download_job import DownloadJob
from app.schemas.download import DownloadJobOut, EnqueueRequest
from app.services.download.engine import DownloadEngine

router = APIRouter()


def _get_job_or_404(db: Session, job_id: int) -> DownloadJob:
    job = db.get(DownloadJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job


@router.post("/downloads", response_model=DownloadJobOut, status_code=201)
def create_download(
    payload: EnqueueRequest,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    job_id = engine.enqueue(str(payload.url))
    return _get_job_or_404(db, job_id)


@router.get("/downloads", response_model=list[DownloadJobOut])
def list_downloads(db: Session = Depends(get_db)):
    return db.query(DownloadJob).order_by(DownloadJob.id).all()


@router.get("/downloads/{job_id}", response_model=DownloadJobOut)
def get_download(job_id: int, db: Session = Depends(get_db)):
    return _get_job_or_404(db, job_id)


@router.post("/downloads/{job_id}/pause", response_model=DownloadJobOut)
def pause_download(
    job_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_job_or_404(db, job_id)
    engine.pause(job_id)
    db.expire_all()
    return _get_job_or_404(db, job_id)


@router.post("/downloads/{job_id}/resume", response_model=DownloadJobOut)
def resume_download(
    job_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_job_or_404(db, job_id)
    if not engine.resume(job_id):
        raise HTTPException(status_code=409, detail="Job is not paused")
    db.expire_all()
    return _get_job_or_404(db, job_id)


@router.post("/downloads/{job_id}/retry", response_model=DownloadJobOut)
def retry_download(
    job_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_job_or_404(db, job_id)
    if not engine.retry(job_id):
        raise HTTPException(status_code=409, detail="Job is not failed/cancelled")
    db.expire_all()
    return _get_job_or_404(db, job_id)


@router.post("/downloads/{job_id}/cancel", response_model=DownloadJobOut)
def cancel_download(
    job_id: int,
    db: Session = Depends(get_db),
    engine: DownloadEngine = Depends(get_download_engine),
):
    _get_job_or_404(db, job_id)
    engine.cancel(job_id)
    db.expire_all()
    return _get_job_or_404(db, job_id)
