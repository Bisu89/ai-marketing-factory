"""FFprobe/FFmpeg + Pillow real-artifact inspection for Final QA (Task 28
sections 8/17/20/21/28). The only I/O boundary in app.modules.postqa --
schemas.py and analyzer.py stay pure. Every technique here duplicates an
already-proven recipe from an earlier task's own module (Task 24's
volumedetect probe, Task 25's ASS Dialogue-line parsing, Task 27's frame-
quality scoring) rather than importing across the module boundary --
this codebase's established "duplicate a proven recipe" convention (see
e.g. app.modules.caption.ass_writer's own identical reasoning for its own
duplicated font/style constants).

Deliberately cheap (section 48): one ffprobe call, one ffmpeg
volumedetect pass (audio-only, no video decode), a plain-text ASS parse,
and Pillow histogram statistics on the already-saved thumbnail.jpg (never
re-extracting/re-scoring candidate frames from the video -- that's Task
27's own job, already done once).
"""

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from app.modules.postqa.schemas import AudioLevelInfo, VideoStreamInfo

# Section 7/9/10/17/21 -- duplicated thresholds, matching the exact values
# already proven in Task 24 (audio/renderer.py's own
# _SILENCE_MEAN_VOLUME_DB_THRESHOLD) and Task 27
# (thumbnail/scoring.py's own MIN_BRIGHTNESS/MAX_BRIGHTNESS/MIN_CONTRAST/
# MIN_EDGE_DENSITY) -- not re-derived, since these are the same real-world
# signal thresholds either way.
_MIN_THUMB_BRIGHTNESS = 15.0
_MAX_THUMB_BRIGHTNESS = 240.0
_MIN_THUMB_CONTRAST = 8.0
_MIN_THUMB_EDGE_DENSITY = 2.0

_ASS_TIME_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})\.(\d{2})$")


def probe_final_video(path: Path) -> VideoStreamInfo:
    """Section 8: one ffprobe call, full-format JSON -- never decodes a
    single frame. Missing/unreadable file is reported via `file_exists`/
    zeroed fields rather than raising -- callers (the analyzer) already
    treat that as its own FAIL check, not an exceptional code path.
    """
    if not path.exists():
        return VideoStreamInfo(
            duration=0.0, width=0, height=0, fps=0.0, video_streams=0, audio_streams=0,
            video_codec=None, audio_codec=None, pix_fmt=None, file_exists=False, file_size=0,
        )
    file_size = path.stat().st_size
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return VideoStreamInfo(
            duration=0.0, width=0, height=0, fps=0.0, video_streams=0, audio_streams=0,
            video_codec=None, audio_codec=None, pix_fmt=None, file_exists=True, file_size=file_size,
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return VideoStreamInfo(
            duration=0.0, width=0, height=0, fps=0.0, video_streams=0, audio_streams=0,
            video_codec=None, audio_codec=None, pix_fmt=None, file_exists=True, file_size=file_size,
        )

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    video = video_streams[0] if video_streams else {}
    audio = audio_streams[0] if audio_streams else {}

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    num, _, den = str(video.get("r_frame_rate", "0/1")).partition("/")
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    try:
        duration = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0

    return VideoStreamInfo(
        duration=duration, width=width, height=height, fps=fps,
        video_streams=len(video_streams), audio_streams=len(audio_streams),
        video_codec=video.get("codec_name"), audio_codec=audio.get("codec_name"),
        pix_fmt=video.get("pix_fmt"), file_exists=True, file_size=file_size,
    )


def probe_audio_levels(video_path: Path) -> AudioLevelInfo:
    """Section 17/18/19: ffmpeg's own `volumedetect` filter, audio-only --
    the same technique app.modules.audio.renderer._probe_loudness (Task
    24) already uses, run here directly against final.mp4's own audio
    track (never re-analyzing audio_master.wav, which may have been
    ducked/mixed differently than what actually landed in the final
    output).
    """
    if not video_path.exists():
        return AudioLevelInfo(mean_volume_db=None, max_volume_db=None, probed=False)
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not mean_match:
        return AudioLevelInfo(mean_volume_db=None, max_volume_db=None, probed=False)
    return AudioLevelInfo(
        mean_volume_db=float(mean_match.group(1)),
        max_volume_db=float(max_match.group(1)) if max_match else None,
        probed=True,
    )


def _parse_ass_time(text: str) -> float | None:
    match = _ASS_TIME_RE.match(text.strip())
    if not match:
        return None
    hours, minutes, seconds, centiseconds = (int(g) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0


def parse_ass_captions(content: str) -> tuple[int, float | None]:
    """Section 28: caption count + the latest end-time across every
    Dialogue line -- app.modules.caption.ass_writer.validate_ass_content
    (Task 25) already confirms structural validity (10-field Dialogue
    lines, non-empty text); this adds the two numbers QA actually needs
    that validator never computed (a file can be *structurally* valid ASS
    with zero real caption lines).
    """
    count = 0
    max_end = None
    for line in content.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line[len("Dialogue:"):].split(",", 9)
        if len(fields) < 10 or not fields[9].strip():
            continue
        count += 1
        end = _parse_ass_time(fields[2])
        if end is not None and (max_end is None or end > max_end):
            max_end = end
    return count, max_end


def thumbnail_looks_low_quality(path: Path) -> bool:
    """Section 21: a deterministic technical re-check (brightness/contrast/
    edge-density) against the already-SAVED thumbnail.jpg -- never AI
    vision, never re-extracting a fresh candidate frame (Task 27 already
    did the real selection; this only confirms what shipped still looks
    usable). Missing/unreadable file is reported by the caller's own
    exists/size check, not here -- this returns False (not "low quality")
    for a file it can't even open, so that check doesn't double-report
    the same problem.
    """
    try:
        with Image.open(path) as img:
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            brightness = stat.mean[0]
            contrast = stat.stddev[0]
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_density = ImageStat.Stat(edges).mean[0]
    except Exception:
        return False
    if brightness < _MIN_THUMB_BRIGHTNESS or brightness > _MAX_THUMB_BRIGHTNESS:
        return True
    if contrast < _MIN_THUMB_CONTRAST:
        return True
    if edge_density < _MIN_THUMB_EDGE_DENSITY:
        return True
    return False


def probe_thumbnail_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None
