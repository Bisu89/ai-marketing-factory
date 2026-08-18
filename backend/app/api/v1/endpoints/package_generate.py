"""Ready-to-Post Package (Task 27 -- see
docs/features/53-thumbnail-metadata-package.md): the composition-root
adapter between app.modules.thumbnail/app.modules.metadata (pure logic,
see those modules' own docstrings) and app.modules.beat/video_composer.
Same composition-root shape as caption_generate.py/audio_generate.py.

final.mp4 (Task 26's own Final Composer output) is the one and only
source for the thumbnail (section 4/5 -- no AI image generation, ever);
title/description/hashtags are derived entirely from content this Factory
already produced (ContentBrief, the HOOK beat's own narration) or an
explicit manual override -- never a new AI/LLM call (section 22/25).

Produces two standalone, user-facing artifacts next to the project's own
final.mp4 (`thumbnail.jpg`, `metadata.json`) plus a private cache sidecar
(`package.meta.json`) -- matches Task 24/25's own "sidecar JSON metadata,
atomic tmp-then-replace write" convention exactly.
"""

import hashlib
import json
import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal
from app.modules.beat.project_service import _UNSET, get_project_draft, set_project_package_overrides
from app.modules.beat.schemas import Beat, BeatType, PackageProjectConfig, ProjectOut
from app.modules.metadata.schemas import ContentInputs, MetadataError, PackageMetadata
from app.modules.metadata.service import derive_category, derive_description, derive_hashtags, derive_title
from app.modules.thumbnail.renderer import (
    ENGINE_VERSION as THUMBNAIL_ENGINE_VERSION,
    build_thumbnail,
    save_thumbnail,
    select_thumbnail_frame,
    shorten_headline,
    validate_thumbnail,
)
from app.modules.thumbnail.schemas import ThumbnailConfig, ThumbnailError
from app.modules.video_composer.models import VideoComposeJob

logger = logging.getLogger(__name__)
router = APIRouter()

METADATA_ENGINE_VERSION = "post-package-v1"

_THUMBNAIL_FILENAME = "thumbnail.jpg"
_METADATA_FILENAME = "metadata.json"
_CACHE_FILENAME = "package.meta.json"


# -- Package incompleteness / validation error codes (section 50) ---------

PACKAGE_INCOMPLETE = "PACKAGE_INCOMPLETE"
PACKAGE_VALIDATION_FAILED = "PACKAGE_VALIDATION_FAILED"


class PackageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# -- Locating the completed render's own output directory -----------------


def _completed_render_job(project_id: int, render_job_id: int | None) -> VideoComposeJob | None:
    """Section 33/53: the Package stage's one required upstream input is a
    genuinely COMPLETED render -- not merely "a render_job_id exists on
    Project" (that field is set the instant a job is *queued*, well before
    it finishes, see factory_pipeline.py's own _stage_render). Returns
    None (never raises) for "nothing to package yet" -- the same lenient
    convention Voice/Motion/Audio/Captions already use for their own
    not-ready-yet case.
    """
    if render_job_id is None:
        return None
    db = SessionLocal()
    try:
        job = db.get(VideoComposeJob, render_job_id)
        if job is None or job.status != "completed" or not job.output_path:
            return None
        db.expunge(job)
        return job
    finally:
        db.close()


def _output_dir(job: VideoComposeJob) -> Path:
    return Path(job.output_path).parent


def thumbnail_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _THUMBNAIL_FILENAME


def metadata_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _METADATA_FILENAME


def _cache_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _CACHE_FILENAME


def _read_render_metadata(job: VideoComposeJob) -> dict:
    path = Path(job.output_path).with_name("render_metadata.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_cache(job: VideoComposeJob) -> dict | None:
    path = _cache_path(job)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(job: VideoComposeJob, **fields) -> None:
    _cache_path(job).write_text(json.dumps(fields, indent=2), encoding="utf-8")


# -- Content inputs (section 21/24/26) -------------------------------------


def _hook_text(beats: list[Beat]) -> str | None:
    hook_beats = [b for b in sorted(beats, key=lambda b: b.order) if b.type == BeatType.HOOK and b.narration and b.narration.strip()]
    return hook_beats[0].narration if hook_beats else None


def build_content_inputs(draft: ProjectOut) -> ContentInputs:
    brief = draft.content_brief
    return ContentInputs(
        core_message=brief.core_message if brief else None,
        cta=brief.cta if brief else None,
        topic=brief.topic if brief else None,
        angle=brief.angle if brief else None,
        emotion=brief.emotion if brief else None,
        tone=brief.tone if brief else None,
        hook_text=_hook_text(draft.beats),
        project_name=draft.project_name,
    )


def _thumbnail_config(draft: ProjectOut, width: int, height: int, headline_text: str | None) -> ThumbnailConfig:
    package_config: PackageProjectConfig = draft.config.package
    count = max(1, package_config.thumbnail_candidate_count)
    if count == 1:
        offsets = (0.5,)
    else:
        span = 0.92 - 0.08
        offsets = tuple(round(0.08 + i * span / (count - 1), 4) for i in range(count))
    return ThumbnailConfig(
        width=width, height=height, candidate_offsets=offsets,
        headline_enabled=package_config.thumbnail_headline_enabled, headline_text=headline_text,
    )


# -- Fingerprints (section 39/40) ------------------------------------------


def thumbnail_fingerprint(video_path: Path, config: ThumbnailConfig) -> str:
    stat = video_path.stat()
    payload = "|".join([
        str(video_path), str(stat.st_mtime_ns), str(stat.st_size),
        str(config.width), str(config.height), ",".join(f"{o:.4f}" for o in config.candidate_offsets),
        str(config.headline_enabled), config.headline_text or "", str(config.headline_max_chars),
        THUMBNAIL_ENGINE_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def metadata_fingerprint(
    inputs: ContentInputs, manual_title: str | None, manual_description: str | None,
    manual_hashtags: list[str] | None, package_config: PackageProjectConfig, language: str,
    duration: float, width: int, height: int,
) -> str:
    payload = "|".join([
        str(asdict(inputs)), manual_title or "", manual_description or "", ",".join(manual_hashtags or []),
        str(package_config.max_hashtags), package_config.platform_profile, language,
        f"{duration:.3f}", str(width), str(height), METADATA_ENGINE_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# -- Aspect ratio label (section 10) ---------------------------------------


def _aspect_ratio_label(width: int, height: int) -> str:
    import math

    divisor = math.gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


# -- Thumbnail generation (section 4-19) -----------------------------------


def _generate_thumbnail(job: VideoComposeJob, config: ThumbnailConfig) -> None:
    video_path = Path(job.output_path)
    work_dir = _output_dir(job) / ".thumbnail_candidates"
    try:
        best_frame = select_thumbnail_frame(video_path, config, work_dir)
        image = build_thumbnail(best_frame, config)
        out_path = thumbnail_path(job)
        tmp_path = out_path.with_suffix(".tmp.jpg")
        save_thumbnail(image, tmp_path)
        validate_thumbnail(tmp_path, expected_width=config.width, expected_height=config.height)
        tmp_path.replace(out_path)
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)


# -- Metadata generation (section 20-30) -----------------------------------


def _generate_metadata(
    job: VideoComposeJob, draft: ProjectOut, inputs: ContentInputs, render_duration: float, width: int, height: int,
) -> PackageMetadata:
    package_config: PackageProjectConfig = draft.config.package
    hashtags = derive_hashtags(inputs, draft.manual_hashtags, package_config.max_hashtags)
    title = derive_title(inputs, draft.manual_title, max_chars=70)
    description = derive_description(
        inputs, draft.manual_description, hashtags,
        cta_enabled=draft.config.content.cta_enabled, max_chars=500,
    )
    metadata = PackageMetadata(
        title=title, description=description, hashtags=hashtags,
        language=draft.config.content.language, category=derive_category(inputs),
        platform_profile=package_config.platform_profile, duration=render_duration,
        width=width, height=height, aspect_ratio=_aspect_ratio_label(width, height),
        thumbnail=_THUMBNAIL_FILENAME, video=Path(job.output_path).name,
    )
    out_path = metadata_path(job)
    tmp_path = out_path.with_suffix(".tmp.json")
    tmp_path.write_text(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(out_path)
    return metadata


# -- The stage itself (section 37/40/41/43) --------------------------------


def generate_project_package(project_id: int, settings: Settings) -> bool:
    """Idempotent, and independently so per artifact (section 40/41/49):
    the thumbnail and metadata each have their own fingerprint, so a
    description-only edit never touches thumbnail.jpg and a final-video
    change never touches metadata.json unless the content itself also
    changed. Returns whether anything was actually (re)written this call.

    Section 37: generate -> validate -> commit -- nothing under the
    canonical `thumbnail.jpg`/`metadata.json` names is ever a partial
    write (atomic tmp-then-replace for both, matching every earlier
    stage's own convention).
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return False  # Render hasn't produced a valid final video yet -- not an error

    video_path = Path(job.output_path)
    if not video_path.exists():
        return False  # Project.render_job_id/job row exist but the file itself is gone -- reconciliation's job, not a hard failure here

    inputs = build_content_inputs(draft)
    render_meta = _read_render_metadata(job)
    duration = float(render_meta.get("duration") or 0.0)
    width = int(render_meta.get("width") or get_render_profile(draft.config.render.profile).width)
    height = int(render_meta.get("height") or get_render_profile(draft.config.render.profile).height)

    # The thumbnail headline and the metadata title are deliberately the
    # SAME underlying message (section 14: "do not invent a completely
    # different message") -- computed once, shortened+upper-cased only
    # for the on-image overlay.
    try:
        title_for_headline = derive_title(inputs, draft.manual_title, max_chars=70)
    except MetadataError:
        title_for_headline = None
    headline_text = shorten_headline(title_for_headline, 40) if title_for_headline else None

    thumb_config = _thumbnail_config(draft, width, height, headline_text)
    thumb_fp = thumbnail_fingerprint(video_path, thumb_config)
    meta_fp = metadata_fingerprint(
        inputs, draft.manual_title, draft.manual_description, draft.manual_hashtags,
        draft.config.package, draft.config.content.language, duration, width, height,
    )

    cache = _load_cache(job)
    thumb_valid = thumbnail_path(job).exists()
    meta_valid = metadata_path(job).exists()
    thumb_cached = bool(cache) and cache.get("thumbnail_fingerprint") == thumb_fp and thumb_valid
    meta_cached = bool(cache) and cache.get("metadata_fingerprint") == meta_fp and meta_valid

    if thumb_cached and meta_cached:
        return False  # section 40: nothing changed, both artifacts already valid and current

    changed = False
    if not thumb_cached:
        try:
            _generate_thumbnail(job, thumb_config)
        except ThumbnailError:
            raise
        changed = True
    if not meta_cached:
        try:
            _generate_metadata(job, draft, inputs, duration, width, height)
        except MetadataError:
            raise
        changed = True

    _save_cache(job, thumbnail_fingerprint=thumb_fp, metadata_fingerprint=meta_fp, engine_version=METADATA_ENGINE_VERSION)
    return changed


def validate_package(project_id: int, settings: Settings) -> None:
    """Section 34/43: raises PackageError(PACKAGE_INCOMPLETE) if any
    required artifact is missing, PackageError(PACKAGE_VALIDATION_FAILED)
    if one exists but fails structural validation. Never silently accepts
    a partial package.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        raise PackageError(PACKAGE_INCOMPLETE, "No completed render exists for this project yet.")

    video_path = Path(job.output_path)
    if not video_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"final video is missing: {video_path}")

    thumb_path = thumbnail_path(job)
    if not thumb_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"thumbnail.jpg is missing: {thumb_path}")
    render_meta = _read_render_metadata(job)
    width = int(render_meta.get("width") or get_render_profile(draft.config.render.profile).width)
    height = int(render_meta.get("height") or get_render_profile(draft.config.render.profile).height)
    try:
        validate_thumbnail(thumb_path, expected_width=width, expected_height=height)
    except ThumbnailError as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, str(exc)) from exc

    meta_path = metadata_path(job)
    if not meta_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"metadata.json is missing: {meta_path}")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, f"metadata.json does not parse: {exc}") from exc

    for key in ("title", "description", "hashtags"):
        if key not in data:
            raise PackageError(PACKAGE_VALIDATION_FAILED, f"metadata.json is missing required key {key!r}")
    try:
        from app.modules.metadata.service import validate_description, validate_hashtags, validate_title

        validate_title(data["title"], max_chars=200)
        validate_description(data["description"], max_chars=2000)
        validate_hashtags(data["hashtags"], max_count=max(1, len(data["hashtags"])))
    except MetadataError as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, str(exc)) from exc


def package_is_valid(project_id: int, settings: Settings) -> bool:
    try:
        validate_package(project_id, settings)
    except PackageError:
        return False
    return True


def package_was_attempted(project_id: int, library_dir: str) -> bool:
    """Whether a prior Package stage run ever claimed to have produced
    this project's package -- mirrors every earlier stage's own
    *_was_attempted (Voice/Motion/Audio/Captions).
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return False
    return _cache_path(job).exists()


# -- API --------------------------------------------------------------------


class PackageOut(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] = []
    language: str | None = None
    category: str | None = None
    platform_profile: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    thumbnail_path: str | None = None
    video_path: str | None = None
    thumbnail_media_url: str | None = None
    video_media_url: str | None = None
    manual_title: str | None = None
    manual_description: str | None = None
    manual_hashtags: list[str] | None = None
    is_complete: bool = False


class PackageOverridesIn(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    clear_title: bool = False
    clear_description: bool = False
    clear_hashtags: bool = False


def _to_media_url(file_path: str, library_dir: Path) -> str | None:
    # Duplicates video_composer.schemas._to_media_url's own tiny helper --
    # this composition root already depends on video_composer.models, but
    # that private function isn't part of this module's own contract, so
    # this 3-line transform is reproduced rather than reached into.
    try:
        rel = Path(file_path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


@router.get("/projects/{project_id}/package", response_model=PackageOut)
def get_project_package(project_id: int, settings: Settings = Depends(get_settings)) -> PackageOut:
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    out = PackageOut(
        manual_title=draft.manual_title, manual_description=draft.manual_description,
        manual_hashtags=draft.manual_hashtags,
    )
    if job is None:
        return out
    library_dir = Path(settings.library_dir)
    meta_path = metadata_path(job)
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            out = out.model_copy(update={
                "title": data.get("title"), "description": data.get("description"),
                "hashtags": data.get("hashtags", []), "language": data.get("language"),
                "category": data.get("category"), "platform_profile": data.get("platform_profile"),
                "duration": data.get("duration"), "width": data.get("width"), "height": data.get("height"),
                "aspect_ratio": data.get("aspect_ratio"), "video_path": job.output_path,
                "video_media_url": _to_media_url(job.output_path, library_dir),
            })
        except (OSError, json.JSONDecodeError):
            pass
    thumb_path = thumbnail_path(job)
    if thumb_path.exists():
        out = out.model_copy(update={
            "thumbnail_path": str(thumb_path), "thumbnail_media_url": _to_media_url(str(thumb_path), library_dir),
        })
    out = out.model_copy(update={"is_complete": package_is_valid(project_id, settings)})
    return out


@router.put("/projects/{project_id}/package-overrides", response_model=dict)
def set_package_overrides(project_id: int, payload: PackageOverridesIn) -> dict:
    """Section 48: manual edits always win over the generated values.
    `clear_*` explicitly resets that field back to "derive it" -- omitting
    a field entirely leaves it untouched (see set_project_package_overrides's
    own _UNSET-sentinel reasoning).
    """
    title = None if payload.clear_title else (payload.title if payload.title is not None else _UNSET)
    description = None if payload.clear_description else (payload.description if payload.description is not None else _UNSET)
    hashtags = None if payload.clear_hashtags else (payload.hashtags if payload.hashtags is not None else _UNSET)
    set_project_package_overrides(project_id, title=title, description=description, hashtags=hashtags)
    return {"project_id": project_id}


@router.post("/projects/{project_id}/regenerate-package", response_model=dict)
def regenerate_package(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses both artifacts' own cache on
    purpose, matching every earlier stage's own regenerate-* precedent.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is not None:
        _cache_path(job).unlink(missing_ok=True)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}


@router.post("/projects/{project_id}/regenerate-thumbnail", response_model=dict)
def regenerate_thumbnail(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Section 49: an independent action -- never reruns Script/Voice/
    Motion/Render, and (unlike regenerate-package) leaves metadata.json's
    own cache untouched if it's still valid.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return {"project_id": project_id, "generated": False}
    cache = _load_cache(job) or {}
    cache.pop("thumbnail_fingerprint", None)
    _save_cache(job, **cache)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}


@router.post("/projects/{project_id}/regenerate-metadata", response_model=dict)
def regenerate_metadata(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return {"project_id": project_id, "generated": False}
    cache = _load_cache(job) or {}
    cache.pop("metadata_fingerprint", None)
    _save_cache(job, **cache)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}
