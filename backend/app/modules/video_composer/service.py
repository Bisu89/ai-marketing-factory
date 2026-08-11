import logging
import queue
import random
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import edge_tts
from PIL import ImageFont

from app.db.session import SessionLocal
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("queued", "merging", "narrating", "subtitling", "mixing_audio", "finalizing")

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
        script_text: str,
        voice: str,
        music_volume: float,
        transition_duration: float,
        burn_subtitles: bool,
        requested_output_dir: str | None,
    ) -> int:
        db = SessionLocal()
        try:
            job = VideoComposeJob(
                title=title,
                script_text=script_text,
                voice=voice,
                music_volume=music_volume,
                transition_duration=transition_duration,
                burn_subtitles=burn_subtitles,
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
            script_text = job.script_text
            voice = job.voice
            music_path = job.music_path
            music_volume = job.music_volume
            transition_duration = job.transition_duration
            burn_subtitles = job.burn_subtitles
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
        narration_audio = tmp_dir / "narration.mp3"
        mixed_audio = tmp_dir / "mixed_audio.m4a"
        subtitle_ass = output_dir / "phu_de_karaoke.ass"
        subtitle_srt = output_dir / "phu_de.srt"
        final_video = output_dir / "video_hoan_chinh.mp4"

        try:
            self._set_status(job_id, "merging")
            width, height, fps = self._probe_video_info(clip_paths[0])
            if len(clip_paths) > 1:
                self._merge_clips_with_transitions(clip_paths, merged_video, transition_duration, width, height, fps)
            else:
                # A single clip has nothing to transition into -- skip the
                # ffmpeg scale/pad/concat pass entirely and feed the
                # original upload straight into narration/subtitle/finalize.
                # Saves a redundant re-encode and keeps the source quality.
                merged_video = clip_paths[0]

            self._set_status(job_id, "narrating")
            words = self._run_narration(script_text, voice, narration_audio)

            self._set_status(job_id, "subtitling")
            lines = self._group_words_into_lines(words)
            font_size = max(28, int(height * 0.045))
            self._write_subtitles(lines, subtitle_ass, subtitle_srt, width, height, font_size)

            self._set_status(job_id, "mixing_audio")
            video_duration = self._probe_duration(merged_video)
            self._mix_audio(narration_audio, music_path, music_volume, video_duration, mixed_audio)

            self._set_status(job_id, "finalizing")
            self._finalize(merged_video, mixed_audio, title, subtitle_ass, burn_subtitles, final_video, width)
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
            job.subtitle_srt_path = str(subtitle_srt)
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
    ) -> None:
        # Trend-style captions: text stays plain white at all times: instead
        # of recolouring the spoken word (the old \k karaoke fill), a solid
        # rounded box is drawn behind whichever word is being spoken right
        # now. The box needs a real x position per word, which ASS's \k tag
        # can't give us (it only knows to fill left-to-right inside one
        # Dialogue line) -- so word widths are measured with the same bold
        # TTF (style below sets Bold=1, so this must match or the box drifts
        # off the word) libass renders with, laid out left-to-right around
        # the row's centred x, and each word gets its own timed Dialogue
        # event carrying just the box (Layer 0, drawn first / behind). The
        # row's text is a second, separate Dialogue spanning the whole row
        # (Layer 1, drawn on top) so it never itself changes color.
        font = ImageFont.truetype(FONT_PATH_BOLD, font_size)
        space_width = font.getlength(" ")
        margin_x = 40
        margin_v = int(height * 0.11)
        available_width = width - 2 * margin_x
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

        ass_content = (
            f"""[Script Info]
Title: Phu de karaoke
ScriptType: v4.00+
WrapStyle: 2
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,8,{margin_x},{margin_x},{margin_v},1

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

    # --- audio mixing + final composition -----------------------------------

    def _mix_audio(
        self,
        narration_path: Path,
        music_path: str | None,
        music_volume: float,
        video_duration: float,
        output_path: Path,
    ) -> None:
        if music_path:
            self._run_ffmpeg(
                [
                    "-i", str(narration_path),
                    "-stream_loop", "-1",
                    "-i", music_path,
                    "-filter_complex",
                    f"[0:a]apad[narration];"
                    f"[1:a]volume={music_volume}[music];"
                    f"[narration][music]amix=inputs=2:duration=first:dropout_transition=0[a]",
                    "-map", "[a]",
                    "-t", str(video_duration),
                    str(output_path),
                ]
            )
        else:
            self._run_ffmpeg(
                [
                    "-i", str(narration_path),
                    "-filter_complex", "[0:a]apad[a]",
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
                "-c:a", "aac",
                "-shortest",
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
