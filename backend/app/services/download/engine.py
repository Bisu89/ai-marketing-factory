import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.db.session import SessionLocal
from app.models.download_job import DownloadJob
from app.services.download.downloader import Downloader, DownloadCancelled, DownloadPaused
from app.services.library.organizer import VideoMetadata, organize_completed_download

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "downloading")
RESUMABLE_STATUSES = ("failed", "cancelled")

DB_WRITE_INTERVAL_SEC = 0.3


class JobControl:
    def __init__(self) -> None:
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()


class DownloadEngine:
    """Background download engine: a bounded pool of worker threads consumes
    job ids from a queue, one video download runs per worker at a time, and
    the FastAPI request/response cycle never blocks on any of it.
    """

    def __init__(self, downloader: Downloader, download_dir: Path, library_dir: Path, max_workers: int):
        self._downloader = downloader
        self._download_dir = download_dir
        self._library_dir = library_dir
        self._max_workers = max_workers

        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._controls: dict[int, JobControl] = {}
        self._last_db_write: dict[int, float] = {}
        self._workers: list[threading.Thread] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._library_dir.mkdir(parents=True, exist_ok=True)
        self._recover_pending_jobs()

        for i in range(self._max_workers):
            thread = threading.Thread(target=self._worker_loop, name=f"download-worker-{i}", daemon=True)
            thread.start()
            self._workers.append(thread)

    def shutdown(self, timeout: float = 5.0) -> None:
        for _ in self._workers:
            self._queue.put(None)
        for thread in self._workers:
            thread.join(timeout=timeout)

    # --- public control API -------------------------------------------------

    def enqueue(self, url: str, metadata: dict | None = None) -> int:
        db = SessionLocal()
        try:
            job = DownloadJob(url=url, destination_path="", status="queued")
            if metadata:
                job.platform = metadata.get("platform")
                job.video_id = metadata.get("video_id")
                job.channel_name = metadata.get("channel_name")
                job.title = metadata.get("title")
                job.original_url = metadata.get("original_url", url)
                job.thumbnail_url = metadata.get("thumbnail_url")
                job.views = metadata.get("views")
                job.likes = metadata.get("likes")
                job.duration_sec = metadata.get("duration_sec")
                job.upload_date = metadata.get("upload_date")
                job.tags_json = json.dumps(metadata.get("tags") or [])
            db.add(job)
            db.commit()
            db.refresh(job)
            job.destination_path = str(self._resolve_destination(job.id, url))
            db.commit()
            job_id = job.id
        finally:
            db.close()

        self._controls[job_id] = JobControl()
        self._queue.put(job_id)
        return job_id

    def pause(self, job_id: int) -> None:
        control = self._controls.get(job_id)
        if control is not None:
            control.pause_event.set()

    def resume(self, job_id: int) -> bool:
        with self._lock:
            db = SessionLocal()
            try:
                job = db.get(DownloadJob, job_id)
                if job is None or job.status != "paused":
                    return False
                job.status = "queued"
                db.commit()
            finally:
                db.close()

            control = self._controls.setdefault(job_id, JobControl())
            control.pause_event.clear()
            control.cancel_event.clear()
            self._queue.put(job_id)
            return True

    def retry(self, job_id: int) -> bool:
        with self._lock:
            db = SessionLocal()
            try:
                job = db.get(DownloadJob, job_id)
                if job is None or job.status not in RESUMABLE_STATUSES:
                    return False
                job.status = "queued"
                job.error_message = None
                db.commit()
            finally:
                db.close()

            control = self._controls.setdefault(job_id, JobControl())
            control.pause_event.clear()
            control.cancel_event.clear()
            self._queue.put(job_id)
            return True

    def cancel(self, job_id: int) -> bool:
        control = self._controls.get(job_id)
        if control is not None:
            control.cancel_event.set()

        with self._lock:
            db = SessionLocal()
            try:
                job = db.get(DownloadJob, job_id)
                if job is None:
                    return False
                # "downloading" jobs are left to the worker thread: it will observe
                # cancel_event on the next chunk and transition to "cancelled" itself.
                if job.status in ("queued", "paused"):
                    destination = Path(job.destination_path)
                    job.status = "cancelled"
                    db.commit()
                    destination.unlink(missing_ok=True)
                return True
            finally:
                db.close()

    # --- worker internals ----------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                self._queue.task_done()
                return
            try:
                self._run_job(job_id)
            except Exception:
                logger.exception("Unhandled error running download job %s", job_id)
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: int) -> None:
        control = self._controls.setdefault(job_id, JobControl())

        db = SessionLocal()
        try:
            job = db.get(DownloadJob, job_id)
            if job is None:
                return
            if job.status == "cancelled" or control.cancel_event.is_set():
                return

            job.status = "downloading"
            job.attempts += 1
            db.commit()

            url = job.url
            destination = Path(job.destination_path)
            video_metadata = self._extract_metadata(job)
        finally:
            db.close()

        resume_from = destination.stat().st_size if destination.exists() else 0

        def on_progress(downloaded: int, total: int | None, speed: float) -> None:
            eta = (total - downloaded) / speed if total is not None and speed > 0 else None
            progress_pct = (downloaded / total * 100) if total else None
            self._write_progress(job_id, downloaded, total, speed, eta, progress_pct)

        try:
            self._downloader.download(
                url=url,
                destination=destination,
                resume_from=resume_from,
                cancel_event=control.cancel_event,
                pause_event=control.pause_event,
                on_progress=on_progress,
            )
        except DownloadPaused:
            control.pause_event.clear()
            self._set_status(job_id, "paused")
            return
        except DownloadCancelled:
            destination.unlink(missing_ok=True)
            self._set_status(job_id, "cancelled")
            return
        except Exception as exc:
            self._set_status(job_id, "failed", error_message=str(exc))
            return

        # The downloader's own final on_progress call carries the true final byte
        # count, but _write_progress throttles DB writes -- force this one through
        # so downloaded_bytes/total_bytes never lag behind a "completed" status.
        final_size = destination.stat().st_size if destination.exists() else 0
        self._write_progress(job_id, final_size, final_size, 0.0, 0.0, 100.0, force=True)

        if video_metadata is None:
            self._set_status(job_id, "completed", progress_pct=100.0)
            return

        downloaded_at = datetime.now(timezone.utc)
        try:
            final_path = organize_completed_download(destination, self._library_dir, video_metadata, downloaded_at)
        except Exception as exc:
            logger.exception("Failed to organize completed download for job %s", job_id)
            self._set_status(job_id, "failed", error_message=f"Download OK but organizing into library failed: {exc}")
            return

        self._set_status(
            job_id,
            "completed",
            progress_pct=100.0,
            destination_path=str(final_path),
            downloaded_at=downloaded_at,
        )

    def _write_progress(
        self,
        job_id: int,
        downloaded: int,
        total: int | None,
        speed: float,
        eta: float | None,
        progress_pct: float | None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        last = self._last_db_write.get(job_id, 0.0)
        if not force and now - last < DB_WRITE_INTERVAL_SEC:
            return
        self._last_db_write[job_id] = now

        db = SessionLocal()
        try:
            job = db.get(DownloadJob, job_id)
            if job is None:
                return
            job.downloaded_bytes = downloaded
            job.total_bytes = total
            job.speed_bps = speed
            job.eta_seconds = eta
            job.progress_pct = progress_pct
            db.commit()
        finally:
            db.close()

    def _set_status(self, job_id: int, status: str, **fields) -> None:
        db = SessionLocal()
        try:
            job = db.get(DownloadJob, job_id)
            if job is None:
                return
            job.status = status
            for key, value in fields.items():
                setattr(job, key, value)
            db.commit()
        finally:
            db.close()

    def _extract_metadata(self, job: DownloadJob) -> VideoMetadata | None:
        if not (job.platform and job.video_id and job.channel_name):
            return None
        return VideoMetadata(
            platform=job.platform,
            video_id=job.video_id,
            channel_name=job.channel_name,
            title=job.title or job.video_id,
            original_url=job.original_url or job.url,
            thumbnail_url=job.thumbnail_url,
            views=job.views,
            likes=job.likes,
            duration_sec=job.duration_sec,
            upload_date=job.upload_date,
            tags=json.loads(job.tags_json or "[]"),
        )

    def _resolve_destination(self, job_id: int, url: str) -> Path:
        name = Path(urlparse(url).path).name or "download.bin"
        return self._download_dir / f"{job_id}_{name}"

    def _recover_pending_jobs(self) -> None:
        db = SessionLocal()
        try:
            pending = db.query(DownloadJob).filter(DownloadJob.status.in_(ACTIVE_STATUSES)).all()
            job_ids = [job.id for job in pending]
            for job in pending:
                if job.status == "downloading":
                    job.status = "queued"
            db.commit()
        finally:
            db.close()

        for job_id in job_ids:
            self._controls[job_id] = JobControl()
            self._queue.put(job_id)
