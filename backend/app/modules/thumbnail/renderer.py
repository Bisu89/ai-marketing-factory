"""FFmpeg frame extraction + Pillow frame analysis/compose (Task 27
sections 4-19). The only I/O boundary in app.modules.thumbnail -- schemas.py
stays pure, scoring.py stays pure; every subprocess/file-read/file-write
lives here, mirroring app.modules.motion.renderer's own "one file owns the
real ffmpeg/Pillow calls" shape.

No AI image generation, no cloud thumbnail API (section 4) -- the
thumbnail is always a real frame lifted straight out of the project's own
final.mp4, which already IS this video's visual identity (section 5).
"""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from app.modules.thumbnail.schemas import (
    THUMBNAIL_GENERATION_FAILED,
    THUMBNAIL_INVALID,
    THUMBNAIL_NO_VALID_FRAME,
    FrameStats,
    ThumbnailConfig,
    ThumbnailError,
)
from app.modules.thumbnail.scoring import select_best_frame_with_fallback

# Section 17 -- reuses this app's own already-established, already-bundled
# font (video_composer.service.FONT_PATH_BOLD duplicated here, not
# imported, per this codebase's established module-boundary "duplicate a
# proven recipe" convention -- see app.modules.caption.ass_writer's own
# identical reasoning for its own font references).
FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"

ENGINE_VERSION = "thumbnail-v1"

_JPEG_QUALITY = 88


def _run_ffmpeg(args: list[str]) -> None:
    command = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise ThumbnailError(THUMBNAIL_GENERATION_FAILED, f"ffmpeg failed: {result.stderr.strip()[-2000:]}")


def probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise ThumbnailError(THUMBNAIL_GENERATION_FAILED, f"Could not read video duration for {video_path}") from exc


def extract_candidate_frames(video_path: Path, offsets: tuple[float, ...], duration: float, work_dir: Path) -> list[tuple[float, Path]]:
    """Section 6: one still frame per fractional offset into the video's
    own duration. `-ss` before `-i` seeks fast (keyframe-nearest, not
    frame-accurate) -- acceptable here since candidates are already spread
    several seconds apart and this is a thumbnail pick, not a precision
    edit point.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    frames: list[tuple[float, Path]] = []
    for i, fraction in enumerate(offsets):
        timestamp = max(0.0, min(duration * fraction, max(0.0, duration - 0.05)))
        frame_path = work_dir / f"candidate_{i:02d}.jpg"
        try:
            _run_ffmpeg(["-ss", f"{timestamp:.3f}", "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(frame_path)])
        except ThumbnailError:
            continue  # section 7: an extraction failure just means one fewer candidate, not a hard stop
        if frame_path.exists() and frame_path.stat().st_size > 0:
            frames.append((fraction, frame_path))
    return frames


def compute_frame_stats(offset_fraction: float, path: Path) -> FrameStats | None:
    """Section 8: pure Pillow histogram statistics -- brightness (mean),
    contrast (stdev), and edge density (mean of a FIND_EDGES pass, a
    sharpness/detail proxy) -- never AI vision. Returns None for a file
    Pillow can't even open (section 7's own "obviously corrupted").
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
        return None
    return FrameStats(offset_fraction=offset_fraction, path=path, brightness=brightness, contrast=contrast, edge_density=edge_density)


def _cover_crop_resize(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """Section 12: cover behavior -- scale + center crop, never stretch.
    No per-frame focal-point metadata exists for an arbitrary extracted
    video frame (unlike a Beat's own source image, which Motion's own
    focal_x/focal_y describes -- see app.modules.motion.schemas), so this
    always center-crops, matching section 12's own explicit fallback.
    """
    src_width, src_height = img.size
    src_ratio = src_width / src_height
    target_ratio = target_width / target_height
    if src_ratio > target_ratio:
        new_width = max(1, round(src_height * target_ratio))
        x0 = (src_width - new_width) // 2
        img = img.crop((x0, 0, x0 + new_width, src_height))
    else:
        new_height = max(1, round(src_width / target_ratio))
        y0 = (src_height - new_height) // 2
        img = img.crop((0, y0, src_width, y0 + new_height))
    return img.resize((target_width, target_height), Image.LANCZOS)


def shorten_headline(text: str, max_chars: int) -> str:
    """Section 15: a deterministic, word-boundary-only shortening -- never
    cuts mid-word (section 15's own explicit "do not simply truncate in
    the middle" example), never an LLM call. Upper-cased to match this
    app's own existing punchy on-screen-text convention (see
    app.modules.caption.ass_writer's "big_statement" preset).
    """
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized.upper()

    words = normalized.split()
    kept: list[str] = []
    length = 0
    for word in words:
        added = len(word) if not kept else len(word) + 1
        if length + added > max_chars:
            break
        kept.append(word)
        length += added
    if not kept:
        return normalized[:max_chars].upper()
    return " ".join(kept).upper()


def _wrap_headline(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and font.getlength(candidate) > max_width:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines:
                break
        else:
            current.append(word)
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines[:max_lines]


def _draw_headline(img: Image.Image, headline: str, max_chars: int) -> Image.Image:
    """Section 13/16: text + font + size + position + stroke only -- no
    thumbnail editor. Large, high-contrast, stroked text near the bottom
    third with safe margins, never covering the full frame.

    The source frame is lifted straight from final.mp4, which may itself
    already have Task 25's own burned-in captions sitting in that same
    bottom region -- a stroke alone, and even a merely translucent banner,
    were both found (real manual verification) to leave the headline
    overlapping visibly with whatever caption text happened to be on
    screen at that exact timestamp. A fully opaque banner behind the
    headline (the same "text needs its own backdrop, not just an outline"
    reasoning video_composer.service's own `_finalize` title drawtext
    already uses via `box=1:boxcolor=black@0.4`, just opaque rather than
    40% here) is what actually guarantees readability regardless of what's
    behind it.
    """
    text = shorten_headline(headline, max_chars)
    if not text:
        return img

    width, height = img.size
    font_size = max(24, round(height * 0.085))
    font = ImageFont.truetype(FONT_PATH_BOLD, font_size)
    margin_x = round(width * 0.06)
    max_text_width = width - 2 * margin_x

    lines = _wrap_headline(text, font, max_text_width)
    if not lines:
        return img

    line_height = font_size * 1.2
    band_padding = round(font_size * 0.5)
    total_height = line_height * len(lines)
    # Extends to the very bottom edge, not just a safe-margin line above it
    # -- this app's own default caption presets sit as low as ~2-3% from
    # the bottom (CAPTION_PRESET_CONFIG's margin_v_frac), so a band that
    # stops higher than that still lets a sliver of burned-in caption text
    # peek out underneath (found via real manual verification).
    band_bottom = height
    band_top = band_bottom - total_height - 2 * band_padding - round(height * 0.02)

    # Fully opaque, not merely translucent: even a 92%-opaque band still
    # let high-contrast burned-in caption text ghost through legibly
    # underneath the headline (found via the same manual verification) --
    # this needs to actually hide what's behind it, not just darken it.
    draw_band = ImageDraw.Draw(img)
    draw_band.rectangle([(0, band_top), (width, band_bottom)], fill=(0, 0, 0))

    draw = ImageDraw.Draw(img)
    stroke_width = max(2, font_size // 16)
    y = band_top + band_padding
    for line in lines:
        line_width = font.getlength(line)
        x = (width - line_width) / 2
        draw.text(
            (x, y), line, font=font, fill="white",
            stroke_width=stroke_width, stroke_fill="black",
        )
        y += line_height
    return img


def build_thumbnail(frame_path: Path, config: ThumbnailConfig) -> Image.Image:
    """Section 12/13: cover-crop/resize to the configured dimensions, then
    an optional headline overlay. Pure image transform -- saving is the
    caller's job (see caption_generate.py/audio_generate.py's own
    established "compute in-memory, atomic-write in the composition root"
    split).
    """
    try:
        with Image.open(frame_path) as raw:
            img = raw.convert("RGB")
            img = _cover_crop_resize(img, config.width, config.height)
    except Exception as exc:
        raise ThumbnailError(THUMBNAIL_GENERATION_FAILED, f"Could not process candidate frame {frame_path}: {exc}") from exc

    if config.headline_enabled and config.headline_text:
        img = _draw_headline(img, config.headline_text, config.headline_max_chars)
    return img


def save_thumbnail(img: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=_JPEG_QUALITY)


def validate_thumbnail(path: Path, *, expected_width: int, expected_height: int) -> None:
    """Section 19: exists, readable, correct dimensions/format, non-empty.
    Raises ThumbnailError(THUMBNAIL_INVALID) on the first problem found.
    """
    if not path.exists():
        raise ThumbnailError(THUMBNAIL_INVALID, f"Thumbnail file does not exist: {path}")
    if path.stat().st_size <= 0:
        raise ThumbnailError(THUMBNAIL_INVALID, f"Thumbnail file is empty: {path}")
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            width, height = img.size
            fmt = img.format
    except Exception as exc:
        raise ThumbnailError(THUMBNAIL_INVALID, f"Thumbnail file is not a readable image: {path} ({exc})") from exc
    if fmt != "JPEG":
        raise ThumbnailError(THUMBNAIL_INVALID, f"Thumbnail format {fmt!r} is not JPEG: {path}")
    if width != expected_width or height != expected_height:
        raise ThumbnailError(
            THUMBNAIL_INVALID,
            f"Thumbnail dimensions {width}x{height} do not match expected {expected_width}x{expected_height}: {path}",
        )


def select_thumbnail_frame(video_path: Path, config: ThumbnailConfig, work_dir: Path) -> Path:
    """Section 6-9 end to end: extract candidates, score, pick the best,
    deterministically. Falls back to the least-bad candidate rather than
    hard-failing the whole Package stage when every candidate trips the
    same rejection heuristic (select_best_frame_with_fallback's own
    "never block the factory over a soft failure" reasoning) -- a real,
    uniformly flat/low-detail video is still a real video. Only raises
    ThumbnailError(THUMBNAIL_NO_VALID_FRAME) when there is truly nothing
    to fall back to: extraction produced zero frames, or none could even
    be analyzed (a genuinely corrupt/unreadable video).
    """
    duration = probe_duration(video_path)
    if duration <= 0:
        raise ThumbnailError(THUMBNAIL_GENERATION_FAILED, f"Video has zero/invalid duration: {video_path}")

    frames = extract_candidate_frames(video_path, config.candidate_offsets, duration, work_dir)
    if not frames:
        raise ThumbnailError(THUMBNAIL_NO_VALID_FRAME, f"No candidate frames could be extracted from {video_path}")

    stats = [s for s in (compute_frame_stats(fraction, path) for fraction, path in frames) if s is not None]
    if not stats:
        raise ThumbnailError(THUMBNAIL_NO_VALID_FRAME, f"No candidate frame from {video_path} could be analyzed")

    best = select_best_frame_with_fallback(stats)
    if best is None:
        raise ThumbnailError(THUMBNAIL_NO_VALID_FRAME, f"No usable candidate frame could be found for {video_path}")
    return best.path
