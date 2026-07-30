import logging
import math
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from scenedetect import SceneManager, open_video, split_video_ffmpeg
from scenedetect.detectors import ContentDetector

from app.db.session import SessionLocal
from app.models.video import Video
from app.modules.scene_cutter.models import SceneCutJob, SceneCutResult

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("queued", "analyzing", "splitting")


class SceneCutterService:
    """Background scene-cutting engine: its own queue + worker thread, fully
    independent of DownloadEngine (see app/modules/README.md) -- a change to
    download logic can never break this, and vice versa.

    Runs one job at a time: scene detection (OpenCV) and splitting (ffmpeg
    subprocess) are both CPU-bound, and this is a desktop-local tool with no
    need for the parallel-worker-pool complexity DownloadEngine has for
    network-bound downloads.
    """

    def __init__(self, library_dir: Path):
        self._library_dir = library_dir
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        (self._library_dir / "_local_files").mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(target=self._worker_loop, name="scene-cutter-worker", daemon=True)
        self._worker.start()
        self._recover_pending_jobs()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    # --- public API -----------------------------------------------------------

    def enqueue(
        self,
        video_id: int | None,
        source_path: str | None,
        threshold: float,
        min_scene_len_sec: float,
        trim_sec: float,
    ) -> int:
        db = SessionLocal()
        try:
            job = SceneCutJob(
                video_id=video_id,
                source_path=source_path,
                threshold=threshold,
                min_scene_len_sec=min_scene_len_sec,
                trim_sec=trim_sec,
                status="queued",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()

        self._queue.put(job_id)
        return job_id

    # --- worker internals -------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                self._queue.task_done()
                return
            try:
                self._run_job(job_id)
            except Exception:
                logger.exception("Unhandled error running scene-cut job %s", job_id)
                self._set_status(job_id, "failed", error_message="Internal error")
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(SceneCutJob, job_id)
            if job is None:
                return
            video_id = job.video_id
            source_path = job.source_path
            threshold = job.threshold
            min_scene_len_sec = job.min_scene_len_sec
            trim_sec = job.trim_sec
        finally:
            db.close()

        input_path, output_dir, resolve_error = self._resolve_paths(job_id, video_id, source_path)
        if resolve_error is not None:
            self._set_status(job_id, "failed", error_message=resolve_error)
            return

        self._set_status(job_id, "analyzing")

        try:
            scenes = self._detect_scenes(input_path, threshold, min_scene_len_sec, trim_sec)
        except Exception as exc:
            logger.exception("Scene detection failed for job %s", job_id)
            self._set_status(job_id, "failed", error_message=str(exc))
            return

        if not scenes:
            self._set_status(
                job_id,
                "failed",
                error_message="Không phát hiện được cảnh nào (video có thể chỉ có 1 cảnh duy nhất)",
            )
            return

        self._set_status(job_id, "splitting")

        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            split_video_ffmpeg(
                str(input_path),
                scenes,
                output_dir=str(output_dir),
                output_file_template="scene-$SCENE_NUMBER.mp4",
                show_progress=False,
            )
        except Exception as exc:
            logger.exception("Scene splitting failed for job %s", job_id)
            self._set_status(job_id, "failed", error_message=str(exc))
            return

        # Matches pyscenedetect's own $SCENE_NUMBER padding exactly (see
        # scenedetect.video_splitter.split_video_ffmpeg) so the file_path we
        # record here always matches what ffmpeg actually wrote to disk.
        padding = max(3, math.floor(math.log(len(scenes), 10)) + 1)

        db = SessionLocal()
        try:
            job = db.get(SceneCutJob, job_id)
            if job is None:
                return
            for i, (start, end) in enumerate(scenes, start=1):
                file_path = output_dir / f"scene-{i:0{padding}d}.mp4"
                db.add(
                    SceneCutResult(
                        job_id=job_id,
                        scene_number=i,
                        start_timecode=start.get_timecode(),
                        end_timecode=end.get_timecode(),
                        file_path=str(file_path),
                    )
                )
            job.status = "completed"
            job.scene_count = len(scenes)
            job.output_dir = str(output_dir)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def _resolve_paths(
        self, job_id: int, video_id: int | None, source_path: str | None
    ) -> tuple[Path | None, Path | None, str | None]:
        if video_id is not None:
            db = SessionLocal()
            try:
                video = db.get(Video, video_id)
                if video is None or not video.video_path:
                    return None, None, "Video not found or not downloaded yet"
            finally:
                db.close()
            input_path = Path(video.video_path)
            output_dir = input_path.parent / "scenes" / f"job_{job_id}"
            return input_path, output_dir, None

        input_path = Path(source_path)
        if not input_path.exists():
            return None, None, f"Không tìm thấy file: {input_path}"
        output_dir = self._library_dir / "_local_files" / f"job_{job_id}"
        return input_path, output_dir, None

    @staticmethod
    def _detect_scenes(video_path: Path, threshold: float, min_scene_len_sec: float, trim_sec: float):
        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=threshold, min_scene_len=int(min_scene_len_sec * video.frame_rate))
        )
        scene_manager.detect_scenes(video)
        scenes = scene_manager.get_scene_list()

        if trim_sec > 0:
            trimmed = []
            for start, end in scenes:
                duration_sec = (end - start).get_seconds()
                actual_trim = min(trim_sec, duration_sec / 3)
                trimmed.append((start + actual_trim, end - actual_trim))
            scenes = trimmed

        return scenes

    def _set_status(self, job_id: int, status: str, **fields) -> None:
        db = SessionLocal()
        try:
            job = db.get(SceneCutJob, job_id)
            if job is None:
                return
            job.status = status
            for key, value in fields.items():
                setattr(job, key, value)
            db.commit()
        finally:
            db.close()

    def _recover_pending_jobs(self) -> None:
        db = SessionLocal()
        try:
            pending = db.query(SceneCutJob).filter(SceneCutJob.status.in_(PENDING_STATUSES)).all()
            job_ids = [job.id for job in pending]
            for job in pending:
                job.status = "queued"
            db.commit()
        finally:
            db.close()

        for job_id in job_ids:
            self._queue.put(job_id)
