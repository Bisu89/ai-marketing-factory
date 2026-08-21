import json
import logging
import queue
import random
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import edge_tts
from PIL import ImageFont

from app.core import render_errors
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.exceptions import NotFoundError, RenderCancelled, ValidationError
from app.db.session import SessionLocal
from app.modules.video_composer.models import CAPTION_PRESETS, VideoComposeClip, VideoComposeJob

logger = logging.getLogger(__name__)

# Statuses a job can be found in when the app starts back up -- anything
# other than a terminal state (completed/failed/cancelled). "queued" means
# it never actually started (safe to just re-queue); everything else means
# it was genuinely RUNNING when the process died (see _recover_pending_jobs,
# Task 11 -- docs/features/38-render-job-hardening.md).
PENDING_STATUSES = (
    "queued", "rendering_beats", "merging", "narrating", "subtitling", "mixing_audio", "finalizing",
    "composing_final", "validating",
)
_RUNNING_STATUSES = tuple(s for s in PENDING_STATUSES if s != "queued")

# A callable that does the actual per-beat motion rendering for a
# composition-originated job: (composition_request, scenes_dir, is_cancelled,
# on_progress) -> ordered clip paths. Injected at construction time (see
# app/main.py) exactly the way app.services.download.engine.DownloadEngine
# takes a pluggable `Downloader` -- this file never imports
# app.modules.motion or app.modules.composition to implement it; the real
# implementation lives in app/api/v1/endpoints/composition_render.py (the
# composition root, allowed to import all three).
BeatRenderer = Callable[
    [dict, Path, Callable[[], bool], Callable[[int, int], None], Callable[[subprocess.Popen | None], None]],
    list[Path],
]

# Duration validation tolerance for the finished output vs. the merged
# clips' own probed duration (Task 10 hardening -- see
# docs/features/37-e2e-pipeline-hardening.md's "Final validation"). A
# container/encoder can shift the reported duration by a small fraction of
# a second without anything actually being wrong; this is not an allowance
# for narration/mixing genuinely changing the video's length.
_OUTPUT_DURATION_TOLERANCE_SEC = 0.5

# Task 26 (see docs/features/52-final-composer.md section 13) -- video
# duration is the sum of already-Voice-settled, already-frame-quantized
# Beat clip durations (Task 23's own per-clip tolerance is 2 frames each);
# across several beats that can add up to a few hundred ms without anything
# actually being wrong. Not an allowance for a genuine timing disagreement
# between Beat clips and the Audio Master.
_FINAL_DURATION_TOLERANCE_SEC = 1.0

FONT_PATH = "C:/Windows/Fonts/arial.ttf"
# The karaoke subtitle style below renders Bold=1, so word widths must be
# measured with the bold metrics or the highlight box drifts off the word.
FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"
TRANSITION_STYLE = "slideleft"

MAX_WORDS_PER_LINE = 5
MAX_LINE_DURATION_SEC = 4.5
LINE_BREAK_GAP_SEC = 0.6

# Background box colour behind the word currently being spoken. Text itself
# always stays white -- ASS &HBBGGRR& order (reversed from usual RRGGBB).
HIGHLIGHT_COLORS = [
    "00FFFF",
    "FFFF00",
    "9314FF",
    "00A5FF",
    "32CD32",
    "00D7FF",
    "FF6EC7",
    "F0E000",
]

# Per-preset caption styling (see _write_subtitles). `alignment`/`margin_v_frac`
# use ASS's own numpad alignment convention: 2 = bottom-center, 5 = middle-
# center. `font_scale` multiplies the caller-supplied base font_size, so
# "big_statement" reads as dramatically larger without a second font-sizing
# system.
CAPTION_PRESET_CONFIG = {
    "emotional": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "cinematic": {"font_bold": False, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.08, "alignment": 2},
    "word_highlight": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "big_statement": {"font_bold": True, "italic": False, "font_scale": 1.8, "margin_v_frac": 0.45, "alignment": 5},
    "quote": {"font_bold": False, "italic": True, "font_scale": 0.9, "margin_v_frac": 0.45, "alignment": 5},
    # 8 = top-center (ASS numpad convention) -- a modest margin below the
    # very top edge (clear of platform UI like TikTok's own top icons),
    # smaller than the default "emotional" size so it reads as a caption,
    # not a headline.
    "top": {"font_bold": True, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.09, "alignment": 8},
}
assert set(CAPTION_PRESET_CONFIG) == set(CAPTION_PRESETS)

# Task 26 (see docs/features/52-final-composer.md section 18/22) -- ffmpeg's
# own `overlay` filter exposes W/H (main video) and w/h (overlay) as filter
# expression variables directly, so position is just an (x, y) expression
# pair per corner; margins keep the mark off the frame edge (section 22's
# "safe area"), never flush against it.
WATERMARK_POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
_WATERMARK_POSITION_EXPR: dict[str, Callable[[int, int], tuple[str, str]]] = {
    "top-left": lambda mx, my: (f"{mx}", f"{my}"),
    "top-right": lambda mx, my: (f"W-w-{mx}", f"{my}"),
    "bottom-left": lambda mx, my: (f"{mx}", f"H-h-{my}"),
    "bottom-right": lambda mx, my: (f"W-w-{mx}", f"H-h-{my}"),
}


class VideoComposerService:
    """Background video-composition engine: merges uploaded clips (in the
    user's chosen order) with a swipe-left transition, overlays a title,
    generates TTS narration (any edge-tts voice/language the caller picks)
    + burned-in karaoke subtitles from a typed script, and mixes in optional
    background music.

    Its own queue + worker thread, independent of DownloadEngine and
    SceneCutterService (see app/modules/README.md) -- ffmpeg/TTS work here
    has nothing to do with either of those and shouldn't share failure
    modes with them. Single worker: the whole pipeline is CPU/GPU-bound
    (ffmpeg) or network-bound in a single request (TTS), and this is a
    desktop-local tool run by one user at a time.
    """

    def __init__(
        self,
        library_dir: Path,
        beat_renderer: BeatRenderer | None = None,
        event_bus: EventBus | None = None,
    ):
        self._library_dir = library_dir
        self._root = library_dir / "_video_composer"
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._beat_renderer = beat_renderer
        self._event_bus = event_bus

        # Runtime-only job-control state (Task 11 -- see
        # docs/features/38-render-job-hardening.md), never persisted to
        # SQLite: a cancellation flag per in-flight job, and whichever
        # ffmpeg subprocess that job currently owns (if any), so cancel_job
        # can terminate it immediately rather than only at the next
        # checkpoint. Mirrors app.services.download.engine.DownloadEngine's
        # JobControl -- same shape, independent instance (never shared).
        self._cancel_events: dict[int, threading.Event] = {}
        self._active_processes: dict[int, subprocess.Popen] = {}
        self._runtime_lock = threading.Lock()

    def start(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(target=self._worker_loop, name="video-composer-worker", daemon=True)
        self._worker.start()
        self._recover_pending_jobs()

    def shutdown(self, timeout: float = 5.0) -> None:
        # Stop accepting new work first, then let whatever's already
        # RUNNING finish (or be cancelled by the user before shutdown) --
        # this is a graceful stop, not a kill; the worker thread exits
        # after its current _run_job call returns.
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=timeout)

    # --- public API used by the router -----------------------------------

    def create_job(
        self,
        title: str,
        script_text: str,
        voice: str,
        music_volume: float,
        transition_duration: float,
        burn_subtitles: bool,
        requested_output_dir: str | None,
        narration_volume: float = 1.0,
        music_ducking_ratio: float = 8.0,
        fade_in_sec: float = 0.0,
        fade_out_sec: float = 0.0,
        caption_preset: str = "emotional",
        sfx_cues: list[dict] | None = None,
        narration_mode: str = "tts",
        beat_narration_specs: list[dict] | None = None,
        render_profile: str = "SOCIAL_VERTICAL",
        preflight_seconds: float | None = None,
        composition_request_json: dict | None = None,
        audio_master_path: str | None = None,
        captions_ass_path: str | None = None,
        watermark_enabled: bool = False,
        watermark_path: str | None = None,
        watermark_position: str = "bottom-right",
        watermark_opacity: float = 1.0,
        watermark_scale: float = 0.15,
        watermark_margin_x: int = 24,
        watermark_margin_y: int = 24,
        outro_clip_path: str | None = None,
    ) -> int:
        db = SessionLocal()
        try:
            job = VideoComposeJob(
                title=title,
                script_text=script_text,
                voice=voice,
                music_volume=music_volume,
                narration_volume=narration_volume,
                music_ducking_ratio=music_ducking_ratio,
                fade_in_sec=fade_in_sec,
                fade_out_sec=fade_out_sec,
                caption_preset=caption_preset,
                sfx_cues=sfx_cues,
                narration_mode=narration_mode,
                beat_narration_specs=beat_narration_specs,
                transition_duration=transition_duration,
                burn_subtitles=burn_subtitles,
                requested_output_dir=requested_output_dir,
                render_profile=render_profile,
                preflight_seconds=preflight_seconds,
                # Persisted so the worker can do beat rendering itself
                # (see BeatRenderer above) and so retry_job can rebuild an
                # equivalent request -- None for the plain upload-based
                # Video Composer flow, which has real clips already.
                composition_request_json=composition_request_json,
                # Task 26 -- Final Composer (see docs/features/52-final-composer.md).
                audio_master_path=audio_master_path,
                captions_ass_path=captions_ass_path,
                watermark_enabled=watermark_enabled,
                watermark_path=watermark_path,
                watermark_position=watermark_position,
                watermark_opacity=watermark_opacity,
                watermark_scale=watermark_scale,
                watermark_margin_x=watermark_margin_x,
                watermark_margin_y=watermark_margin_y,
                outro_clip_path=outro_clip_path,
                status="queued",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()

    def set_beat_render_seconds(self, job_id: int, seconds: float) -> None:
        """Records how long the RENDER_BEATS phase took for this job. As of
        Task 11 (docs/features/38-render-job-hardening.md) this phase runs
        on the worker itself (_run_beat_rendering_phase, below), not on the
        HTTP request thread -- kept as its own small setter (rather than
        folding into _set_status) since it's timing data, not a status
        transition.
        """
        self._set_fields(job_id, beat_render_seconds=seconds)

    def set_beat_progress(self, job_id: int, current: int, total: int) -> None:
        """Live progress during RENDER_BEATS only -- always a real, known
        count (never a guessed percentage), per this task's own "never fake
        progress" instruction.
        """
        self._set_fields(job_id, render_progress_current=current, render_progress_total=total)
        self._publish("render.job.progress", {"job_id": job_id, "current": current, "total": total})

    def cancel_job(self, job_id: int) -> bool:
        """Cancels a QUEUED or RUNNING job. Returns False if the job doesn't
        exist or is already in a terminal state (completed/failed/cancelled
        cannot be cancelled). A QUEUED job (never picked up by the worker
        yet) is cancelled immediately here; a RUNNING job is signalled via
        an in-memory cancel event (observed at the next phase/beat
        checkpoint -- see _is_cancelled) and has its currently-owned ffmpeg
        process (if any) terminated right away, rather than waiting for
        that checkpoint. Only the process this specific job registered is
        ever touched -- never an unrelated OS process.
        """
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return False
            status = job.status
            if status == "queued":
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                self._write_render_report(self._library_dir, job_id, status="cancelled", failed_phase=None, timing={})
                self._publish("render.job.cancelled", {"job_id": job_id})
                return True
            if status not in _RUNNING_STATUSES:
                return False  # completed/failed/cancelled -- nothing to do
        finally:
            db.close()

        with self._runtime_lock:
            self._cancel_events.setdefault(job_id, threading.Event()).set()
            process = self._active_processes.get(job_id)
        if process is not None and process.poll() is None:
            process.terminate()
        return True

    def retry_job(self, job_id: int) -> int:
        """Creates a fresh RenderJob attempt for a failed/cancelled job,
        reusing its stored render request (composition_request_json --
        None for the plain upload-based flow, which has no stored request
        to replay and so cannot be retried this way). Never mutates the
        original job row -- retrying creates job N+1, job N keeps its own
        final status/report/log exactly as they were, per this task's "do
        not corrupt the previous job record" instruction.
        """
        db = SessionLocal()
        try:
            original = db.get(VideoComposeJob, job_id)
            if original is None:
                raise NotFoundError("Video compose job", job_id)
            if original.composition_request_json is None:
                raise ValidationError("This job has no stored render request and cannot be retried.")
            if original.status not in ("failed", "cancelled"):
                raise ValidationError(
                    f"Only a failed or cancelled job can be retried (current status: {original.status})."
                )
            new_job = VideoComposeJob(
                title=original.title,
                script_text=original.script_text,
                voice=original.voice,
                music_path=original.music_path,
                music_volume=original.music_volume,
                narration_volume=original.narration_volume,
                music_ducking_ratio=original.music_ducking_ratio,
                fade_in_sec=original.fade_in_sec,
                fade_out_sec=original.fade_out_sec,
                caption_preset=original.caption_preset,
                sfx_cues=original.sfx_cues,
                narration_mode=original.narration_mode,
                beat_narration_specs=original.beat_narration_specs,
                transition_duration=original.transition_duration,
                burn_subtitles=original.burn_subtitles,
                requested_output_dir=original.requested_output_dir,
                render_profile=original.render_profile,
                composition_request_json=original.composition_request_json,
                audio_master_path=original.audio_master_path,
                captions_ass_path=original.captions_ass_path,
                watermark_enabled=original.watermark_enabled,
                watermark_path=original.watermark_path,
                watermark_position=original.watermark_position,
                watermark_opacity=original.watermark_opacity,
                watermark_scale=original.watermark_scale,
                watermark_margin_x=original.watermark_margin_x,
                watermark_margin_y=original.watermark_margin_y,
                outro_clip_path=original.outro_clip_path,
                previous_job_id=original.id,
                status="queued",
            )
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            new_job_id = new_job.id
        finally:
            db.close()

        self.enqueue(new_job_id)
        return new_job_id

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

    def save_clip_paths(self, job_id: int, paths: list[Path]) -> None:
        """Registers already-on-disk clip files as a job's ordered input
        clips, without copying them -- unlike save_input_clips, which
        exists for browser multipart uploads that must be copied to disk
        first. This is the extension point a composition-plan renderer
        (see app/api/v1/endpoints/composition_render.py) uses to hand off
        clips it already produced/located on disk, without this module
        needing to know anything about where they came from.
        """
        db = SessionLocal()
        try:
            for position, path in enumerate(paths):
                db.add(VideoComposeClip(job_id=job_id, position=position, file_path=str(path)))
            db.commit()
        finally:
            db.close()

    def set_music_path(self, job_id: int, path: str) -> None:
        """Like save_clip_paths relative to save_input_clips: registers an
        already-on-disk music file directly, without copying it -- for a
        caller (e.g. a composition-plan renderer) that already has a real
        path, as opposed to save_music's browser-upload copy step.
        """
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is not None:
                job.music_path = path
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
                with self._runtime_lock:
                    self._cancel_events.pop(job_id, None)
                    self._active_processes.pop(job_id, None)
                self._queue.task_done()

    def _run_beat_rendering_phase(self, job_id: int, composition_request: dict) -> list[Path] | None:
        """RENDER_BEATS, run on the worker (Task 11 moved this off the HTTP
        request thread -- see docs/features/38-render-job-hardening.md).
        Delegates the actual motion rendering to the injected
        `self._beat_renderer` (implemented in composition_render.py, which
        alone is allowed to import both app.modules.motion and
        app.modules.composition). Returns None (having already marked the
        job failed/cancelled itself) if rendering didn't produce clips.
        """
        if self._beat_renderer is None:
            self._fail_job(job_id, "rendering_beats", "This job requires beat rendering but none is configured.")
            return None

        self._set_status(job_id, "rendering_beats")
        self._log(job_id, "phase started: RENDER_BEATS")
        self._publish("render.job.phase_changed", {"job_id": job_id, "phase": "RENDER_BEATS"})
        scenes_dir = self.job_dir(job_id) / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        start = time.monotonic()
        try:
            clip_paths = self._beat_renderer(
                composition_request,
                scenes_dir,
                lambda: self._is_cancelled(job_id),
                lambda current, total: self.set_beat_progress(job_id, current, total),
                lambda process: self._register_process(job_id, process)
                if process is not None
                else self._unregister_process(job_id),
            )
        except RenderCancelled:
            self._finish_cancelled(job_id, "rendering_beats")
            return None
        except Exception as exc:
            logger.exception("Beat rendering failed for job %s", job_id)
            self._fail_job(job_id, "rendering_beats", str(exc))
            return None

        beat_render_seconds = time.monotonic() - start
        self.save_clip_paths(job_id, clip_paths)
        self.set_beat_render_seconds(job_id, beat_render_seconds)
        self._log(job_id, f"phase completed: RENDER_BEATS ({beat_render_seconds:.2f}s, {len(clip_paths)} clips)")
        return clip_paths

    def _run_job(self, job_id: int) -> None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            if job.status == "cancelled":
                return  # cancelled while still queued -- the worker never actually starts it
            composition_request = job.composition_request_json
            has_clips = bool(job.clips)
        finally:
            db.close()

        self._log(job_id, "job started")
        self._publish("render.job.started", {"job_id": job_id})

        if not has_clips and composition_request is not None:
            if self._run_beat_rendering_phase(job_id, composition_request) is None:
                return  # already marked failed/cancelled

        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            clip_paths = [Path(c.file_path) for c in job.clips]
            title = job.title
            script_text = job.script_text
            voice = job.voice
            music_path = job.music_path
            music_volume = job.music_volume
            narration_volume = job.narration_volume
            music_ducking_ratio = job.music_ducking_ratio
            fade_in_sec = job.fade_in_sec
            fade_out_sec = job.fade_out_sec
            caption_preset = job.caption_preset
            sfx_cues = job.sfx_cues
            narration_mode = job.narration_mode
            beat_narration_specs = job.beat_narration_specs
            transition_duration = job.transition_duration
            burn_subtitles = job.burn_subtitles
            requested_output_dir = job.requested_output_dir
            preflight_seconds = job.preflight_seconds
            beat_render_seconds = job.beat_render_seconds
            audio_master_path = job.audio_master_path
            captions_ass_path = job.captions_ass_path
            watermark_enabled = job.watermark_enabled
            watermark_path = job.watermark_path
            watermark_position = job.watermark_position
            watermark_opacity = job.watermark_opacity
            watermark_scale = job.watermark_scale
            watermark_margin_x = job.watermark_margin_x
            watermark_margin_y = job.watermark_margin_y
            outro_clip_path = job.outro_clip_path
        finally:
            db.close()

        if not clip_paths:
            self._fail_job(job_id, "merging", "Không có video nào để ghép")
            return
        for clip in clip_paths:
            if not clip.exists():
                self._fail_job(job_id, "merging", f"Không tìm thấy file: {clip}")
                return

        work_dir = self.job_dir(job_id)
        tmp_dir = work_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        default_output_dir = work_dir / "output"
        output_dir = Path(requested_output_dir) if requested_output_dir else default_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if narration_mode == "precomposed":
            # Task 26 -- Final Composer (see docs/features/52-final-composer.md).
            # A completely different, single-pass pipeline: no TTS, no
            # local-narration timeline, no _mix_audio, no crossfade merge --
            # every other narration_mode value below is entirely unaffected.
            self._run_final_composition(
                job_id, clip_paths, audio_master_path,
                captions_ass_path if burn_subtitles else None,
                watermark_path if watermark_enabled else None,
                watermark_position, watermark_opacity, watermark_scale, watermark_margin_x, watermark_margin_y,
                output_dir, tmp_dir, preflight_seconds, beat_render_seconds,
                outro_clip_path,
            )
            return

        merged_video = tmp_dir / "merged.mp4"
        # Extension matches actual content: edge_tts (_run_narration) writes
        # real MP3 bytes; the local-narration timeline concatenates AAC
        # segments with "-c copy" (see _build_narration_timeline), which
        # needs an AAC/MP4-family container, not an MP3 one.
        narration_audio = tmp_dir / ("narration_timeline.m4a" if narration_mode == "local" else "narration.mp3")
        mixed_audio = tmp_dir / "mixed_audio.m4a"
        subtitle_ass = output_dir / "phu_de_karaoke.ass"
        subtitle_srt = output_dir / "phu_de.srt"
        final_video = output_dir / "video_hoan_chinh.mp4"
        # Never expose final_video until it's been validated (Task 10
        # hardening -- "atomic output"): ffmpeg writes into this temp name
        # first; only a successful _validate_final_output triggers the
        # atomic rename onto final_video, below. If anything fails first,
        # this is deleted and final_video never exists for this job.
        tmp_final_video = output_dir / ".video_hoan_chinh.tmp.mp4"

        render_start = time.monotonic()
        composition_seconds = narrating_seconds = subtitling_seconds = 0.0
        mixing_seconds = finalizing_seconds = validation_seconds = 0.0

        def _checkpoint() -> None:
            # Phase-boundary cancellation (Task 11): each phase below is a
            # handful of seconds at most (see the Task 10 benchmark), so
            # checking here -- rather than mid-ffmpeg-call -- keeps worst-
            # case cancel latency bounded to "however long the current
            # phase's ffmpeg call takes" without needing every _run_ffmpeg
            # call site to track/kill its own Popen. RENDER_BEATS (the one
            # phase long enough for that gap to matter) gets live process
            # termination instead -- see _run_beat_rendering_phase.
            if self._is_cancelled(job_id):
                raise RenderCancelled()

        try:
            _checkpoint()
            self._set_status(job_id, "merging")
            self._log(job_id, "phase started: COMPOSE_VIDEO")
            stage_start = time.monotonic()
            width, height, fps = self._probe_video_info(clip_paths[0])
            if len(clip_paths) > 1:
                self._merge_clips_with_transitions(clip_paths, merged_video, transition_duration, width, height, fps)
            else:
                # A single clip has nothing to transition into -- skip the
                # ffmpeg scale/pad/concat pass entirely and feed the
                # original upload straight into narration/subtitle/finalize.
                # Saves a redundant re-encode and keeps the source quality.
                merged_video = clip_paths[0]
            composition_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: COMPOSE_VIDEO ({composition_seconds:.2f}s)")

            _checkpoint()
            self._set_status(job_id, "narrating")
            self._log(job_id, "phase started: BUILD_AUDIO")
            stage_start = time.monotonic()
            if narration_mode == "local":
                # No network call, no transcript -- a pre-recorded local
                # clip has no live word-boundary data of its own. Beats
                # with no narration asset assigned get pure silence for
                # their full duration, never TTS -- see
                # docs/features/36-audio-pipeline.md.
                self._build_narration_timeline(beat_narration_specs or [], tmp_dir / "narration_segments", narration_audio)
                words: list[dict] = []
            else:
                words = self._run_narration(script_text, voice, narration_audio)
            narrating_seconds = time.monotonic() - stage_start

            self._set_status(job_id, "subtitling")
            stage_start = time.monotonic()
            if narration_mode == "local" and captions_ass_path is not None:
                # See docs/features/56-classic-render-captions.md -- a real,
                # already-resolved captions.ass (Task 25's Caption Engine,
                # built from Beat.narration + Beat.start/end, independent
                # of TTS engine) burns directly here instead of the empty
                # file _write_subtitles([], ...) would otherwise produce
                # from local narration's own lack of word-boundary data.
                subtitle_ass = Path(captions_ass_path)
            else:
                lines = self._group_words_into_lines(words)
                font_size = max(28, int(height * 0.045))
                self._write_subtitles(lines, subtitle_ass, subtitle_srt, width, height, font_size, caption_preset)
            subtitling_seconds = time.monotonic() - stage_start

            _checkpoint()
            self._set_status(job_id, "mixing_audio")
            stage_start = time.monotonic()
            video_duration = self._probe_duration(merged_video)
            self._mix_audio(
                narration_audio,
                music_path,
                music_volume,
                narration_volume,
                music_ducking_ratio,
                fade_in_sec,
                fade_out_sec,
                video_duration,
                mixed_audio,
                sfx_cues=sfx_cues,
            )
            mixing_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: BUILD_AUDIO ({narrating_seconds + mixing_seconds:.2f}s)")

            _checkpoint()
            self._set_status(job_id, "finalizing")
            self._log(job_id, "phase started: BURN_CAPTIONS")
            stage_start = time.monotonic()
            self._finalize(merged_video, mixed_audio, title, subtitle_ass, burn_subtitles, tmp_final_video, width)
            finalizing_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: BURN_CAPTIONS ({subtitling_seconds + finalizing_seconds:.2f}s)")

            _checkpoint()
            self._set_status(job_id, "validating")
            self._log(job_id, "phase started: VALIDATE_OUTPUT")
            stage_start = time.monotonic()
            self._validate_final_output(
                tmp_final_video, expected_duration=video_duration, width=width, height=height, fps=fps
            )
            tmp_final_video.replace(final_video)
            validation_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: VALIDATE_OUTPUT ({validation_seconds:.2f}s)")
        except RenderCancelled:
            tmp_final_video.unlink(missing_ok=True)
            self._finish_cancelled(job_id, self._get_status(job_id) or "unknown")
            return
        except Exception as exc:
            failed_phase = self._get_status(job_id) or "unknown"
            logger.exception("Video-compose job %s failed in phase %s", job_id, failed_phase)
            tmp_final_video.unlink(missing_ok=True)
            self._fail_job(
                job_id,
                failed_phase,
                str(exc),
                timing={
                    "preflight": preflight_seconds,
                    "beat_render": beat_render_seconds,
                    "composition": round(composition_seconds, 2) or None,
                    "audio": round(narrating_seconds + mixing_seconds, 2) or None,
                    "captions": round(subtitling_seconds + finalizing_seconds, 2) or None,
                    "validation": round(validation_seconds, 2) or None,
                },
            )
            return
        finally:
            if not get_settings().debug:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        render_seconds = time.monotonic() - render_start
        self._write_render_metadata(
            final_video,
            video_duration,
            render_seconds,
            width=width,
            height=height,
            fps=fps,
            clip_count=len(clip_paths),
        )
        self._write_render_report(
            self._library_dir,
            job_id,
            status="completed",
            final_video=final_video,
            video_duration=video_duration,
            clip_count=len(clip_paths),
            width=width,
            height=height,
            fps=fps,
            caption_enabled=burn_subtitles,
            narration_mode=narration_mode,
            timing={
                "preflight": preflight_seconds,
                "beat_render": beat_render_seconds,
                "composition": round(composition_seconds, 2),
                "audio": round(narrating_seconds + mixing_seconds, 2),
                "captions": round(subtitling_seconds + finalizing_seconds, 2),
                "validation": round(validation_seconds, 2),
                "total": round(render_seconds, 2),
            },
        )

        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            job.status = "completed"
            job.output_path = str(final_video)
            job.subtitle_srt_path = str(subtitle_srt)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        self._log(job_id, f"job completed ({render_seconds:.2f}s)")
        self._publish("render.job.completed", {"job_id": job_id, "output_path": str(final_video)})

    # --- Final Composer (Task 26 -- see docs/features/52-final-composer.md) --

    def _run_final_composition(
        self,
        job_id: int,
        clip_paths: list[Path],
        audio_master_path: str,
        captions_ass_path: str | None,
        watermark_path: str | None,
        watermark_position: str,
        watermark_opacity: float,
        watermark_scale: float,
        watermark_margin_x: int,
        watermark_margin_y: int,
        output_dir: Path,
        tmp_dir: Path,
        preflight_seconds: float | None,
        beat_render_seconds: float | None,
        outro_clip_path: str | None = None,
    ) -> None:
        """Beat clips + Audio Master + Captions + optional watermark ->
        final.mp4 in ONE ffmpeg pass (section 33: "prefer one final
        composition pass" -- no intermediate merged/captioned/watermarked
        full-video file ever touches disk). Only ever called from _run_job
        when narration_mode == "precomposed"; the original multi-pass
        merge/narrate/subtitle/mix/finalize pipeline above is completely
        untouched for every other job.

        `outro_clip_path` (Outro Card -- see docs/features/89-outro-card.md,
        real user report: videos cut off abruptly right when narration
        ends), when given, is a separately pre-rendered short clip
        (app.modules.outro's own renderer) concatenated onto the end of
        this main composition, AFTER validation against Audio Master's own
        duration below -- that check is only about the main video/audio
        staying internally consistent with each other, so the outro
        (deliberately extending the video beyond narration's length) never
        needs to participate in it.

        Section 6/8: every input is validated -- Beat clip existence/
        readability/video-stream, Audio Master existence/readability,
        Captions/Watermark existence when provided -- *before* the only
        ffmpeg call this method makes (_compose_final); nothing partial is
        ever written to the canonical output path.
        """
        final_video = output_dir / "video_hoan_chinh.mp4"
        tmp_final_video = output_dir / ".video_hoan_chinh.tmp.mp4"

        def _checkpoint() -> None:
            if self._is_cancelled(job_id):
                raise RenderCancelled()

        render_start = time.monotonic()
        composing_seconds = validation_seconds = 0.0
        width = height = 0
        fps = 0.0
        audio_duration = 0.0
        try:
            _checkpoint()
            self._set_status(job_id, "composing_final")
            self._log(job_id, "phase started: FINAL_COMPOSITION")
            stage_start = time.monotonic()

            clip_durations: list[float] = []
            for index, clip in enumerate(clip_paths):
                if not clip.exists():
                    raise RuntimeError(
                        f"{render_errors.MISSING_BEAT_ARTIFACT}: Beat clip {index + 1}/{len(clip_paths)} "
                        f"not found: {clip}"
                    )
                try:
                    clip_width, clip_height, clip_fps = self._probe_video_info(clip)
                    clip_duration = self._probe_duration(clip)
                except (ValueError, ZeroDivisionError) as exc:
                    raise RuntimeError(
                        f"{render_errors.INVALID_BEAT_ARTIFACT}: Beat clip {index + 1}/{len(clip_paths)} "
                        f"is not a readable video: {clip} ({exc})"
                    ) from exc
                if index == 0:
                    width, height, fps = clip_width, clip_height, clip_fps
                clip_durations.append(clip_duration)

            if not Path(audio_master_path).exists():
                raise RuntimeError(
                    f"{render_errors.AUDIO_MASTER_MISSING}: Audio Master file not found: {audio_master_path}"
                )
            try:
                audio_duration = self._probe_duration(Path(audio_master_path))
            except ValueError as exc:
                raise RuntimeError(
                    f"{render_errors.AUDIO_MASTER_MISSING}: Audio Master is not a readable audio file: "
                    f"{audio_master_path}"
                ) from exc

            if captions_ass_path is not None and not Path(captions_ass_path).exists():
                raise RuntimeError(
                    f"{render_errors.CAPTION_ARTIFACT_MISSING}: Captions file not found: {captions_ass_path}"
                )
            if watermark_path is not None and not Path(watermark_path).exists():
                raise RuntimeError(
                    f"{render_errors.WATERMARK_ARTIFACT_MISSING}: Watermark file not found: {watermark_path}"
                )

            # Section 9/13: video duration is the sum of Beat clip durations
            # (gapless concat -- see _compose_final, no crossfade eaten
            # time); Audio Master is authoritative for the final trim, but a
            # real mismatch beyond tolerance means something upstream
            # disagrees about timing, not something to silently paper over.
            video_duration = sum(clip_durations)
            duration_diff = abs(video_duration - audio_duration)
            if duration_diff > _FINAL_DURATION_TOLERANCE_SEC:
                raise RuntimeError(
                    f"{render_errors.FINAL_DURATION_MISMATCH}: video={video_duration:.2f}s "
                    f"audio={audio_duration:.2f}s diff={duration_diff:.2f}s "
                    f"(tolerance {_FINAL_DURATION_TOLERANCE_SEC}s)"
                )

            _checkpoint()
            try:
                self._compose_final(
                    clip_paths, Path(audio_master_path),
                    Path(captions_ass_path) if captions_ass_path else None,
                    Path(watermark_path) if watermark_path else None,
                    watermark_position, watermark_opacity, watermark_scale, watermark_margin_x, watermark_margin_y,
                    width, height, audio_duration, tmp_final_video,
                )
            except RuntimeError as exc:
                raise RuntimeError(f"{render_errors.FINAL_ENCODING_FAILED}: {exc}") from exc
            composing_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: FINAL_COMPOSITION ({composing_seconds:.2f}s)")

            _checkpoint()
            self._set_status(job_id, "validating")
            self._log(job_id, "phase started: VALIDATE_OUTPUT")
            stage_start = time.monotonic()
            self._validate_final_output(
                tmp_final_video, expected_duration=audio_duration, width=width, height=height, fps=fps
            )
            tmp_final_video.replace(final_video)
            validation_seconds = time.monotonic() - stage_start
            self._log(job_id, f"phase completed: VALIDATE_OUTPUT ({validation_seconds:.2f}s)")

            outro_duration = 0.0
            if outro_clip_path is not None and Path(outro_clip_path).exists():
                _checkpoint()
                self._log(job_id, "phase started: APPEND_OUTRO")
                outro_duration = self._probe_duration(Path(outro_clip_path))
                tmp_with_outro = tmp_dir / ".video_hoan_chinh.outro.tmp.mp4"
                self._append_outro_clip(final_video, Path(outro_clip_path), tmp_with_outro)
                tmp_with_outro.replace(final_video)
                self._log(job_id, f"phase completed: APPEND_OUTRO (+{outro_duration:.2f}s)")
                audio_duration += outro_duration
        except RenderCancelled:
            tmp_final_video.unlink(missing_ok=True)
            self._finish_cancelled(job_id, self._get_status(job_id) or "unknown")
            return
        except Exception as exc:
            failed_phase = self._get_status(job_id) or "unknown"
            logger.exception("Video-compose job %s failed in phase %s", job_id, failed_phase)
            tmp_final_video.unlink(missing_ok=True)
            self._fail_job(
                job_id, failed_phase, str(exc),
                timing={
                    "preflight": preflight_seconds,
                    "beat_render": beat_render_seconds,
                    "composition": round(composing_seconds, 2) or None,
                    "validation": round(validation_seconds, 2) or None,
                },
            )
            return
        finally:
            if not get_settings().debug:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        render_seconds = time.monotonic() - render_start
        self._write_render_metadata(
            final_video, audio_duration, render_seconds, width=width, height=height, fps=fps,
            clip_count=len(clip_paths),
        )
        self._write_render_report(
            self._library_dir, job_id, status="completed", final_video=final_video, video_duration=audio_duration,
            clip_count=len(clip_paths), width=width, height=height, fps=fps,
            caption_enabled=captions_ass_path is not None, narration_mode="precomposed",
            timing={
                "preflight": preflight_seconds,
                "beat_render": beat_render_seconds,
                "composition": round(composing_seconds, 2),
                "validation": round(validation_seconds, 2),
                "total": round(render_seconds, 2),
            },
        )

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
        self._log(job_id, f"job completed ({render_seconds:.2f}s)")
        self._publish("render.job.completed", {"job_id": job_id, "output_path": str(final_video)})

    def _compose_final(
        self,
        clip_paths: list[Path],
        audio_path: Path,
        captions_path: Path | None,
        watermark_path: Path | None,
        watermark_position: str,
        watermark_opacity: float,
        watermark_scale: float,
        watermark_margin_x: int,
        watermark_margin_y: int,
        width: int,
        height: int,
        duration: float,
        output_path: Path,
    ) -> None:
        """The one ffmpeg call (section 31/32): concat (gapless, via the
        `concat` filter -- Beat clips are already normalized to the same
        resolution/fps/pixel format by Task 23's own Motion renderer, so no
        blind re-encode/re-scale pass is needed first, section 11) ->
        captions -> watermark -> format -> encode. Audio is mapped straight
        from Audio Master (section 12/29/30) -- every Beat clip is always
        rendered `-an` (no audio stream at all, see app.modules.motion.
        renderer), so there is no risk of accidentally keeping Beat-clip
        audio in the final mix.
        """
        inputs: list[str] = []
        for clip in clip_paths:
            inputs += ["-i", str(clip)]
        audio_input_index = len(clip_paths)
        inputs += ["-i", str(audio_path)]

        concat_labels = "".join(f"[{i}:v]" for i in range(len(clip_paths)))
        filters = [f"{concat_labels}concat=n={len(clip_paths)}:v=1:a=0[vcat]"]
        video_label = "vcat"

        if captions_path is not None:
            # Section 15: reuse this app's own established font resolution
            # (FONT_PATH/FONT_PATH_BOLD -- the same Arial this service
            # already relies on for _write_subtitles/_finalize's drawtext)
            # rather than trusting ambient system font matching -- both
            # video_composer's own ASS Style lines and app.modules.caption.
            # ass_writer's own (Task 25) hardcode "Arial" as the font
            # family, so pointing fontsdir at this known location is this
            # app's one and only configured fallback, not a silent
            # substitution.
            fontsdir = self._escape_for_ffmpeg_filter(Path(FONT_PATH).parent)
            escaped_ass = self._escape_for_ffmpeg_filter(captions_path)
            filters.append(f"[{video_label}]subtitles='{escaped_ass}':fontsdir='{fontsdir}'[vcap]")
            video_label = "vcap"

        if watermark_path is not None:
            watermark_input_index = audio_input_index + 1
            inputs += ["-i", str(watermark_path)]
            target_width = max(2, int(width * watermark_scale))
            x_expr, y_expr = _WATERMARK_POSITION_EXPR[watermark_position](watermark_margin_x, watermark_margin_y)
            filters.append(
                f"[{watermark_input_index}:v]scale={target_width}:-1,format=rgba,"
                f"colorchannelmixer=aa={watermark_opacity}[wm]"
            )
            filters.append(f"[{video_label}][wm]overlay=x={x_expr}:y={y_expr}[vwm]")
            video_label = "vwm"

        filters.append(f"[{video_label}]format=yuv420p[v]")

        self._run_ffmpeg(
            inputs
            + [
                "-filter_complex", ";".join(filters),
                "-map", "[v]",
                "-map", f"{audio_input_index}:a",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                # Audio Master's own duration is authoritative (section 12/13)
                # -- a hard trim here, not a stretch: both streams are
                # already within _FINAL_DURATION_TOLERANCE_SEC of this
                # value by construction (checked before this call).
                "-t", f"{duration}",
                str(output_path),
            ]
        )

    def _append_outro_clip(self, main_video: Path, outro_clip: Path, output_path: Path) -> None:
        """Concatenates the Outro Card (docs/features/89-outro-card.md) onto
        the end of the already-composed, already-validated main video.
        Uses the `concat` *filter* (full re-encode of both inputs
        together), not the concat *demuxer*'s `-c copy` -- the demuxer
        requires the two inputs' codecs/params to already match exactly,
        which two separately-invoked ffmpeg encodes (main composition here,
        the outro's own render_outro_clip elsewhere) have no guarantee of;
        the filter decodes both and re-encodes fresh, so it's correct
        regardless of any such mismatch, at the cost of one more (still
        short, since the outro itself is 5-7s) re-encode pass.
        """
        self._run_ffmpeg(
            [
                "-i", str(main_video),
                "-i", str(outro_clip),
                "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path),
            ]
        )

    # --- ffmpeg/ffprobe helpers --------------------------------------------

    @staticmethod
    def _run_ffmpeg(args: list[str]) -> None:
        # -nostdin + stdin=DEVNULL: ffmpeg reads stdin by default for
        # interactive key commands; run as a subprocess with an inherited/
        # piped stdin that never delivers EOF, it can block indefinitely on
        # certain inputs instead of failing fast (confirmed as a real,
        # reproducible hang while building app/modules/motion/renderer.py --
        # see docs/features/23-local-motion-renderer.md's "Real bugs" -- and
        # flagged there as a latent gap in this exact method).
        command = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"] + args
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
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
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
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
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
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
        safe_transition = min(transition_duration, shortest / 2)

        inputs: list[str] = []
        for clip in clips:
            inputs += ["-i", str(clip)]

        filter_parts = []
        for i in range(len(clips)):
            filter_parts.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
            )

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

    # --- narration + subtitles ----------------------------------------------

    def _run_narration(self, script_text: str, voice: str, output_path: Path) -> list[dict]:
        import asyncio

        async def _generate() -> list[dict]:
            communicate = edge_tts.Communicate(script_text, voice, boundary="WordBoundary")
            words: list[dict] = []
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        words.append(
                            {
                                "start": chunk["offset"] / 1e7,
                                "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                                "text": chunk["text"],
                            }
                        )
            return words

        return asyncio.run(_generate())

    @staticmethod
    def _build_narration_timeline(specs: list[dict], segments_dir: Path, output_path: Path) -> None:
        """Builds one continuous local narration track from per-beat
        pre-recorded audio, preserving Beat boundaries exactly: each entry
        in `specs` (`{"duration": float, "path": str | None}`, one per
        Beat, in order) occupies exactly `duration` seconds in the output
        -- its own audio (silence-padded if shorter -- validating it isn't
        *longer* is the caller's job, see composition_render.py's
        preflight) or pure silence if `path` is None. This is what makes
        local narration a drop-in replacement for _run_narration's output:
        the same single "one narration file" contract _mix_audio already
        expects, so nothing downstream needs to change.
        """
        segments_dir.mkdir(parents=True, exist_ok=True)
        segment_paths: list[Path] = []
        for index, spec in enumerate(specs):
            duration = float(spec["duration"])
            source_path = spec.get("path")
            segment_path = segments_dir / f"segment_{index:03d}.m4a"
            if source_path:
                VideoComposerService._run_ffmpeg(
                    [
                        "-i", str(source_path),
                        "-af", f"apad=whole_dur={duration}",
                        "-t", str(duration),
                        "-c:a", "aac",
                        str(segment_path),
                    ]
                )
            else:
                VideoComposerService._run_ffmpeg(
                    [
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                        "-t", str(duration),
                        "-c:a", "aac",
                        str(segment_path),
                    ]
                )
            segment_paths.append(segment_path)

        if not segment_paths:
            # No beats at all -- shouldn't happen (an empty CompositionPlan
            # is already rejected before rendering starts), but produce a
            # trivially short silent file rather than leaving no narration
            # input at all for _mix_audio to read.
            VideoComposerService._run_ffmpeg(
                ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1", "-c:a", "aac", str(output_path)]
            )
            return

        concat_list = segments_dir / "concat.txt"
        concat_list.write_text(
            # ffmpeg's concat demuxer resolves relative "file" entries
            # against the *list file's own directory*, not the process cwd.
            # segment_path is relative to cwd (job_dir is built from a
            # relative library root) -- writing that same relative path
            # verbatim doubles it up with segments_dir's own path, producing
            # a nonexistent nested path. Resolve to an absolute path instead.
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths), encoding="utf-8"
        )
        VideoComposerService._run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)]
        )

    @staticmethod
    def _group_words_into_lines(words: list[dict]) -> list[list[dict]]:
        lines: list[list[dict]] = []
        current: list[dict] = []
        for word in words:
            if current:
                gap = word["start"] - current[-1]["end"]
                would_be_duration = word["end"] - current[0]["start"]
                if (
                    gap > LINE_BREAK_GAP_SEC
                    or len(current) >= MAX_WORDS_PER_LINE
                    or would_be_duration > MAX_LINE_DURATION_SEC
                ):
                    lines.append(current)
                    current = []
            current.append(word)
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds % 1) * 1000))
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _rounded_rect_drawing(w: float, h: float, r: float) -> str:
        """ASS \\p vector-drawing path for a filled rounded rectangle spanning
        (0,0) to (w,h) -- used as the highlight box behind the active word."""
        r = min(r, w / 2, h / 2)
        return (
            f"m {r:.1f} 0 "
            f"l {w - r:.1f} 0 "
            f"b {w:.1f} 0 {w:.1f} 0 {w:.1f} {r:.1f} "
            f"l {w:.1f} {h - r:.1f} "
            f"b {w:.1f} {h:.1f} {w:.1f} {h:.1f} {w - r:.1f} {h:.1f} "
            f"l {r:.1f} {h:.1f} "
            f"b 0 {h:.1f} 0 {h:.1f} 0 {h - r:.1f} "
            f"l 0 {r:.1f} "
            f"b 0 0 0 0 {r:.1f} 0"
        )

    @staticmethod
    def _split_line_for_width(line: list[dict], font: ImageFont.FreeTypeFont, space_width: float, available_width: float) -> list[list[dict]]:
        """Re-break a line's words wherever the cumulative rendered width
        would exceed the box a single unwrapped row can occupy. The box
        layout below assumes each `line` it's handed renders on exactly one
        row -- libass's own auto-wrap can't be relied on for that (it wraps
        at whatever width fits, independent of these word-timed boxes), so
        wrapping has to happen here, using the same width math."""
        rows: list[list[dict]] = []
        current: list[dict] = []
        current_width = 0.0
        for word in line:
            word_width = font.getlength(word["text"])
            added = word_width if not current else word_width + space_width
            if current and current_width + added > available_width:
                rows.append(current)
                current = []
                added = word_width
                current_width = 0.0
            current.append(word)
            current_width += added
        if current:
            rows.append(current)
        return rows

    def _write_subtitles(
        self,
        lines: list[list[dict]],
        ass_path: Path,
        srt_path: Path,
        width: int,
        height: int,
        font_size: int,
        caption_preset: str = "emotional",
    ) -> None:
        """Burns word-timed captions to `ass_path` (+ a plain `srt_path`
        alongside, unchanged regardless of preset -- it's a reference/
        accessibility artifact, not what actually gets burned in), styled
        per `caption_preset`. All 5 presets share the same word-boundary
        timing data and the same `_split_line_for_width` row-wrapping --
        only the Dialogue layout strategy and ASS Style differ. "emotional"
        is exactly the original, already-shipped karaoke-highlight-box
        behavior (see 17-karaoke-highlight-box.md), now one case among five
        instead of the only option.
        """
        if caption_preset not in CAPTION_PRESET_CONFIG:
            raise ValueError(f"Unknown caption preset {caption_preset!r}, must be one of {CAPTION_PRESETS}")
        config = CAPTION_PRESET_CONFIG[caption_preset]

        scaled_font_size = max(20, int(font_size * config["font_scale"]))
        font_path = FONT_PATH_BOLD if config["font_bold"] else FONT_PATH
        font = ImageFont.truetype(font_path, scaled_font_size)
        space_width = font.getlength(" ")
        margin_x = 40
        margin_v = int(height * config["margin_v_frac"])
        available_width = width - 2 * margin_x

        if caption_preset == "emotional":
            ass_lines = self._ass_events_emotional(lines, font, space_width, available_width, width, margin_v, scaled_font_size)
        elif caption_preset == "word_highlight":
            ass_lines = self._ass_events_word_highlight(lines, font, space_width, available_width)
        elif caption_preset in ("cinematic", "top"):
            # "top" is the same plain, unadorned static-line layout as
            # "cinematic" -- only the Style's own alignment/margin/font_scale
            # (set via CAPTION_PRESET_CONFIG above) differ.
            ass_lines = self._ass_events_static_lines(lines, font, space_width, available_width)
        elif caption_preset == "big_statement":
            ass_lines = self._ass_events_big_statement(lines)
        else:  # "quote"
            ass_lines = self._ass_events_quote(lines, font, space_width, available_width)

        style_line = (
            f"Style: Karaoke,Arial,{scaled_font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"{1 if config['font_bold'] else 0},{1 if config['italic'] else 0},0,0,100,100,0,0,1,3,0,"
            f"{config['alignment']},{margin_x},{margin_x},{margin_v},1"
        )
        ass_content = (
            f"""[Script Info]
Title: Phu de {caption_preset}
ScriptType: v4.00+
WrapStyle: 2
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            + "\n".join(ass_lines)
            + "\n"
        )
        ass_path.write_text(ass_content, encoding="utf-8")

        srt_lines = []
        for i, line in enumerate(lines, start=1):
            plain_text = " ".join(word["text"] for word in line)
            srt_lines.append(
                f"{i}\n{self._format_srt_time(line[0]['start'])} --> "
                f"{self._format_srt_time(line[-1]['end'])}\n{plain_text}\n"
            )
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    def _ass_events_emotional(
        self,
        lines: list[list[dict]],
        font: ImageFont.FreeTypeFont,
        space_width: float,
        available_width: float,
        width: int,
        margin_v: int,
        font_size: int,
    ) -> list[str]:
        """The original karaoke-highlight-box preset (see
        17-karaoke-highlight-box.md), unchanged: a solid rounded box slides
        behind whichever word is being spoken; text itself stays plain
        white. The box needs a real x position per word, which ASS's \\k
        tag can't give us (it only fills left-to-right inside one Dialogue
        line) -- so word widths are measured with the same bold TTF the
        Style below renders with, laid out left-to-right around the row's
        centred x, and each word gets its own timed Dialogue event carrying
        just the box (Layer 0, drawn first/behind). The row's text is a
        second, separate Dialogue spanning the whole row (Layer 1, on top).
        """
        box_height = font_size * 1.35
        box_top = margin_v - font_size * 0.14
        pad_x = font_size * 0.22
        radius = font_size * 0.22

        ass_lines = []
        for line in lines:
            for row in self._split_line_for_width(line, font, space_width, available_width):
                row_start = row[0]["start"]
                row_end = row[-1]["end"]
                plain_text = " ".join(word["text"] for word in row)

                word_widths = [font.getlength(word["text"]) for word in row]
                total_width = sum(word_widths) + space_width * (len(row) - 1)
                cursor_x = width / 2 - total_width / 2
                color = random.choice(HIGHLIGHT_COLORS)
                for word, word_width in zip(row, word_widths):
                    box_x = cursor_x - pad_x
                    box_w = word_width + pad_x * 2
                    drawing = self._rounded_rect_drawing(box_w, box_height, radius)
                    ass_lines.append(
                        f"Dialogue: 0,{self._format_ass_time(word['start'])},{self._format_ass_time(word['end'])},"
                        f"Karaoke,,0,0,0,,{{\\an7\\pos({box_x:.1f},{box_top:.1f})\\bord0\\shad0"
                        f"\\1c&H{color}&\\1a&H00&\\p1}}{drawing}{{\\p0}}"
                    )
                    cursor_x += word_width + space_width

                ass_lines.append(
                    f"Dialogue: 1,{self._format_ass_time(row_start)},{self._format_ass_time(row_end)},"
                    f"Karaoke,,0,0,0,,{plain_text}"
                )
        return ass_lines

    def _ass_events_word_highlight(
        self,
        lines: list[list[dict]],
        font: ImageFont.FreeTypeFont,
        space_width: float,
        available_width: float,
    ) -> list[str]:
        """Simpler alternative to "emotional": no box, just recolours the
        active word inline within the row's own text via an ASS `\\c`
        override, reset back to white immediately after -- one Dialogue
        event per word, each carrying the full row so the rest of the row
        is visible throughout, not just the active word.
        """
        ass_lines = []
        for line in lines:
            for row in self._split_line_for_width(line, font, space_width, available_width):
                words_text = [word["text"] for word in row]
                for i, word in enumerate(row):
                    color = random.choice(HIGHLIGHT_COLORS)
                    rendered = " ".join(
                        f"{{\\c&H{color}&}}{text}{{\\c&HFFFFFF&}}" if j == i else text
                        for j, text in enumerate(words_text)
                    )
                    ass_lines.append(
                        f"Dialogue: 0,{self._format_ass_time(word['start'])},{self._format_ass_time(word['end'])},"
                        f"Karaoke,,0,0,0,,{rendered}"
                    )
        return ass_lines

    def _ass_events_static_lines(
        self,
        lines: list[list[dict]],
        font: ImageFont.FreeTypeFont,
        space_width: float,
        available_width: float,
    ) -> list[str]:
        """"cinematic" preset: clean, elegant movie-subtitle look -- one
        static Dialogue per row spanning its whole start..end span, no
        per-word timing/animation at all.
        """
        ass_lines = []
        for line in lines:
            for row in self._split_line_for_width(line, font, space_width, available_width):
                plain_text = " ".join(word["text"] for word in row)
                ass_lines.append(
                    f"Dialogue: 0,{self._format_ass_time(row[0]['start'])},{self._format_ass_time(row[-1]['end'])},"
                    f"Karaoke,,0,0,0,,{plain_text}"
                )
        return ass_lines

    @staticmethod
    def _ass_events_big_statement(lines: list[list[dict]]) -> list[str]:
        """"big_statement" preset: one or two words at a time, upper-cased,
        for a fast-cut, high-impact look -- position/size come entirely
        from the Style block (large font, middle-center alignment), not
        per-event overrides.
        """
        ass_lines = []
        for line in lines:
            for i in range(0, len(line), 2):
                chunk = line[i : i + 2]
                text = " ".join(word["text"] for word in chunk).upper()
                ass_lines.append(
                    f"Dialogue: 0,{VideoComposerService._format_ass_time(chunk[0]['start'])},"
                    f"{VideoComposerService._format_ass_time(chunk[-1]['end'])},Karaoke,,0,0,0,,{text}"
                )
        return ass_lines

    def _ass_events_quote(
        self,
        lines: list[list[dict]],
        font: ImageFont.FreeTypeFont,
        space_width: float,
        available_width: float,
    ) -> list[str]:
        """"quote" preset: each row wrapped in curly quotation marks; the
        Style block sets Italic=1 for the elegant look. Reuses row-wrapping
        (rather than showing a whole `line` unbroken) so a long narration
        chunk still fits the frame width.
        """
        ass_lines = []
        for line in lines:
            for row in self._split_line_for_width(line, font, space_width, available_width):
                plain_text = " ".join(word["text"] for word in row)
                ass_lines.append(
                    f"Dialogue: 0,{self._format_ass_time(row[0]['start'])},{self._format_ass_time(row[-1]['end'])},"
                    f"Karaoke,,0,0,0,,“{plain_text}”"
                )
        return ass_lines

    # --- audio mixing + final composition -----------------------------------

    def _mix_audio(
        self,
        narration_path: Path,
        music_path: str | None,
        music_volume: float,
        narration_volume: float,
        music_ducking_ratio: float,
        fade_in_sec: float,
        fade_out_sec: float,
        video_duration: float,
        output_path: Path,
        sfx_cues: list[dict] | None = None,
    ) -> None:
        """Mixes narration (always present) with optional background music
        (ducked under narration via ffmpeg's sidechaincompress -- real,
        dynamic ducking keyed off the narration's own level, not just a
        lower static volume) and optional SFX cues (each played once,
        delayed to its own start offset), then applies optional fade in/out
        to the combined result. `-t {video_duration}` on the output is the
        same hard, deterministic-duration safety net the original version
        of this method already used -- unchanged regardless of how many
        optional layers are mixed in.
        """
        sfx_cues = sfx_cues or []

        inputs: list[str] = ["-i", str(narration_path)]
        # apad's own default (no explicit target) pads only a small,
        # ffmpeg-internal amount -- not reliably "the rest of video_duration"
        # once amix/sidechaincompress are also in the graph (confirmed by a
        # real test failure while building this pipeline: narration+music
        # with a multi-second gap between narration and video length
        # silently truncated to narration's own raw length instead of
        # video_duration). whole_dur makes the target explicit and
        # deterministic regardless of what else is in the filter chain.
        filters: list[str] = [f"[0:a]volume={narration_volume},apad=whole_dur={video_duration}[narration]"]
        mix_labels = ["narration"]
        next_index = 1

        if music_path:
            inputs += ["-stream_loop", "-1", "-i", music_path]
            filters.append(f"[{next_index}:a]volume={music_volume}[music_pre]")
            # sidechaincompress: music (main input) is compressed using
            # narration (sidechain input) as the trigger -- music level
            # drops automatically whenever narration is actually speaking,
            # and returns to normal during silence. threshold/attack/release
            # are fixed, sensible defaults for speech-over-music; `ratio`
            # (ffmpeg's own parameter, 1.0=no effect..20.0=max) is the one
            # knob exposed as music_ducking_ratio.
            filters.append(
                f"[music_pre][narration]sidechaincompress=threshold=0.05:"
                f"ratio={music_ducking_ratio}:attack=5:release=300[ducked]"
            )
            mix_labels.append("ducked")
            next_index += 1

        for i, cue in enumerate(sfx_cues):
            inputs += ["-i", str(cue["path"])]
            delay_ms = max(0, int(round(cue.get("start_sec", 0.0) * 1000)))
            cue_volume = cue.get("volume", 1.0)
            label = f"sfx{i}"
            filters.append(f"[{next_index}:a]volume={cue_volume},adelay={delay_ms}|{delay_ms}[{label}]")
            mix_labels.append(label)
            next_index += 1

        if len(mix_labels) > 1:
            mix_inputs = "".join(f"[{label}]" for label in mix_labels)
            filters.append(f"{mix_inputs}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[mixed]")
            last_label = "mixed"
        else:
            last_label = "narration"

        # Final apad=whole_dur, always applied: sidechaincompress was found
        # (by a real test failure while building this pipeline) to truncate
        # its output back to narration's *raw*, pre-padding length even
        # when fed an already-apad-padded sidechain input -- padding
        # narration alone before compression isn't reliably enough. Padding
        # the fully-combined output here, right before the end, is: whole_dur
        # only ever *adds* silence if the stream is shorter than
        # video_duration, never trims, so it's a safe no-op once the stream
        # is already long enough. The outer -t below remains the final trim.
        final_ops = [f"apad=whole_dur={video_duration}"]
        if fade_in_sec > 0:
            final_ops.append(f"afade=t=in:st=0:d={fade_in_sec}")
        if fade_out_sec > 0:
            fade_out_start = max(0.0, video_duration - fade_out_sec)
            final_ops.append(f"afade=t=out:st={fade_out_start}:d={fade_out_sec}")
        filters.append(f"[{last_label}]{','.join(final_ops)}[a]")

        self._run_ffmpeg(
            inputs
            + [
                "-filter_complex", ";".join(filters),
                "-map", "[a]",
                "-t", str(video_duration),
                str(output_path),
            ]
        )

    @staticmethod
    def _escape_for_ffmpeg_filter(path: Path) -> str:
        return path.resolve().as_posix().replace(":", "\\:")

    def _finalize(
        self,
        merged_video: Path,
        audio_path: Path,
        title: str,
        subtitle_ass: Path,
        burn_subtitles: bool,
        output_path: Path,
        width: int,
    ) -> None:
        video_filters = []

        title_font_size = max(28, int(width * 0.05))
        title_escaped = title.replace(":", "\\:").replace("'", "\\'")
        font_escaped = FONT_PATH.replace(":", "\\:")
        video_filters.append(
            f"drawtext=fontfile='{font_escaped}':text='{title_escaped}':"
            f"fontsize={title_font_size}:fontcolor=white:borderw=3:bordercolor=black@0.6:"
            f"box=1:boxcolor=black@0.4:boxborderw={int(title_font_size * 0.35)}:"
            f"x=(w-text_w)/2:y=h*0.02"
        )

        if burn_subtitles:
            video_filters.append(f"subtitles='{self._escape_for_ffmpeg_filter(subtitle_ass)}'")

        self._run_ffmpeg(
            [
                "-i", str(merged_video),
                "-i", str(audio_path),
                "-filter_complex", f"[0:v]{','.join(video_filters)}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                # Without an explicit output pixel format, libx264 just
                # keeps whatever the filter chain produced -- drawtext/
                # subtitles here can end up yuv444p depending on the input,
                # which is invalid/unplayable on plenty of real players
                # (this is a real, previously-undetected bug: no test ever
                # checked the *final* output's pixel format before -- see
                # docs/features/35-multi-beat-composition.md). yuv420p is
                # this app's own documented final-output spec everywhere
                # else (Task 06's motion renderer, Task 10's golden sample).
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-shortest",
                str(output_path),
            ]
        )

    @staticmethod
    def _write_render_metadata(
        final_video: Path,
        video_duration: float,
        render_seconds: float,
        *,
        width: int,
        height: int,
        fps: float,
        clip_count: int,
    ) -> None:
        """Lightweight render metadata (Video Factory Epic, Task 10, +width/
        height/fps/clip_count in Task 34) -- a JSON sidecar next to the
        finished video, not a new DB column or a billing system. `ai_cost`
        is always 0.0 here: this pipeline's only "AI" step is `edge_tts`
        narration, which is Microsoft's free, unofficial API (no key, no
        billed usage) -- see docs/features/28-video-factory-e2e-pipeline.md
        for why a nonzero cost would only make sense once a *paid* provider
        (e.g. a real AI image/video generator) is ever wired in, which this
        app's RenderPolicy (app/core/render_policy.py) currently forbids
        anyway. `clip_count` is this job's own vocabulary (it renders
        `clip_paths`, plural inputs -- it has no notion of a "Beat"); for a
        Video-Factory-originated job this is exactly the beat count.
        """
        metadata = {
            "render_time_seconds": round(render_seconds, 2),
            "ai_cost": 0.0,
            "render_mode": "local",
            "duration": round(video_duration, 2),
            "output_size_mb": round(final_video.stat().st_size / (1024 * 1024), 2),
            "width": width,
            "height": height,
            "fps": fps,
            "clip_count": clip_count,
        }
        metadata_path = final_video.with_name("render_metadata.json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    @staticmethod
    def _validate_final_output(path: Path, *, expected_duration: float, width: int, height: int, fps: float) -> None:
        """Final validation (Task 10 hardening -- see
        docs/features/37-e2e-pipeline-hardening.md): a render only counts as
        successful once its actual output file is inspected with ffprobe,
        not merely because every ffmpeg subprocess in the pipeline exited
        with code 0 (a prior real bug -- yuv444p output that no test or
        runtime check ever caught, see docs/features/35-multi-beat-composition.md
        -- shows exit-code-0 alone isn't enough).

        Validates against `width`/`height`/`fps` (already probed from this
        job's own clip_paths[0] and passed to every ffmpeg call in this
        pipeline) rather than a hardcoded app.core.render_profile.RenderProfile
        -- the plain upload-based Video Composer flow (unlike Video Factory)
        legitimately renders whatever resolution its input clips already
        are, so validating self-consistently ("did the pipeline actually
        produce what it told ffmpeg to produce") is correct for every job,
        Video-Factory-originated or not. Video/audio codec and pixel format
        are validated against fixed constants because _finalize's ffmpeg
        command hardcodes them the same way for every job regardless of
        caller (`-c:v libx264 -pix_fmt yuv420p -c:a aac`).

        Caption "burned in" verification is NOT attempted here: ffprobe can
        report streams/codecs/duration but has no way to confirm burned-in
        pixels actually contain readable text, and this codebase has no
        OCR/frame-inspection tooling. The nearest available guarantee is
        that `_write_subtitles` succeeded and `_finalize`'s `subtitles=`
        filter ran without ffmpeg raising -- both already required for this
        method to even be reached.
        """
        if not path.exists():
            raise RuntimeError(f"{render_errors.OUTPUT_VALIDATION_FAILED}: rendered file does not exist: {path}")

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: ffprobe failed on rendered output: "
                f"{probe.stderr.strip()[-500:]}"
            )
        try:
            data = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: ffprobe returned unparsable output for {path}"
            ) from exc

        streams = data.get("streams", [])
        # Section 42: exactly one video stream, exactly one audio stream --
        # not merely "at least one." Every caller of this method always
        # explicitly `-map`s exactly one video + one audio stream (never a
        # blanket `-map 0`), so this is a real guarantee, not just a hope.
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        if len(video_streams) != 1:
            raise RuntimeError(
                f"{render_errors.FINAL_STREAM_INVALID}: expected exactly 1 video stream, found {len(video_streams)}"
            )
        video_stream = video_streams[0]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        if len(audio_streams) != 1:
            raise RuntimeError(
                f"{render_errors.FINAL_STREAM_INVALID}: expected exactly 1 audio stream, found {len(audio_streams)}"
            )
        audio_stream = audio_streams[0]

        try:
            actual_duration = float(data.get("format", {}).get("duration", 0.0))
        except (TypeError, ValueError):
            actual_duration = 0.0
        diff = abs(actual_duration - expected_duration)
        logger.info(
            "Duration validation: expected=%.2fs actual=%.2fs diff=%.2fs (tolerance=%.2fs)",
            expected_duration, actual_duration, diff, _OUTPUT_DURATION_TOLERANCE_SEC,
        )
        if actual_duration <= 0:
            raise RuntimeError(f"{render_errors.OUTPUT_VALIDATION_FAILED}: rendered output has zero/invalid duration")
        if diff > _OUTPUT_DURATION_TOLERANCE_SEC:
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: rendered duration {actual_duration:.2f}s differs from "
                f"expected {expected_duration:.2f}s by {diff:.2f}s (tolerance {_OUTPUT_DURATION_TOLERANCE_SEC}s)"
            )

        if int(video_stream.get("width", 0)) != width or int(video_stream.get("height", 0)) != height:
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: resolution "
                f"{video_stream.get('width')}x{video_stream.get('height')} does not match expected {width}x{height}"
            )
        num, _, den = str(video_stream.get("r_frame_rate", "0/1")).partition("/")
        try:
            actual_fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            actual_fps = 0.0
        if actual_fps <= 0 or abs(actual_fps - fps) > 0.5:
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: fps {actual_fps} does not match expected {fps}"
            )
        if video_stream.get("codec_name") != "h264":
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: video codec {video_stream.get('codec_name')!r} != h264"
            )
        if video_stream.get("pix_fmt") != "yuv420p":
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: pixel format {video_stream.get('pix_fmt')!r} != yuv420p"
            )
        if audio_stream.get("codec_name") != "aac":
            raise RuntimeError(
                f"{render_errors.OUTPUT_VALIDATION_FAILED}: audio codec {audio_stream.get('codec_name')!r} != aac"
            )

    @staticmethod
    def _write_render_report(
        library_dir: Path,
        job_id: int,
        *,
        status: str,
        final_video: Path | None = None,
        video_duration: float | None = None,
        clip_count: int | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
        caption_enabled: bool = False,
        narration_mode: str = "tts",
        timing: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        failed_phase: str | None = None,
    ) -> None:
        """Writes `.render/job_<id>/report.json` under the app's own
        library_dir (Task 10 -- see docs/features/37-e2e-pipeline-hardening.md),
        independent of `requested_output_dir` (which may be an external,
        user-chosen folder that's fine for the final video but shouldn't
        also be where this app stores its own render bookkeeping). On
        success this is a superset of the pre-existing `render_metadata.json`
        sidecar (_write_render_metadata, unchanged, still written next to
        the video for backward compatibility) -- this method additionally
        tracks external API accounting and per-phase timing, and also
        writes on *failure*, which render_metadata.json never did.

        `external_api_calls`/`external_api_cost_estimate`: this pipeline's
        only external network call is edge_tts narration (narration_mode=
        "tts"). Per this task's own explicit accounting rules, an
        unofficial free API is still an external call (1), with an honestly
        unknown cost (null) -- not invented, not silently reported as the
        old always-0.0 `ai_cost` did. Local narration (narration_mode=
        "local") makes zero external calls, so both fields are 0. Task 26's
        own "precomposed" mode (see docs/features/52-final-composer.md)
        makes zero external calls here too -- narration/BGM/captions were
        all already produced locally by earlier Factory stages before this
        job ever started; a real bug (this method originally treated any
        narration_mode other than "local" as needing 1 external call,
        mis-billing every precomposed render) caught by manual verification.
        """
        report_dir = library_dir / ".render" / f"job_{job_id}"
        report_dir.mkdir(parents=True, exist_ok=True)

        if status == "completed":
            external_api_calls = 0 if narration_mode in ("local", "precomposed") else 1
            report = {
                "status": "completed",
                "job_id": job_id,
                "job": {"id": job_id, "status": "completed"},
                "video": {
                    "path": str(final_video),
                    "duration": round(video_duration, 2),
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "size_bytes": final_video.stat().st_size,
                },
                "beats": clip_count,
                "captions": caption_enabled,
                "external_api_calls": external_api_calls,
                "external_api_cost_estimate": 0 if external_api_calls == 0 else None,
                "timing": timing or {},
            }
        else:
            # "failed" or "cancelled" (Task 11) -- same shape either way,
            # per this task's own "do not create a second report format"
            # instruction; error_code/message are simply None for a
            # cancellation, which was never an error.
            report = {
                "status": status,
                "job_id": job_id,
                "job": {"id": job_id, "status": status},
                "error_code": error_code,
                "message": error_message,
                "failed_phase": failed_phase,
                "timing": timing or {},
            }
        (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    def _log(self, job_id: int, message: str) -> None:
        """`.render/job_<id>/render.log` (Task 11 -- see
        docs/features/38-render-job-hardening.md): a dedicated, append-only
        log per job, next to its report.json. Deliberately small (phase
        lifecycle only, one line each -- job started/phase started/phase
        completed/job completed) rather than a full ffmpeg-stderr transcript:
        that's already captured on failure (error_message/report.json's
        "message", plus this process's own `logger.exception` output) --
        duplicating raw stderr into a third location wasn't worth the extra
        surface area for this task. Never logs secrets/API keys -- there
        are none anywhere in this pipeline's ffmpeg-only, local-only
        commands to begin with.
        """
        log_dir = self._library_dir / ".render" / f"job_{job_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with open(log_dir / "render.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def _publish(self, event_name: str, payload: dict) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_name, payload)

    def _is_cancelled(self, job_id: int) -> bool:
        event = self._cancel_events.get(job_id)
        return event is not None and event.is_set()

    def _register_process(self, job_id: int, process: subprocess.Popen) -> None:
        """Tracks the ffmpeg subprocess a job currently owns, so cancel_job
        can terminate it immediately instead of only at the next phase/beat
        checkpoint -- see BeatRenderer's `register_process` callback
        (composition_render.render_beats_for_job is the real caller).
        """
        with self._runtime_lock:
            self._active_processes[job_id] = process

    def _unregister_process(self, job_id: int) -> None:
        with self._runtime_lock:
            self._active_processes.pop(job_id, None)

    def _set_fields(self, job_id: int, **fields) -> None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            db.commit()
        finally:
            db.close()

    def _fail_job(self, job_id: int, failed_phase: str, message: str, timing: dict | None = None) -> None:
        error_code = render_errors.PHASE_TO_ERROR_CODE.get(failed_phase, render_errors.RENDER_FAILED)
        self._set_status(job_id, "failed", error_message=message)
        self._write_render_report(
            self._library_dir, job_id, status="failed",
            error_code=error_code, error_message=message, failed_phase=failed_phase, timing=timing,
        )
        self._log(job_id, f"job failed in phase {failed_phase}: {message}")
        self._publish("render.job.failed", {"job_id": job_id, "error_code": error_code, "phase": failed_phase})

    def _finish_cancelled(self, job_id: int, cancelled_phase: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            if job is not None:
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()
        # Never delete source assets/library files -- only this job's own
        # scratch space (motion clips it rendered, ffmpeg tmp files).
        shutil.rmtree(self.job_dir(job_id) / "scenes", ignore_errors=True)
        shutil.rmtree(self.job_dir(job_id) / "tmp", ignore_errors=True)
        self._write_render_report(
            self._library_dir, job_id, status="cancelled", failed_phase=cancelled_phase, timing={}
        )
        self._log(job_id, f"job cancelled in phase {cancelled_phase}")
        self._publish("render.job.cancelled", {"job_id": job_id, "phase": cancelled_phase})

    # --- status/recovery -----------------------------------------------------

    def _get_status(self, job_id: int) -> str | None:
        db = SessionLocal()
        try:
            job = db.get(VideoComposeJob, job_id)
            return job.status if job is not None else None
        finally:
            db.close()

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
        self._publish("render.job.phase_changed", {"job_id": job_id, "status": status})

    def _recover_pending_jobs(self) -> None:
        """Startup recovery (Task 11 -- see
        docs/features/38-render-job-hardening.md). A job still "queued"
        never actually started -- safe to just re-queue, same as before
        this task. A job in any other PENDING_STATUSES value was genuinely
        RUNNING when the process died: an ffmpeg encode killed mid-write
        can leave corrupt/partial intermediates (unlike a resumable HTTP
        download, which is why app.services.download.engine.DownloadEngine's
        equivalent recovery silently re-queues instead), so these are
        marked FAILED with error_code=RENDER_INTERRUPTED instead -- an
        explicit, informed user Retry (see retry_job) is safer than an
        automatic silent re-run.
        """
        db = SessionLocal()
        try:
            queued = db.query(VideoComposeJob).filter(VideoComposeJob.status == "queued").all()
            queued_ids = [job.id for job in queued]

            interrupted = db.query(VideoComposeJob).filter(VideoComposeJob.status.in_(_RUNNING_STATUSES)).all()
            interrupted_ids = [job.id for job in interrupted]
            for job in interrupted:
                job.status = "failed"
                job.error_message = "Render was interrupted by an application restart."
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        for job_id in interrupted_ids:
            self._write_render_report(
                self._library_dir, job_id, status="failed",
                error_code=render_errors.RENDER_INTERRUPTED,
                error_message="Render was interrupted by an application restart.",
                failed_phase="unknown", timing={},
            )
            self._log(job_id, "job recovered as failed: interrupted by application restart")

        for job_id in queued_ids:
            self._queue.put(job_id)
