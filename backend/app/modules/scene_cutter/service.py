import logging
import queue
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from scenedetect import SceneManager, open_video, split_video_ffmpeg
from scenedetect.detectors import ContentDetector

from app.db.session import SessionLocal
from app.models.video import Video
from app.modules.scene_cutter.models import SceneCutJob, SceneCutResult

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("queued", "analyzing", "splitting")

# Real user report: a single continuous scene came back cut into 3. This
# is the same "guaranteed, not dependent on a single tunable being
# perfectly right for a given video" merge already used twice elsewhere
# in this app (app.api.v1.endpoints.beat_generate.py's _merge_short_beats,
# app.modules.caption.ass_writer.py's own line-wrap budget) -- a spurious
# scene boundary (a whip-pan, a flash, motion blur, a brief lighting
# change) tends to produce an abnormally short scene either side of it,
# so merging anything under this floor into its predecessor catches a
# false split PySceneDetect's own ContentDetector(threshold=...,
# min_scene_len=...) missed, without having to guess the one "correct"
# threshold for every video.
_MIN_SCENE_DURATION_FOR_MERGE_SEC = 1.0


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
        (self._library_dir / "_uploads").mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(target=self._worker_loop, name="scene-cutter-worker", daemon=True)
        self._worker.start()
        self._recover_pending_jobs()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    # --- public API -----------------------------------------------------------

    def save_uploaded_file(self, filename: str, file_obj: BinaryIO) -> Path:
        """Stages an uploaded video under library_dir/_uploads/ with a random
        name (avoids collisions/overwrites between uploads, and sidesteps
        having to sanitize a client-supplied filename for the filesystem).
        Kept inside library_dir so it -- and, via source_path, its scenes --
        stay reachable through the /media static mount.
        """
        suffix = Path(filename).suffix or ".mp4"
        destination = self._library_dir / "_uploads" / f"{uuid.uuid4().hex}{suffix}"
        with open(destination, "wb") as out:
            shutil.copyfileobj(file_obj, out)
        return destination

    def enqueue(
        self,
        video_id: int | None,
        source_path: str | None,
        threshold: float,
        min_scene_len_sec: float,
        trim_sec: float,
        requested_output_dir: str | None = None,
    ) -> int:
        db = SessionLocal()
        try:
            job = SceneCutJob(
                video_id=video_id,
                source_path=source_path,
                threshold=threshold,
                min_scene_len_sec=min_scene_len_sec,
                trim_sec=trim_sec,
                requested_output_dir=requested_output_dir,
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
            requested_output_dir = job.requested_output_dir
        finally:
            db.close()

        input_path, output_dir, resolve_error = self._resolve_paths(
            job_id, video_id, source_path, requested_output_dir
        )
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

        # Random filenames (not scene-001.mp4, scene-002.mp4, ...) -- the
        # scene's position/order is already captured in scene_number and the
        # start/end timecodes on SceneCutResult, so the filename itself
        # doesn't need to encode it. Generated up front so the exact same
        # names used by the custom formatter below are also what gets
        # written to SceneCutResult.file_path -- no guessing/reverse-
        # engineering ffmpeg's own naming scheme required.
        scene_filenames = [f"{uuid.uuid4().hex}.mp4" for _ in scenes]

        def _formatter(_video_metadata, scene_metadata) -> str:
            return scene_filenames[scene_metadata.index]

        try:
            split_video_ffmpeg(
                str(input_path),
                scenes,
                output_dir=str(output_dir),
                formatter=_formatter,
                show_progress=False,
            )
        except Exception as exc:
            logger.exception("Scene splitting failed for job %s", job_id)
            self._set_status(job_id, "failed", error_message=str(exc))
            return

        db = SessionLocal()
        try:
            job = db.get(SceneCutJob, job_id)
            if job is None:
                return
            for i, (start, end) in enumerate(scenes, start=1):
                file_path = output_dir / scene_filenames[i - 1]
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

    def _resolve_input_path(
        self, video_id: int | None, source_path: str | None
    ) -> tuple[Path | None, str | None]:
        """Just the input-file half of _resolve_paths below -- split out so
        preview_scenes (no job, no output_dir, nothing written to disk) can
        share it without needing a job_id to build a default_output_dir it
        will never use.
        """
        if video_id is not None:
            db = SessionLocal()
            try:
                video = db.get(Video, video_id)
                if video is None or not video.video_path:
                    return None, "Video not found or not downloaded yet"
            finally:
                db.close()
            return Path(video.video_path), None

        input_path = Path(source_path)
        if not input_path.exists():
            return None, f"Không tìm thấy file: {input_path}"
        return input_path, None

    def _resolve_paths(
        self,
        job_id: int,
        video_id: int | None,
        source_path: str | None,
        requested_output_dir: str | None,
    ) -> tuple[Path | None, Path | None, str | None]:
        input_path, error = self._resolve_input_path(video_id, source_path)
        if error is not None:
            return None, None, error

        if video_id is not None:
            default_output_dir = input_path.parent / "scenes" / f"job_{job_id}"
        else:
            default_output_dir = self._library_dir / "_local_files" / f"job_{job_id}"

        output_dir = Path(requested_output_dir) if requested_output_dir else default_output_dir
        return input_path, output_dir, None

    def preview_scenes(
        self,
        video_id: int | None,
        source_path: str | None,
        threshold: float,
        min_scene_len_sec: float,
        trim_sec: float,
    ) -> list[tuple]:
        """Real user follow-up (docs/features/107-scene-cutter-false-split-fix.md):
        no single threshold works for every video -- a continuous handheld
        shot with fast motion needs a high threshold, a rapid multi-clip
        compilation needs a low one, and the only way to know which a given
        video needs is to actually look at the result. Runs detection only
        -- no ffmpeg splitting, no job/DB row, nothing written to disk --
        so trying a few threshold values back to back is fast, not a full
        cut-and-wait cycle each time. Raises ValueError (not a job status)
        since there's no job row to report a failure status on.
        """
        input_path, error = self._resolve_input_path(video_id, source_path)
        if error is not None:
            raise ValueError(error)
        return self._detect_scenes(input_path, threshold, min_scene_len_sec, trim_sec)

    @staticmethod
    def _merge_short_scenes(scenes: list[tuple], min_duration_sec: float) -> list[tuple]:
        """Extends a scene shorter than min_duration_sec to absorb it into
        the one immediately before it (the two are already contiguous --
        PySceneDetect's own scene list always covers the full video with
        no gaps -- so this is just widening the previous scene's end).
        The first scene has no predecessor to merge into and is left
        alone, same edge case _merge_short_beats already accepts.
        """
        if len(scenes) <= 1:
            return scenes
        merged = [scenes[0]]
        for start, end in scenes[1:]:
            duration_sec = (end - start).get_seconds()
            if duration_sec < min_duration_sec:
                prev_start, _ = merged[-1]
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))
        return merged

    @staticmethod
    def _detect_scenes(video_path: Path, threshold: float, min_scene_len_sec: float, trim_sec: float):
        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=threshold, min_scene_len=int(min_scene_len_sec * video.frame_rate))
        )
        scene_manager.detect_scenes(video)
        scenes = scene_manager.get_scene_list()
        scenes = SceneCutterService._merge_short_scenes(scenes, _MIN_SCENE_DURATION_FOR_MERGE_SEC)

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
