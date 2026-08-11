import json
import logging
import queue
import random
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import edge_tts
from PIL import ImageFont

from app.db.session import SessionLocal
from app.modules.video_composer.models import CAPTION_PRESETS, VideoComposeClip, VideoComposeJob

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
}
assert set(CAPTION_PRESET_CONFIG) == set(CAPTION_PRESETS)


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
        narration_volume: float = 1.0,
        music_ducking_ratio: float = 8.0,
        fade_in_sec: float = 0.0,
        fade_out_sec: float = 0.0,
        caption_preset: str = "emotional",
        sfx_cues: list[dict] | None = None,
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
            narration_volume = job.narration_volume
            music_ducking_ratio = job.music_ducking_ratio
            fade_in_sec = job.fade_in_sec
            fade_out_sec = job.fade_out_sec
            caption_preset = job.caption_preset
            sfx_cues = job.sfx_cues
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

        render_start = time.monotonic()
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
            self._write_subtitles(lines, subtitle_ass, subtitle_srt, width, height, font_size, caption_preset)

            self._set_status(job_id, "mixing_audio")
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

            self._set_status(job_id, "finalizing")
            self._finalize(merged_video, mixed_audio, title, subtitle_ass, burn_subtitles, final_video, width)
        except Exception as exc:
            logger.exception("Video-compose job %s failed", job_id)
            self._set_status(job_id, "failed", error_message=str(exc))
            return
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        render_seconds = time.monotonic() - render_start
        self._write_render_metadata(final_video, video_duration, render_seconds)

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
        elif caption_preset == "cinematic":
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
                "-c:a", "aac",
                "-shortest",
                str(output_path),
            ]
        )

    @staticmethod
    def _write_render_metadata(final_video: Path, video_duration: float, render_seconds: float) -> None:
        """Lightweight render metadata (Video Factory Epic, Task 10) -- a
        JSON sidecar next to the finished video, not a new DB column or a
        billing system. `ai_cost` is always 0.0 here: this pipeline's only
        "AI" step is `edge_tts` narration, which is Microsoft's free,
        unofficial API (no key, no billed usage) -- see
        docs/features/28-video-factory-e2e-pipeline.md for why a nonzero
        cost would only make sense once a *paid* provider (e.g. a real AI
        image/video generator) is ever wired in, which this app's
        RenderPolicy (app/core/render_policy.py) currently forbids anyway.
        """
        metadata = {
            "render_time_seconds": round(render_seconds, 2),
            "ai_cost": 0.0,
            "render_mode": "local",
            "duration": round(video_duration, 2),
            "output_size_mb": round(final_video.stat().st_size / (1024 * 1024), 2),
        }
        metadata_path = final_video.with_name("render_metadata.json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

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
