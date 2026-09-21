"""Storyteller background engine: its own queue + worker thread (see
app/modules/README.md -- never share VideoComposerService/SceneCutterService,
copy the shape instead). No AI call anywhere in this module -- the script
is written externally (ChatGPT, a translated novel, anything) and
paste/uploaded in as plain text; this module only does TTS + local ffmpeg
compositing.

Pipeline per episode:
  script_text -> chunk into TTS-safe segments -> edge_tts each chunk
  (-> word timestamps) -> concat into one narration track -> (optional)
  build word-timed ASS captions -> composite over a background loop
  (+ optional colour-keyed avatar overlay), 3-panel triptych, or a
  many-image slideshow (one script beat + random Ken Burns zoom per image)
  -> final.mp4
"""

from __future__ import annotations

import asyncio
import logging
import math
import queue
import random
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import NamedTuple

import edge_tts
from PIL import Image

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.storyteller.models import (
    PENDING_STATUSES,
    StorytellerAsset,
    StorytellerEpisode,
)

logger = logging.getLogger(__name__)


class _Panel(NamedTuple):
    """One resolved background/avatar/triptych-panel asset, as _process
    hands it to _composite -- decoupled from the DB row so _composite stays
    a pure function of plain values (real-ffmpeg tests build these
    directly, no DB needed)."""

    path: Path
    is_image: bool
    key_color: str | None = None


OUTPUT_WIDTH, OUTPUT_HEIGHT = 1920, 1080

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

MUSIC_VOLUME = 0.18
MUSIC_DUCKING_RATIO = 8.0

CHUNK_TARGET_CHARS = 1500
_NARRATION_MAX_ATTEMPTS = 4
_NARRATION_RETRY_BACKOFF_SEC = 1.5

_CAPTION_FONT_SIZE = 46
_CAPTION_MAX_WORDS_PER_LINE = 10
_CAPTION_LINE_BREAK_GAP_SEC = 0.6

# drawtext (disclaimer / story-info card), duplicated from
# app/modules/outro/renderer.py's own FONT_PATH/_escape_drawtext -- same
# module-isolation "duplicate, don't import" convention as elsewhere in
# this module.
_DRAWTEXT_FONT_PATH = "C:/Windows/Fonts/arialbd.ttf"
_DRAWTEXT_FONT_PATH_ESCAPED = _DRAWTEXT_FONT_PATH.replace(":", "\\:")


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    # A literal ' inside a single-quoted ffmpeg filter value can't be
    # backslash-escaped (confirmed by a real ffmpeg parse failure during
    # verification: "\\'" inside '...' does not mean "escaped quote", it
    # ends the string early and leaves the rest of the value as stray,
    # unparsed filtergraph text). The correct break-out-and-reopen form is
    # '\'' -- close the quote, an escaped quote *outside* it, reopen.
    text = text.replace("'", "'\\''")
    return text


# -- text chunking (no AI -- plain paragraph/sentence splitting) --------


def chunk_script(text: str, target_chars: int = CHUNK_TARGET_CHARS) -> list[str]:
    """Split into TTS-safe chunks on paragraph boundaries first, falling
    back to sentence boundaries for any paragraph longer than target_chars.
    A very long single call to edge_tts is both slower to retry on failure
    and, empirically, more failure-prone -- chunking bounds the blast
    radius of one bad call to one chunk."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        pieces = [para] if len(para) <= target_chars else _split_sentences(para, target_chars)
        # A "sentence" with no punctuation to split on can still come back
        # longer than target_chars (real narration text almost always has
        # punctuation, but nothing here should silently ignore the limit
        # for text that doesn't) -- hard-split on whitespace as a fallback.
        for piece in pieces:
            for sub in ([piece] if len(piece) <= target_chars else _hard_split(piece, target_chars)):
                if current and len(current) + len(sub) + 1 > target_chars:
                    chunks.append(current.strip())
                    current = ""
                current = f"{current}\n{sub}" if current else sub
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text.strip()]


def _split_sentences(paragraph: str, target_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > target_chars:
            pieces.append(current.strip())
            current = ""
        current = f"{current} {sentence}" if current else sentence
    if current.strip():
        pieces.append(current.strip())
    return pieces


def _hard_split(text: str, target_chars: int) -> list[str]:
    """Last-resort word-boundary split for a single "sentence" that's still
    over target_chars (no punctuation at all to split on)."""
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > target_chars:
            pieces.append(current)
            current = ""
        current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces or [text]


def split_into_beats(text: str, n: int) -> list[str]:
    """Split into exactly min(n, word_count) contiguous, near-equal-length
    word groups -- one beat per slideshow image, so each image's on-screen
    time tracks how much of the script narrates over it. Word-based (not
    sentence-based) so the group count is exact regardless of punctuation
    density; a beat boundary landing mid-sentence is an acceptable
    trade-off for guaranteed 1:1 alignment with the image count."""
    words = text.split()
    if not words:
        return []
    n = max(1, min(n, len(words)))
    base, extra = divmod(len(words), n)
    beats: list[str] = []
    idx = 0
    for i in range(n):
        size = base + (1 if i < extra else 0)
        beats.append(" ".join(words[idx : idx + size]))
        idx += size
    return beats


# -- ffmpeg/ffprobe helpers (duplicated, not imported -- module isolation,
# see app/modules/video_composer/ffmpeg_ops.py's own docstring for the
# identical rationale) -----------------------------------------------


def _run_ffmpeg(args: list[str]) -> None:
    command = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[-2000:]}")


def _probe_duration(path: Path) -> float:
    command = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return float(result.stdout.strip())


def _probe_video_info(path: Path) -> tuple[int, int, float]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "csv=p=0:s=x", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    width_str, height_str, fps_str = result.stdout.strip().split("x")
    num, _, den = fps_str.partition("/")
    return int(width_str), int(height_str), float(num) / float(den or 1)


def _escape_for_ffmpeg_filter(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:")


def _drawtext_filter(lines: list[str], *, y_expr: str, font_size: int = 34) -> str:
    """One drawtext filter per line (stacked), each on its own translucent
    box for readability over arbitrary background footage -- same
    multi-drawtext-per-line shape app.modules.outro.renderer uses for its
    own multi-line CTA, duplicated rather than imported."""
    filters = []
    for i, line in enumerate(lines):
        escaped = _escape_drawtext(line)
        y = f"({y_expr})+{i}*{int(font_size * 1.3)}"
        filters.append(
            f"drawtext=fontfile='{_DRAWTEXT_FONT_PATH_ESCAPED}':text='{escaped}':fontsize={font_size}:"
            f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10:x=(w-text_w)/2:y={y}"
        )
    return ",".join(filters)


def _zoompan_filter(direction: str, max_zoom: float, total_frames: int, fps: int = 30) -> str:
    """A slideshow image's Ken Burns clip: zoompan with d=1 (one output
    frame per already-looped input frame, from -loop 1 -framerate {fps})
    so 'zoom' accumulates continuously across the whole clip instead of
    resetting every d frames. step is sized so the zoom travels its full
    range (1.0<->max_zoom) over exactly this panel's own duration, so a
    short beat doesn't zoom faster/further than a long one. Centered pan
    (x/y always recentring on the current zoom window) keeps the crop
    inside the image regardless of direction, avoiding black-bar drift."""
    step = (max_zoom - 1.0) / max(total_frames, 1)
    if direction == "out":
        zoom_expr = f"if(eq(on,1),{max_zoom:.4f},max(zoom-{step:.6f},1.0))"
    else:
        zoom_expr = f"min(zoom+{step:.6f},{max_zoom:.4f})"
    return (
        f"zoompan=z='{zoom_expr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={fps}"
    )


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


def _probe_image_info(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.width, img.height


def _sample_corner_color(media_path: Path, tmp_dir: Path) -> str:
    """Read the top-left corner pixel as the avatar's background colour,
    for ffmpeg's colorkey filter. Auto-detected default; callers may
    override via StorytellerAsset.key_color afterwards. Works on a still
    image directly, or the first frame extracted from a video clip."""
    if is_image_file(media_path):
        with Image.open(media_path) as img:
            r, g, b = img.convert("RGB").getpixel((0, 0))
        return f"0x{r:02X}{g:02X}{b:02X}"

    frame_path = tmp_dir / "sample_frame.png"
    _run_ffmpeg(["-ss", "0.5", "-i", str(media_path), "-frames:v", "1", str(frame_path)])
    with Image.open(frame_path) as img:
        r, g, b = img.convert("RGB").getpixel((0, 0))
    frame_path.unlink(missing_ok=True)
    return f"0x{r:02X}{g:02X}{b:02X}"


# -- narration (edge_tts, duplicated retry shape from video_composer/
# narration.py -- same "unofficial API, intermittent NoAudioReceived"
# reasoning, module isolation means it's copied not imported) ----------


def _narrate_chunk(text: str, voice: str, rate: str, output_path: Path) -> list[dict]:
    async def _generate_once() -> list[dict]:
        communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        words: list[dict] = []
        with open(output_path, "wb") as f:
            async for event in communicate.stream():
                if event["type"] == "audio":
                    f.write(event["data"])
                elif event["type"] == "WordBoundary":
                    words.append({
                        "start": event["offset"] / 1e7,
                        "end": (event["offset"] + event["duration"]) / 1e7,
                        "text": event["text"],
                    })
        return words

    async def _generate_with_retry() -> list[dict]:
        last_exc: Exception | None = None
        for attempt in range(_NARRATION_MAX_ATTEMPTS):
            try:
                words = await _generate_once()
                if output_path.exists() and output_path.stat().st_size > 0:
                    return words
                last_exc = RuntimeError("edge_tts produced no audio bytes.")
            except Exception as exc:  # noqa: BLE001 -- retried regardless of exact exception type
                last_exc = exc
            if attempt < _NARRATION_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_NARRATION_RETRY_BACKOFF_SEC * (attempt + 1))
        raise RuntimeError(f"edge_tts failed after {_NARRATION_MAX_ATTEMPTS} attempts: {last_exc}")

    return asyncio.run(_generate_with_retry())


def _mix_narration_and_music(
    narration_path: Path,
    music_path: Path | None,
    video_duration: float,
    output_path: Path,
    music_volume: float = MUSIC_VOLUME,
    music_ducking_ratio: float = MUSIC_DUCKING_RATIO,
) -> None:
    """Narration + optional looped, ducked background music -> one audio
    track. Same sidechaincompress ducking technique as
    video_composer/audio_mix.py's mix_audio (music level drops whenever
    narration is speaking), duplicated rather than imported per this
    module's isolation convention -- simplified to narration+music only,
    no SFX cues (storyteller has no SFX concept)."""
    inputs = ["-i", str(narration_path)]
    filters = [f"[0:a]apad=whole_dur={video_duration}[narration]"]
    if music_path is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]
        filters.append(f"[1:a]volume={music_volume}[music_pre]")
        filters.append(
            f"[music_pre][narration]sidechaincompress=threshold=0.05:"
            f"ratio={music_ducking_ratio}:attack=5:release=300[ducked]"
        )
        filters.append(
            f"[narration][ducked]amix=inputs=2:duration=first:dropout_transition=0,"
            f"apad=whole_dur={video_duration}[a]"
        )
        last_label = "a"
    else:
        last_label = "narration"

    _run_ffmpeg(
        inputs
        + ["-filter_complex", ";".join(filters), "-map", f"[{last_label}]", "-t", str(video_duration), str(output_path)]
    )


# -- captions: one plain static-line style (word-grouped, bottom-third) --


def _group_words_into_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            if gap > _CAPTION_LINE_BREAK_GAP_SEC or len(current) >= _CAPTION_MAX_WORDS_PER_LINE:
                lines.append(current)
                current = []
        current.append(word)
    if current:
        lines.append(current)
    return lines


def _format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _write_captions(words: list[dict], ass_path: Path) -> None:
    lines = _group_words_into_lines(words)
    style = (
        f"Style: Plain,Arial,{_CAPTION_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,3,0,2,60,60,60,1"
    )
    header = (
        "[Script Info]\nTitle: Storyteller captions\nScriptType: v4.00+\nWrapStyle: 2\n"
        f"PlayResX: {OUTPUT_WIDTH}\nPlayResY: {OUTPUT_HEIGHT}\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        f"Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, "
        f"Encoding\n{style}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, "
        "MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for line in lines:
        text = " ".join(w["text"] for w in line)
        events.append(
            f"Dialogue: 0,{_format_ass_time(line[0]['start'])},{_format_ass_time(line[-1]['end'])},"
            f"Plain,,0,0,0,,{text}"
        )
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


# -- service ------------------------------------------------------------


class StorytellerService:
    """Own queue + worker thread. One episode at a time -- narration/render
    are both CPU/network-bound but sequential is fine for a desktop-local
    single-user tool (same reasoning as SceneCutterService)."""

    def __init__(self, library_dir: Path):
        self._library_dir = library_dir
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._recover_pending()
        self._worker = threading.Thread(target=self._worker_loop, name="storyteller-worker", daemon=True)
        self._worker.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        if self._worker is None:
            return
        self._queue.put(None)
        self._worker.join(timeout=timeout)
        self._worker = None

    def enqueue(self, episode_id: int) -> None:
        self._queue.put(episode_id)

    def _recover_pending(self) -> None:
        db = SessionLocal()
        try:
            rows = db.query(StorytellerEpisode).filter(
                StorytellerEpisode.status.in_(PENDING_STATUSES)
            ).all()
            for row in rows:
                row.status = "pending"
                row.progress_stage = None
            db.commit()
            for row in rows:
                self._queue.put(row.id)
        finally:
            db.close()

    def _worker_loop(self) -> None:
        while True:
            episode_id = self._queue.get()
            if episode_id is None:
                self._queue.task_done()
                break
            try:
                self._process(episode_id)
            except Exception:  # noqa: BLE001 -- one bad episode must never kill the worker
                logger.exception("storyteller: episode %s failed", episode_id)
                self._fail(episode_id, "Render thất bại -- xem log backend để biết chi tiết.")
            finally:
                self._queue.task_done()

    def _episode_dir(self, episode_id: int) -> Path:
        d = self._library_dir / "storyteller" / "episodes" / str(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _set(self, episode_id: int, **fields) -> None:
        db = SessionLocal()
        try:
            row = db.get(StorytellerEpisode, episode_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
        finally:
            db.close()

    def _fail(self, episode_id: int, message: str) -> None:
        self._set(episode_id, status="failed", error_message=message, progress_stage=None)

    def _process(self, episode_id: int) -> None:
        db = SessionLocal()
        try:
            episode = db.get(StorytellerEpisode, episode_id)
            if episode is None:
                return

            def load(asset_id: int | None) -> _Panel | None:
                if not asset_id:
                    return None
                asset = db.get(StorytellerAsset, asset_id)
                if asset is None:
                    return None
                return _Panel(Path(asset.path), asset.media_type == "image", asset.key_color)

            background = load(episode.background_asset_id)
            avatar = load(episode.avatar_asset_id)
            left = load(episode.left_asset_id)
            middle = load(episode.middle_asset_id)
            right = load(episode.right_asset_id)
            slides = [p for aid in (episode.slide_asset_ids or []) if (p := load(aid)) is not None]
            music_asset = db.get(StorytellerAsset, episode.music_asset_id) if episode.music_asset_id else None
            music_path = Path(music_asset.path) if music_asset is not None else None

            title, script_text, voice, rate = episode.title, episode.script_text, episode.voice, episode.narration_rate
            burn_captions = episode.burn_captions
            layout = episode.layout
            disclaimer_text = episode.disclaimer_text
            info_lines = [
                f"Truyện: {episode.story_title}" if episode.story_title else None,
                f"Tác giả: {episode.story_author}" if episode.story_author else None,
                f"Nhân vật chính: {episode.story_character}" if episode.story_character else None,
            ]
            info_lines = [line for line in info_lines if line]
        finally:
            db.close()

        work_dir = self._episode_dir(episode_id)
        segments_dir = work_dir / "segments"
        segments_dir.mkdir(exist_ok=True)

        # -- narrate ------------------------------------------------
        self._set(episode_id, status="narrating", progress_stage="Đang đọc kịch bản...")
        all_words: list[dict] = []
        segment_paths: list[Path] = []
        cursor = 0.0
        beat_durations: list[float] = []

        if layout == "slideshow" and slides:
            beats = split_into_beats(script_text, len(slides))
            slides = slides[: len(beats)]  # split_into_beats may clamp for very short scripts
            seg_counter = 0
            for beat_i, beat_text in enumerate(beats):
                beat_start_cursor = cursor
                for sub_chunk in chunk_script(beat_text):
                    seg_path = segments_dir / f"segment_{seg_counter:03d}.mp3"
                    words = _narrate_chunk(sub_chunk, voice, rate, seg_path)
                    for w in words:
                        all_words.append({"start": w["start"] + cursor, "end": w["end"] + cursor, "text": w["text"]})
                    cursor += _probe_duration(seg_path)
                    segment_paths.append(seg_path)
                    seg_counter += 1
                beat_durations.append(cursor - beat_start_cursor)
                self._set(episode_id, progress_stage=f"Đã đọc {beat_i + 1}/{len(beats)} phân đoạn...")
        else:
            chunks = chunk_script(script_text)
            for i, chunk in enumerate(chunks):
                seg_path = segments_dir / f"segment_{i:03d}.mp3"
                words = _narrate_chunk(chunk, voice, rate, seg_path)
                for w in words:
                    all_words.append({"start": w["start"] + cursor, "end": w["end"] + cursor, "text": w["text"]})
                cursor += _probe_duration(seg_path)
                segment_paths.append(seg_path)
                self._set(episode_id, progress_stage=f"Đã đọc {i + 1}/{len(chunks)} đoạn...")

        narration_path = work_dir / "narration.mp3"
        if len(segment_paths) == 1:
            shutil.copyfile(segment_paths[0], narration_path)
        else:
            concat_list = segments_dir / "concat.txt"
            concat_list.write_text(
                "\n".join(f"file '{p.resolve().as_posix()}'" for p in segment_paths), encoding="utf-8"
            )
            _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(narration_path)])
        duration = _probe_duration(narration_path)
        self._set(episode_id, narration_path=str(narration_path), duration_sec=duration)

        # -- background music (optional) -------------------------------
        audio_path = narration_path
        if music_path is not None:
            self._set(episode_id, progress_stage="Đang trộn nhạc nền...")
            mixed_path = work_dir / "mixed_audio.mp3"
            _mix_narration_and_music(narration_path, music_path, duration, mixed_path)
            audio_path = mixed_path

        # -- captions -------------------------------------------------
        captions_path: Path | None = None
        if burn_captions and all_words:
            self._set(episode_id, progress_stage="Đang tạo phụ đề...")
            captions_path = work_dir / "captions.ass"
            _write_captions(all_words, captions_path)
            self._set(episode_id, captions_ass_path=str(captions_path))

        # -- composite --------------------------------------------------
        self._set(episode_id, status="compositing", progress_stage="Đang ghép video...")
        output_path = work_dir / "final.mp4"
        self._composite(
            duration=duration,
            narration_path=audio_path,
            layout=layout,
            background=background,
            avatar=avatar,
            left=left,
            middle=middle,
            right=right,
            slides=list(zip(slides, beat_durations)) if layout == "slideshow" else None,
            captions_path=captions_path,
            disclaimer_text=disclaimer_text,
            info_lines=info_lines,
            output_path=output_path,
        )

        self._set(
            episode_id, status="completed", progress_stage=None,
            output_path=str(output_path), duration_sec=duration,
        )
        logger.info("storyteller: episode %s (%r) completed -> %s", episode_id, title, output_path)

    @staticmethod
    def _panel_input_args(panel: "_Panel", duration: float) -> list[str]:
        if panel.is_image:
            # -loop 1 turns a still image into a video stream for -t
            # seconds -- the ffmpeg-standard "Ken Burns without the pan"
            # still-image-as-background technique.
            return ["-loop", "1", "-framerate", "30", "-t", str(duration), "-i", str(panel.path)]
        return ["-stream_loop", "-1", "-t", str(duration), "-i", str(panel.path)]

    @staticmethod
    def _composite(
        *,
        duration: float,
        narration_path: Path,
        layout: str = "single",
        background: "_Panel | None" = None,
        avatar: "_Panel | None" = None,
        left: "_Panel | None" = None,
        middle: "_Panel | None" = None,
        right: "_Panel | None" = None,
        slides: list[tuple["_Panel", float]] | None = None,
        captions_path: Path | None = None,
        disclaimer_text: str | None = None,
        info_lines: list[str] | None = None,
        output_path: Path,
        rng: random.Random | None = None,
    ) -> None:
        rng = rng or random.Random()
        inputs: list[str] = []
        filters: list[str] = []
        next_index = 0

        def add_input(args: list[str]) -> int:
            nonlocal next_index
            inputs.extend(args)
            idx = next_index
            next_index += 1
            return idx

        def solid_color(width: int) -> list[str]:
            return ["-f", "lavfi", "-t", str(duration), "-i", f"color=c=0x141414:s={width}x{OUTPUT_HEIGHT}:rate=30"]

        if layout == "triptych":
            panel_width = OUTPUT_WIDTH // 3
            panel_labels: list[str] = []
            for panel in (left, middle, right):
                idx = add_input(
                    StorytellerService._panel_input_args(panel, duration) if panel is not None else solid_color(panel_width)
                )
                label = f"p{idx}"
                filters.append(
                    f"[{idx}:v]scale={panel_width}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={panel_width}:{OUTPUT_HEIGHT},setsar=1,fps=30[{label}]"
                )
                panel_labels.append(label)
            filters.append("".join(f"[{lb}]" for lb in panel_labels) + "hstack=inputs=3[bg]")
            current_label = "bg"
        elif layout == "slideshow":
            slide_pairs = slides or []
            if not slide_pairs:
                idx = add_input(solid_color(OUTPUT_WIDTH))
                filters.append(f"[{idx}:v]setsar=1[bg]")
            else:
                slide_labels: list[str] = []
                for panel, beat_duration in slide_pairs:
                    idx = add_input(StorytellerService._panel_input_args(panel, beat_duration))
                    label = f"sl{idx}"
                    base = (
                        f"[{idx}:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
                        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}"
                    )
                    if panel.is_image:
                        # Ken Burns only makes sense on a still image -- a
                        # video slide already has its own motion.
                        direction = rng.choice(("in", "out"))
                        max_zoom = rng.uniform(1.12, 1.28)
                        total_frames = max(1, round(beat_duration * 30))
                        filters.append(
                            f"{base},scale={OUTPUT_WIDTH * 2}:{OUTPUT_HEIGHT * 2},"
                            f"{_zoompan_filter(direction, max_zoom, total_frames)},setsar=1,fps=30[{label}]"
                        )
                    else:
                        filters.append(f"{base},setsar=1,fps=30[{label}]")
                    slide_labels.append(label)
                filters.append(
                    "".join(f"[{lb}]" for lb in slide_labels) + f"concat=n={len(slide_labels)}:v=1:a=0[bg]"
                )
            current_label = "bg"
        else:
            idx = add_input(
                StorytellerService._panel_input_args(background, duration) if background is not None else solid_color(OUTPUT_WIDTH)
            )
            filters.append(
                f"[{idx}:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},setsar=1,fps=30[bg]"
            )
            current_label = "bg"

            if avatar is not None:
                idx = add_input(StorytellerService._panel_input_args(avatar, duration))
                key_color = avatar.key_color or "0x00FF00"
                filters.append(
                    f"[{idx}:v]colorkey={key_color}:0.30:0.15,scale=-2:{int(OUTPUT_HEIGHT * 0.55)}[av]"
                )
                filters.append(f"[{current_label}][av]overlay=W-w-40:H-h-40[withavatar]")
                current_label = "withavatar"

        if captions_path is not None:
            escaped = _escape_for_ffmpeg_filter(captions_path)
            filters.append(f"[{current_label}]subtitles='{escaped}'[cap]")
            current_label = "cap"

        if disclaimer_text:
            dtext = _drawtext_filter([disclaimer_text], y_expr="30", font_size=32)
            filters.append(f"[{current_label}]{dtext}[disc]")
            current_label = "disc"

        if info_lines:
            itext = _drawtext_filter(info_lines, y_expr=f"h-{34 * len(info_lines) + 220}", font_size=30)
            filters.append(f"[{current_label}]{itext}[info]")
            current_label = "info"

        narration_index = add_input(["-i", str(narration_path)])

        args = inputs + [
            "-filter_complex", ";".join(filters),
            "-map", f"[{current_label}]",
            "-map", f"{narration_index}:a",
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(output_path),
        ]
        _run_ffmpeg(args)


# -- plain CRUD (episodes + shared background/avatar assets) -----------


def create_episode(**fields) -> StorytellerEpisode:
    db = SessionLocal()
    try:
        script_text = fields["script_text"]
        episode = StorytellerEpisode(word_count=len(script_text.split()), **fields)
        db.add(episode)
        db.commit()
        db.refresh(episode)
        db.expunge(episode)
        return episode
    finally:
        db.close()


def get_episode(episode_id: int) -> StorytellerEpisode:
    db = SessionLocal()
    try:
        row = db.get(StorytellerEpisode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_episodes() -> list[StorytellerEpisode]:
    db = SessionLocal()
    try:
        rows = db.query(StorytellerEpisode).order_by(StorytellerEpisode.created_at.desc()).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def delete_episode(episode_id: int, library_dir: Path) -> None:
    db = SessionLocal()
    try:
        row = db.get(StorytellerEpisode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()
    shutil.rmtree(library_dir / "storyteller" / "episodes" / str(episode_id), ignore_errors=True)


def retry_episode(episode_id: int) -> StorytellerEpisode:
    db = SessionLocal()
    try:
        row = db.get(StorytellerEpisode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        if row.status not in ("failed", "completed"):
            raise ValidationError("Episode is already in progress")
        row.status = "pending"
        row.error_message = None
        row.progress_stage = None
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def save_asset(*, kind: str, name: str, tmp_upload_path: Path, library_dir: Path) -> StorytellerAsset:
    dest_dir = library_dir / "storyteller" / "assets" / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{name}{tmp_upload_path.suffix}"
    shutil.move(str(tmp_upload_path), str(dest_path))

    if kind == "music" or is_audio_file(dest_path):
        media_type = "audio"
    elif is_image_file(dest_path):
        media_type = "image"
    else:
        media_type = "video"
    width = height = None
    duration = None
    key_color = None
    try:
        if media_type == "image":
            width, height = _probe_image_info(dest_path)
        elif media_type == "audio":
            duration = _probe_duration(dest_path)
        else:
            width, height, _fps = _probe_video_info(dest_path)
            duration = _probe_duration(dest_path)
        if kind == "avatar":
            key_color = _sample_corner_color(dest_path, dest_dir)
    except (subprocess.SubprocessError, ValueError, OSError):
        logger.warning("storyteller: could not probe uploaded asset %s", dest_path)

    db = SessionLocal()
    try:
        asset = StorytellerAsset(
            kind=kind, media_type=media_type, name=name, path=str(dest_path),
            width=width, height=height, duration_sec=duration, key_color=key_color,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        db.expunge(asset)
        return asset
    finally:
        db.close()


def list_assets(kind: str | None = None) -> list[StorytellerAsset]:
    db = SessionLocal()
    try:
        q = db.query(StorytellerAsset)
        if kind:
            q = q.filter(StorytellerAsset.kind == kind)
        rows = q.order_by(StorytellerAsset.created_at.desc()).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def delete_asset(asset_id: int, library_dir: Path) -> None:
    db = SessionLocal()
    try:
        row = db.get(StorytellerAsset, asset_id)
        if row is None:
            raise NotFoundError("Asset", asset_id)
        path = Path(row.path)
        db.delete(row)
        db.commit()
    finally:
        db.close()
    path.unlink(missing_ok=True)
