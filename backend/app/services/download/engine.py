import logging
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.events import EventBus
from app.db.session import SessionLocal
from app.models.channel import Channel
from app.models.download_history import DownloadHistory
from app.models.download_task import DownloadTask
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_tag import VideoTag
from app.services.download.downloader import Downloader, DownloadCancelled, DownloadPaused
from app.services.library.organizer import VideoMetadata, organize_completed_download

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "downloading")
RESUMABLE_STATUSES = ("failed", "cancelled")
TERMINAL_HISTORY_STATUSES = ("completed", "failed", "cancelled")

DB_WRITE_INTERVAL_SEC = 0.3


class JobControl:
    def __init__(self) -> None:
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()


class DownloadEngine:
    """Background download engine: a bounded pool of worker threads consumes
    task ids from a queue, one video download runs per worker at a time, and
    the FastAPI request/response cycle never blocks on any of it.

    Each task references an existing Video row (created/deduplicated by the
    API layer via app.services.library.catalog before enqueuing) -- the engine
    itself only owns download lifecycle state, not video metadata.
    """

    def __init__(
        self,
        downloader: Downloader,
        download_dir: Path,
        library_dir: Path,
        max_workers: int,
        event_bus: EventBus | None = None,
    ):
        self._downloader = downloader
        self._download_dir = download_dir
        self._library_dir = library_dir
        self._max_workers = max_workers
        self._event_bus = event_bus

        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._controls: dict[int, JobControl] = {}
        self._last_db_write: dict[int, float] = {}
        self._workers: list[threading.Thread] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._library_dir.mkdir(parents=True, exist_ok=True)
        self._recover_pending_tasks()

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

    def enqueue(self, url: str, video_id: int) -> int:
        db = SessionLocal()
        try:
            task = DownloadTask(url=url, video_id=video_id, destination_path="", status="queued")
            db.add(task)
            db.commit()
            db.refresh(task)
            task.destination_path = str(self._resolve_destination(task.id, url))
            db.commit()
            task_id = task.id
        finally:
            db.close()

        self._controls[task_id] = JobControl()
        self._queue.put(task_id)
        return task_id

    def pause(self, task_id: int) -> None:
        control = self._controls.get(task_id)
        if control is not None:
            control.pause_event.set()

    def resume(self, task_id: int) -> bool:
        with self._lock:
            db = SessionLocal()
            try:
                task = db.get(DownloadTask, task_id)
                if task is None or task.status != "paused":
                    return False
                task.status = "queued"
                db.commit()
            finally:
                db.close()

            control = self._controls.setdefault(task_id, JobControl())
            control.pause_event.clear()
            control.cancel_event.clear()
            self._queue.put(task_id)
            return True

    def retry(self, task_id: int) -> bool:
        with self._lock:
            db = SessionLocal()
            try:
                task = db.get(DownloadTask, task_id)
                if task is None or task.status not in RESUMABLE_STATUSES:
                    return False
                task.status = "queued"
                task.error_message = None
                db.commit()
            finally:
                db.close()

            control = self._controls.setdefault(task_id, JobControl())
            control.pause_event.clear()
            control.cancel_event.clear()
            self._queue.put(task_id)
            return True

    def cancel(self, task_id: int) -> bool:
        control = self._controls.get(task_id)
        if control is not None:
            control.cancel_event.set()

        with self._lock:
            db = SessionLocal()
            try:
                task = db.get(DownloadTask, task_id)
                if task is None:
                    return False
                # "downloading" tasks are left to the worker thread: it will observe
                # cancel_event on the next chunk and transition to "cancelled" itself.
                if task.status in ("queued", "paused"):
                    destination = Path(task.destination_path)
                    task.status = "cancelled"
                    video_id = task.video_id
                    db.commit()
                    destination.unlink(missing_ok=True)
                    self._record_history(video_id, task_id, "cancelled")
                return True
            finally:
                db.close()

    # --- worker internals ----------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            task_id = self._queue.get()
            if task_id is None:
                self._queue.task_done()
                return
            try:
                self._run_task(task_id)
            except Exception:
                logger.exception("Unhandled error running download task %s", task_id)
            finally:
                self._queue.task_done()

    def _run_task(self, task_id: int) -> None:
        control = self._controls.setdefault(task_id, JobControl())

        db = SessionLocal()
        try:
            task = db.get(DownloadTask, task_id)
            if task is None:
                return
            if task.status == "cancelled" or control.cancel_event.is_set():
                return

            task.status = "downloading"
            task.attempts += 1
            db.commit()

            url = task.url
            destination = Path(task.destination_path)
            video_id = task.video_id
        finally:
            db.close()

        resume_from = destination.stat().st_size if destination.exists() else 0

        def on_progress(downloaded: int, total: int | None, speed: float) -> None:
            eta = (total - downloaded) / speed if total is not None and speed > 0 else None
            progress_pct = (downloaded / total * 100) if total else None
            self._write_progress(task_id, downloaded, total, speed, eta, progress_pct)

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
            self._set_status(task_id, "paused")
            return
        except DownloadCancelled:
            destination.unlink(missing_ok=True)
            self._set_status(task_id, "cancelled")
            self._record_history(video_id, task_id, "cancelled")
            return
        except Exception as exc:
            self._set_status(task_id, "failed", error_message=str(exc))
            self._record_history(video_id, task_id, "failed", str(exc))
            return

        # The downloader's own final on_progress call carries the true final byte
        # count, but _write_progress throttles DB writes -- force this one through
        # so downloaded_bytes/total_bytes never lag behind a "completed" status.
        final_size = destination.stat().st_size if destination.exists() else 0
        self._write_progress(task_id, final_size, final_size, 0.0, 0.0, 100.0, force=True)

        video_metadata = self._load_video_metadata(video_id)
        if video_metadata is None:
            self._set_status(task_id, "failed", error_message="associated video/channel record missing")
            self._record_history(video_id, task_id, "failed", "associated video/channel record missing")
            return

        downloaded_at = datetime.now(timezone.utc)
        try:
            final_path = organize_completed_download(destination, self._library_dir, video_metadata, downloaded_at)
        except Exception as exc:
            logger.exception("Failed to organize completed download for task %s", task_id)
            self._set_status(task_id, "failed", error_message=f"Download OK but organizing into library failed: {exc}")
            self._record_history(video_id, task_id, "failed", str(exc))
            return

        self._mark_video_downloaded(video_id, final_path, downloaded_at)
        self._set_status(task_id, "completed", progress_pct=100.0)
        self._record_history(video_id, task_id, "completed")

        # Hook point for future modules (Subtitle/Story/Caption/Voice/Affiliate/
        # Analytics generators): they subscribe to this event at their own
        # startup instead of the engine importing/calling them directly.
        if self._event_bus is not None:
            self._event_bus.publish("video.downloaded", {"video_id": video_id, "video_path": str(final_path)})

    def _write_progress(
        self,
        task_id: int,
        downloaded: int,
        total: int | None,
        speed: float,
        eta: float | None,
        progress_pct: float | None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        last = self._last_db_write.get(task_id, 0.0)
        if not force and now - last < DB_WRITE_INTERVAL_SEC:
            return
        self._last_db_write[task_id] = now

        db = SessionLocal()
        try:
            task = db.get(DownloadTask, task_id)
            if task is None:
                return
            task.downloaded_bytes = downloaded
            task.total_bytes = total
            task.speed_bps = speed
            task.eta_seconds = eta
            task.progress_pct = progress_pct
            db.commit()
        finally:
            db.close()

    def _set_status(self, task_id: int, status: str, **fields) -> None:
        db = SessionLocal()
        try:
            task = db.get(DownloadTask, task_id)
            if task is None:
                return
            task.status = status
            for key, value in fields.items():
                setattr(task, key, value)
            db.commit()
        finally:
            db.close()

    def _record_history(self, video_id: int, task_id: int, status: str, error_message: str | None = None) -> None:
        assert status in TERMINAL_HISTORY_STATUSES
        db = SessionLocal()
        try:
            db.add(DownloadHistory(video_id=video_id, task_id=task_id, status=status, error_message=error_message))
            db.commit()
        finally:
            db.close()

    def _load_video_metadata(self, video_id: int) -> VideoMetadata | None:
        db = SessionLocal()
        try:
            video = db.get(Video, video_id)
            if video is None:
                return None
            channel = db.get(Channel, video.channel_id)
            if channel is None:
                return None
            tag_names = [
                name
                for (name,) in db.query(Tag.name).join(VideoTag, VideoTag.tag_id == Tag.id).filter(
                    VideoTag.video_id == video_id
                )
            ]
            return VideoMetadata(
                platform=video.platform_name,
                video_id=video.external_id,
                channel_name=channel.name,
                title=video.title,
                original_url=video.original_url,
                thumbnail_url=video.thumbnail_url,
                views=video.views,
                likes=video.likes,
                duration_sec=video.duration_sec,
                upload_date=video.upload_date,
                tags=tag_names,
            )
        finally:
            db.close()

    def _mark_video_downloaded(self, video_id: int, final_path: Path, downloaded_at: datetime) -> None:
        db = SessionLocal()
        try:
            video = db.get(Video, video_id)
            if video is None:
                return
            video.video_path = str(final_path)
            if video.thumbnail_url:
                video.thumbnail_path = str(final_path.parent / "thumbnail.jpg")
            video.filesize_bytes = final_path.stat().st_size if final_path.exists() else None
            video.is_downloaded = True
            video.downloaded_at = downloaded_at
            db.commit()
        finally:
            db.close()

    def _resolve_destination(self, task_id: int, url: str) -> Path:
        name = Path(urlparse(url).path).name or "download.bin"
        return self._download_dir / f"{task_id}_{name}"

    def _recover_pending_tasks(self) -> None:
        db = SessionLocal()
        try:
            pending = db.query(DownloadTask).filter(DownloadTask.status.in_(ACTIVE_STATUSES)).all()
            task_ids = [task.id for task in pending]
            for task in pending:
                if task.status == "downloading":
                    task.status = "queued"
            db.commit()
        finally:
            db.close()

        for task_id in task_ids:
            self._controls[task_id] = JobControl()
            self._queue.put(task_id)
