import logging
import queue
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from app.db.session import SessionLocal
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("queued", "merging", "finalizing")

FONT_PATH = "C:/Windows/Fonts/arial.ttf"
TRANSITION_STYLE = "slideleft"


class VideoComposerService:
    """Background video-composition engine: merges uploaded clips (in the
    user's chosen order) with a swipe-left transition, overlays a title,
    and optionally mixes in background music.

    Its own queue + worker thread, independent of DownloadEngine and
    SceneCutterService (see app/modules/README.md). Single worker: the
    whole pipeline is ffmpeg encoding work, and this is a desktop-local
    tool run by one user at a time.
    """

    def __init__(self, library_dir: Path):
        self._library_dir = library_dir
        self._root = library_dir / "_video_composer"
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(target=self._worker_loop, name="video-composer-worker", daemon=True)
        self._worker.start()
        self._recover_pending_jobs()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    # --- public API used by the router -----------------------------------

    def create_job(
        self,
        title: str,
        music_volume: float,
        transition_duration: float,
        requested_output_dir: str | None,
    ) -> int:
        db = SessionLocal()
        try:
            job = VideoComposeJob(
                title=title,
                music_volume=music_volume,
                transition_duration=transition_duration,
                requested_output_dir=requested_output_dir,
                status="queued",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()

    def job_dir(self, job_id: int) -> Path:
        return self._root / f"job_{job_id}"

    def save_input_clips(self, job_id: int, uploads: list[tuple[str, BinaryIO]]) -> None:
        inputs_dir = self.job_dir(job_id) / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        db = SessionLocal()
        try:
            for position, (filename, file_obj) in enumerate(uploads):
                suffix = Path(filename).suffix or ".mp4"
                destination = inputs_dir / f"{position:03d}_{uuid.uuid4().hex}{suffix}"
                with open(destination, "wb") as out:
                    shutil.copyfileobj(file_obj, out)
                db.add(VideoComposeClip(job_id=job_id, position=position, file_path=str(destination)))
            db.commit()
        finally:
            db.close()

    def save_music(self, job_id: int, filename: str, file_obj: BinaryIO) -> None:
        inputs_dir = self.job_dir(job_id) / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix or ".mp3"
        destination = inputs_dir / f"music_{uuid.uuid4().hex}{suffix}"
        with open(destination, "wb") as out:
            shutil.copyfileobj(file_obj, out)

        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is not None:
                job.music_path = str(destination)
                db.commit()
        finally:
            db.close()

    def enqueue(self, job_id: int) -> None:
        self._queue.put(job_id)

    # --- worker internals --------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            if job_id is None:
                self._queue.task_done()
                return
            try:
                self._run_job(job_id)
            except Exception:
                logger.exception("Unhandled error running video-compose job %s", job_id)
                self._set_status(job_id, "failed", error_message="Internal error")
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            clip_paths = [Path(c.file_path) for c in job.clips]
            title = job.title
            music_path = job.music_path
            music_volume = job.music_volume
            transition_duration = job.transition_duration
            requested_output_dir = job.requested_output_dir
        finally:
            db.close()

        if not clip_paths:
            self._set_status(job_id, "failed", error_message="Không có video nào để ghép")
            return
        for clip in clip_paths:
            if not clip.exists():
                self._set_status(job_id, "failed", error_message=f"Không tìm thấy file: {clip}")
                return

        work_dir = self.job_dir(job_id)
        tmp_dir = work_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        default_output_dir = work_dir / "output"
        output_dir = Path(requested_output_dir) if requested_output_dir else default_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        merged_video = tmp_dir / "merged.mp4"
        final_video = output_dir / "video_hoan_chinh.mp4"

        try:
            self._set_status(job_id, "merging")
            width, height, fps = self._probe_video_info(clip_paths[0])
            self._merge_clips_with_transitions(clip_paths, merged_video, transition_duration, width, height, fps)

            self._set_status(job_id, "finalizing")
            self._finalize(merged_video, title, music_path, music_volume, final_video, width)
        except Exception as exc:
            logger.exception("Video-compose job %s failed", job_id)
            self._set_status(job_id, "failed", error_message=str(exc))
            return
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            job.status = "completed"
            job.output_path = str(final_video)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    # --- ffmpeg/ffprobe helpers --------------------------------------------

    @staticmethod
    def _run_ffmpeg(args: list[str]) -> None:
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[-2000:]}")

    @staticmethod
    def _probe_duration(path: Path) -> float:
        command = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return float(result.stdout.strip())

    @staticmethod
    def _probe_video_info(path: Path) -> tuple[int, int, float]:
        command = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0:s=x",
            str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        width_str, height_str, fps_str = result.stdout.strip().split("x")
        num, _, den = fps_str.partition("/")
        fps = float(num) / float(den or 1)
        return int(width_str), int(height_str), fps

    def _merge_clips_with_transitions(
        self,
        clips: list[Path],
        output_path: Path,
        transition_duration: float,
        width: int,
        height: int,
        fps: float,
    ) -> None:
        durations = [self._probe_duration(c) for c in clips]

        # Clamp so a transition never tries to overlap more than a clip
        # actually contains -- otherwise the computed xfade offset for a
        # short clip could go negative.
        shortest = min(durations)
        safe_transition = min(transition_duration, shortest / 2) if len(clips) > 1 else 0.0

        inputs: list[str] = []
        for clip in clips:
            inputs += ["-i", str(clip)]

        filter_parts = []
        for i in range(len(clips)):
            filter_parts.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
            )

        if len(clips) == 1:
            final_label = "v0"
        else:
            prev_label = "v0"
            cumulative = durations[0]
            for i in range(1, len(clips)):
                offset = max(0.0, cumulative - safe_transition)
                new_label = f"vx{i}"
                filter_parts.append(
                    f"[{prev_label}][v{i}]xfade=transition={TRANSITION_STYLE}:"
                    f"duration={safe_transition}:offset={offset:.3f}[{new_label}]"
                )
                cumulative = cumulative + durations[i] - safe_transition
                prev_label = new_label
            final_label = prev_label

        self._run_ffmpeg(
            inputs
            + [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{final_label}]",
                "-an",
                str(output_path),
            ]
        )

    # --- final composition ---------------------------------------------------

    def _finalize(
        self,
        merged_video: Path,
        title: str,
        music_path: str | None,
        music_volume: float,
        output_path: Path,
        width: int,
    ) -> None:
        title_font_size = max(28, int(width * 0.05))
        title_escaped = title.replace(":", "\\:").replace("'", "\\'")
        font_escaped = FONT_PATH.replace(":", "\\:")
        title_filter = (
            f"drawtext=fontfile='{font_escaped}':text='{title_escaped}':"
            f"fontsize={title_font_size}:fontcolor=white:borderw=3:bordercolor=black@0.6:"
            f"box=1:boxcolor=black@0.4:boxborderw={int(title_font_size * 0.35)}:"
            f"x=(w-text_w)/2:y=h*0.02"
        )

        if music_path:
            self._run_ffmpeg(
                [
                    "-i", str(merged_video),
                    "-stream_loop", "-1",
                    "-i", music_path,
                    "-filter_complex",
                    f"[0:v]{title_filter}[v];[1:a]volume={music_volume}[a]",
                    "-map", "[v]",
                    "-map", "[a]",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-shortest",
                    str(output_path),
                ]
            )
        else:
            self._run_ffmpeg(
                [
                    "-i", str(merged_video),
                    "-filter_complex", f"[0:v]{title_filter}[v]",
                    "-map", "[v]",
                    "-an",
                    "-c:v", "libx264",
                    str(output_path),
                ]
            )

    # --- status/recovery -----------------------------------------------------

    def _set_status(self, job_id: int, status: str, **fields) -> None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
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
            pending = db.query(VideoComposeJob).filter(VideoComposeJob.status.in_(PENDING_STATUSES)).all()
            job_ids = [job.id for job in pending]
            for job in pending:
                job.status = "queued"
            db.commit()
        finally:
            db.close()

        for job_id in job_ids:
            self._queue.put(job_id)
