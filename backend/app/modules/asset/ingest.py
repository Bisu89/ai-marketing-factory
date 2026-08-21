"""Pure ingestion helpers for Task 15 (Local Asset Ingestion + Smart Library
Preparation) -- see docs/features/41-local-asset-ingestion.md. No DB/FastAPI
dependency here (mirrors app.modules.batch.schemas.parse_scripts's own
"pure, directly unit-testable" shape); orchestration (discovering files,
inserting rows, batching commits, progress/cancel) lives in
import_service.py.

Deliberately NOT a second media-probe utility for images: this module uses
Pillow (already a real dependency -- see video_composer/service.py's own
`from PIL import ImageFont`) for image validation, EXIF-aware dimensions,
and thumbnails, since the existing image tooling (motion/renderer.py's
_probe_image) is ffprobe-only and doesn't read EXIF orientation at all --
see extract_image_metadata's own docstring for why that matters here. Video
metadata reuses the exact same ffprobe *command shape* video_composer's own
_probe_duration/_probe_video_info already use (duplicated, not imported --
app.modules.asset must never import app.modules.video_composer; this is the
same "duplicate the pattern across a module boundary" convention already
used for MOTION_PRESET_DEFAULTS between the Python and TS sides of the
Video Factory).
"""

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import FileOperationError

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
# Video ingestion is included (not deferred to "images first") because
# app.modules.asset.Asset already treats type="video" as a first-class,
# already-rendering-tested asset type (see
# tests/api/test_composition_render.py's
# test_video_asset_scene_is_used_directly_without_motion_rendering) --
# supporting it here is not "major architectural work", just more ingestion
# coverage for a type this app already reliably uses.
SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm"})
# Real user report: there was no way to import a music track for BGM at
# all -- Asset already treats type="audio" as first-class (voice_generate.py/
# audio_generate.py's own narration/audio_master registrations, and
# AssetLibraryPage's tile rendering already has a dedicated Music icon
# branch for it), but nothing ever let a *user* bring their own audio file
# in. Same reasoning as video's own comment above: not new architecture,
# just more ingestion coverage for a type this app already relies on.
SUPPORTED_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".flac", ".ogg"})
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_AUDIO_EXTENSIONS

_HASH_CHUNK_SIZE = 1 << 20  # 1 MiB -- large files are streamed, never fully loaded into memory
_THUMBNAIL_MAX_SIZE = (480, 480)


def compute_file_hash(path: Path) -> str:
    """Deterministic SHA-256 content fingerprint -- Task 15's own duplicate-
    detection key (section 6: "do NOT use only filename"). Streamed so a
    large video doesn't need to fit in memory at once.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_orientation(width: int, height: int) -> str:
    if width == height:
        return "SQUARE"
    return "PORTRAIT" if height > width else "LANDSCAPE"


@dataclass
class ImageMetadata:
    width: int
    height: int
    orientation: str
    format: str | None


def extract_image_metadata(path: Path) -> ImageMetadata:
    """Opens with Pillow and applies ImageOps.exif_transpose -- a phone
    photo whose file physically stores e.g. 1920x1080 but carries an EXIF
    "rotate 90" tag visually *is* a 1080x1920 portrait image, and Task 15
    section 11 explicitly wants that reported correctly. The existing
    render pipeline (app.modules.motion.renderer, pure ffmpeg/ffprobe)
    does not read EXIF at all -- exif_transpose here only affects what the
    *Library* reports/filters on, it does not touch the source file or the
    renderer (out of this task's scope; noted as a known pre-existing gap
    in docs/features/41-local-asset-ingestion.md, not something to silently
    "fix" here).

    Raises FileOperationError for anything Pillow can't decode as an image
    at all -- the same exception type/shape _probe_image already raises
    elsewhere in this codebase for the same class of problem, so a corrupt
    file fails ingestion the same recognizable way it would fail rendering.
    """
    try:
        with Image.open(path) as img:
            img.load()  # forces full decode -- Image.open() alone is lazy and can miss truncated data
            transposed = ImageOps.exif_transpose(img)
            width, height = transposed.size
            image_format = img.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FileOperationError(f"Invalid or unreadable image: {path}") from exc

    if width <= 0 or height <= 0:
        raise FileOperationError(f"Invalid or unreadable image: {path}")

    return ImageMetadata(width=width, height=height, orientation=classify_orientation(width, height), format=image_format)


@dataclass
class VideoMetadata:
    width: int
    height: int
    duration_sec: float
    fps: float
    codec: str | None


def extract_video_metadata(path: Path) -> VideoMetadata:
    """Same ffprobe tool and command shape as video_composer's own
    _probe_video_info/_probe_duration (see module docstring for why this is
    a duplicated pattern, not a shared import).
    """
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffprobe was not found on PATH -- is it installed/bundled?") from exc

    import json as _json

    try:
        data = _json.loads(result.stdout)
        stream = data["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        num, _, den = stream["r_frame_rate"].partition("/")
        fps = float(num) / float(den or 1)
        codec = stream.get("codec_name")
        duration = float(data["format"]["duration"])
    except (KeyError, IndexError, ValueError, ZeroDivisionError) as exc:
        raise FileOperationError(f"Invalid or unreadable video: {path}") from exc

    if result.returncode != 0 or width <= 0 or height <= 0 or duration <= 0:
        raise FileOperationError(f"Invalid or unreadable video: {path}")

    return VideoMetadata(width=width, height=height, duration_sec=duration, fps=fps, codec=codec)


@dataclass
class AudioMetadata:
    duration_sec: float
    codec: str | None


def extract_audio_metadata(path: Path) -> AudioMetadata:
    """Same ffprobe tool/shape as extract_video_metadata above, minus the
    video-only fields (no width/height/fps/orientation for an audio file --
    Asset.width/height simply stay None, exactly like a pre-Task-15 manually
    registered audio row already does).
    """
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffprobe was not found on PATH -- is it installed/bundled?") from exc

    import json as _json

    try:
        data = _json.loads(result.stdout)
        stream = data["streams"][0]
        codec = stream.get("codec_name")
        duration = float(data["format"]["duration"])
    except (KeyError, IndexError, ValueError) as exc:
        raise FileOperationError(f"Invalid or unreadable audio file: {path}") from exc

    if result.returncode != 0 or duration <= 0:
        raise FileOperationError(f"Invalid or unreadable audio file: {path}")

    return AudioMetadata(duration_sec=duration, codec=codec)


def generate_image_thumbnail(source_path: Path, dest_path: Path) -> None:
    """A small, fixed-size (max 480x480, aspect-preserving) preview -- never
    full resolution (section 14's own explicit instruction). EXIF-aware,
    same as extract_image_metadata, so a thumbnail never appears sideways
    even though the renderer itself doesn't correct for that yet.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as img:
        transposed = ImageOps.exif_transpose(img).convert("RGB")
        transposed.thumbnail(_THUMBNAIL_MAX_SIZE)
        transposed.save(dest_path, "JPEG", quality=85)


def generate_video_thumbnail(source_path: Path, dest_path: Path, at_seconds: float = 0.5) -> None:
    """One representative frame near the start -- section 15 explicitly
    rules out intelligent scene detection ("a simple frame around the
    beginning is sufficient"). Reuses the same ffmpeg frame-grab shape
    already established in this codebase's own test fixtures
    (tests/api/test_composition_render.py's own frame-sampling helper).
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", str(at_seconds), "-i", str(source_path),
        "-vframes", "1", "-vf", f"scale='min({_THUMBNAIL_MAX_SIZE[0]},iw)':-2",
        str(dest_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?") from exc
    if result.returncode != 0 or not dest_path.exists():
        raise FileOperationError(f"Could not generate a thumbnail for: {source_path}")


# -- Filename/folder tokenization + tag extraction (sections 17-19) -------

_SEPARATOR_RE = re.compile(r"[_\-\s]+")
# Only dropped when they appear as a standalone token (never as a substring
# match -- "image1080" or "copywriter" must survive untouched). Section 18's
# own "only when safe" instruction.
_STOPWORD_TOKENS = frozenset({
    "img", "image", "images", "photo", "photos", "pic", "pics", "picture", "pictures",
    "final", "copy", "edited", "edit", "new", "untitled", "screenshot", "screen", "shot",
    "dsc", "vid", "video", "clip", "frame", "download", "downloaded",
})
_PURE_NUMBER_RE = re.compile(r"^\d+$")


def tokenize_filename(filename: str, strip_stopwords: bool = True) -> list[str]:
    """"woman_opening_gift_emotional.jpg" -> ["woman", "opening", "gift",
    "emotional"] (section 18). Splits on _/-/space, drops the extension,
    lowercases, drops pure-numeric tokens ("01", "02") and, when
    `strip_stopwords` (folder segments pass False -- see
    folder_tags_from_path below), a small, explicit stopword list
    (img/photo/final/copy/...), and drops single-character leftovers --
    never touches a token that isn't an exact stopword/number match, so
    real words are never destroyed.
    """
    stem = Path(filename).stem
    raw_tokens = _SEPARATOR_RE.split(stem)
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in raw_tokens:
        token = raw.strip().lower()
        if not token or len(token) < 2:
            continue
        if _PURE_NUMBER_RE.match(token):
            continue
        if strip_stopwords and token in _STOPWORD_TOKENS:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def folder_tags_from_path(file_path: Path, import_root: Path) -> list[str]:
    """Folder segments between `import_root` and the file itself become
    supplemental tags (section 17): assets/couples/reunion/image1.jpg
    imported from `assets/` -> ["couples", "reunion"]. Each segment is
    split/lowercased/deduped the same way a filename is, but *without* the
    filename stopword list -- a folder name is a human-curated grouping
    decision (unlike an auto-generated camera filename), so a segment like
    "family_photos" keeps "photos" rather than treating it as noise. Never
    includes `import_root` itself or the filename.
    """
    try:
        relative = file_path.resolve().relative_to(import_root.resolve())
    except ValueError:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for segment in relative.parts[:-1]:  # exclude the filename itself
        for token in tokenize_filename(segment, strip_stopwords=False):
            if token not in seen:
                seen.add(token)
                tags.append(token)
    return tags


# -- Category/Emotion inference (sections 21-22) ---------------------------
#
# Values are the *real* existing catalogs (see app/db/seed.py's CATEGORIES/
# EMOTIONS) -- not invented. Duplicated here as plain string constants
# rather than importing app.models.category/emotion, since that core
# package isn't something app.modules.asset depends on today and doing so
# would give this self-contained module a real schema dependency for the
# sake of a static value list (see Asset's own docstring on this). Emotion
# names are Vietnamese in the real catalog (this app's Library was built
# Vietnamese-first -- see app/models/emotion.py) while asset filenames are
# typically English, so the lexicon below is an explicit English-keyword ->
# Vietnamese-catalog-value mapping, not a coincidence.

CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "Couple": frozenset({"couple", "couples", "romance", "romantic", "date", "anniversary"}),
    "Family": frozenset({"family", "mother", "father", "parent", "parents", "mom", "dad", "child", "children", "kid", "kids", "grandma", "grandpa", "grandmother", "grandfather"}),
    "Military": frozenset({"military", "soldier", "soldiers", "army", "veteran", "uniform"}),
    "Proposal": frozenset({"proposal", "propose", "engagement", "ring"}),
    "Transformation": frozenset({"transformation", "before", "after", "makeover", "renovation"}),
    "Comedy": frozenset({"comedy", "funny", "joke", "prank", "silly"}),
}

EMOTION_KEYWORDS: dict[str, frozenset[str]] = {
    "Vui": frozenset({"happy", "joy", "joyful", "smile", "smiling", "cheerful", "excited"}),
    "Cảm động": frozenset({"touching", "moving", "emotional", "heartwarming", "nostalgic", "reunion", "love", "loving"}),
    "Hài hước": frozenset({"funny", "hilarious", "silly", "laugh", "laughing"}),
    "Buồn": frozenset({"sad", "sorrow", "crying", "cry", "grief", "lonely"}),
    "Kịch tính": frozenset({"dramatic", "shock", "shocking", "surprise", "surprised", "intense", "tense", "angry"}),
}


def _best_lexicon_match(tokens: list[str], lexicon: dict[str, frozenset[str]]) -> str | None:
    """Only assigns a value when exactly one candidate has the strongest
    overlap -- a tie (or zero matches) returns None rather than guessing
    (sections 21/22: "if [it] cannot be confidently inferred... = null. Do
    not force a wrong [value]").
    """
    token_set = set(tokens)
    scores = {name: len(token_set & keywords) for name, keywords in lexicon.items()}
    scores = {name: score for name, score in scores.items() if score > 0}
    if not scores:
        return None
    best_score = max(scores.values())
    winners = [name for name, score in scores.items() if score == best_score]
    return winners[0] if len(winners) == 1 else None


def infer_category(tokens: list[str]) -> str | None:
    return _best_lexicon_match(tokens, CATEGORY_KEYWORDS)


def infer_emotion(tokens: list[str]) -> str | None:
    return _best_lexicon_match(tokens, EMOTION_KEYWORDS)


# -- Suitability guidance (sections 33-34) ---------------------------------

PORTRAIT_SUITABILITIES = ("EXCELLENT", "GOOD", "CROP_REQUIRED", "LOW_RESOLUTION")


def classify_portrait_suitability(
    width: int | None, height: int | None, target_width: int = 1080, target_height: int = 1920
) -> str | None:
    """Metadata guidance only (section 34) -- the renderer can and still
    does crop landscape assets; this just tells a human (or a future
    matcher) which local assets need the least cropping for this app's
    default SOCIAL_VERTICAL profile. Deterministic geometry, no AI scoring.

    LOW_RESOLUTION is decided by the "cover" scale factor (the same
    scale-to-fill-the-frame-then-crop-the-overflow approach the render
    pipeline itself uses -- see app.modules.motion.renderer), not a naive
    "is either raw dimension smaller than the target" check: a 1920x1080
    landscape photo has plenty of raw pixels but genuinely can't fill a
    1080x1920 portrait frame without upscaling (its 1080px height is short
    of the 1920px the frame needs), while a 4000x3000 landscape has more
    than enough to crop from. Naively comparing width/height directly
    against the target's width/height mislabels ordinary landscape photos.
    """
    if not width or not height:
        return None
    cover_scale = max(target_width / width, target_height / height)
    if cover_scale > 1.0:
        return "LOW_RESOLUTION"
    target_ratio = target_width / target_height
    ratio = width / height
    if abs(ratio - target_ratio) <= 0.05:
        return "EXCELLENT"
    if ratio < 1.0:
        return "GOOD"
    return "CROP_REQUIRED"
