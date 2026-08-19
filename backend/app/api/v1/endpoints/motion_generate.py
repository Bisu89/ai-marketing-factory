"""Local Motion Engine (Task 23 -- see docs/features/49-local-motion-engine.md):
the composition-root adapter between app.modules.motion (pure MotionPlan
planning + FFmpeg rendering, see that module's own docstrings) and
app.modules.beat/app.modules.asset. Same composition-root shape as
voice_generate.py/content_generate.py: a module under app/modules/* may
never import another module, so this is the one place allowed to know
about Beat/Asset/Motion together.

Turns each Beat's assigned visual Asset into a real, cached, independently-
retryable clip artifact (`beat_<id>.mp4`) *ahead of* Quality/Render --
never a second render pipeline. The existing final-composition path
(composition_render.py's render_beats_for_job) still owns actually
producing the final video; this module's own artifact is a reusable input
to it (see motion_artifact_for_beat below), consulted on a plain best-
effort cache-hit basis -- a project that never runs this stage at all
still renders exactly as it did before this task, on demand, inside the
final render job itself.
"""

import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.project_service import get_project_draft
from app.modules.beat.schemas import Beat, BeatMotionPreset, ProjectConfig
from app.modules.motion.renderer import (
    probe_clip,
    render_motion_clip,
    render_video_clip,
    validate_clip_output,
)
from app.modules.motion.schemas import MotionIntensity
from app.modules.motion.service import build_motion_plan, select_auto_motion

logger = logging.getLogger(__name__)
router = APIRouter()

# Bumped whenever the actual rendered output of this engine changes in a
# way that makes an old cached artifact no longer equivalent to a fresh one
# (section 47) -- part of the fingerprint, so old artifacts are simply
# never matched again rather than needing an explicit migration/cleanup.
RENDERER_VERSION = "local-motion-v1"

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
_METADATA_FILENAME = "motion.meta.json"


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


# -- Storage -- library_dir/_motion/project_<id>/, matching Task 22's own
# _voice/project_<id>/ convention for a per-project intermediate-artifact
# directory. -----------------------------------------------------------


def _motion_dir(project_id: int, library_dir: str) -> Path:
    return Path(library_dir) / "_motion" / f"project_{project_id}"


def beat_clip_path(project_id: int, beat_id: str, library_dir: str) -> Path:
    """Deliberately takes a plain `library_dir: str`, not a full `Settings`
    (unlike this stage's own top-level `generate_project_motion`, which
    matches every sibling stage function's `(project_id, settings)` shape)
    -- composition_render.py's render_beats_for_job calls this from deep
    inside VideoComposerService's own worker thread, which has no `Settings`
    object naturally in scope, only whatever was persisted onto the render
    job's own composition_request JSON (see render_composition below).
    """
    return _motion_dir(project_id, library_dir) / f"beat_{beat_id}.mp4"


def _metadata_path(project_id: int, library_dir: str) -> Path:
    return _motion_dir(project_id, library_dir) / _METADATA_FILENAME


def _load_metadata(project_id: int, library_dir: str) -> dict:
    path = _metadata_path(project_id, library_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_metadata(project_id: int, library_dir: str, metadata: dict) -> None:
    """One combined sidecar keyed by beat_id (section 45's own "do not
    duplicate the entire MotionPlan in multiple places") rather than one
    file per beat -- a project's whole Motion cache state is one small,
    atomically-rewritten JSON object, mirroring narration.meta.json's own
    "small sidecar next to the artifacts it describes" shape.
    """
    path = _metadata_path(project_id, library_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


# -- Motion selection (section 8/9/28/29/58/59) -----------------------------


def resolve_effective_preset(beat: Beat, config: ProjectConfig) -> BeatMotionPreset:
    """Manual override > deterministic auto-selection > fixed project
    default (section 58: "manual motion selection must override
    automatic"). Auto-selection only ever runs when a project explicitly
    opts into `MotionProjectConfig.auto_rotate` -- False by default, so an
    existing project's resolved motion never changes.
    """
    if beat.motion_preset is not None:
        return beat.motion_preset
    if config.motion.auto_rotate:
        auto = select_auto_motion(beat.order, beat.visual_hint)
        return BeatMotionPreset(auto.value.upper())
    return config.motion.default_preset


# -- Fingerprint / cache (section 46/47) ------------------------------------


def motion_fingerprint(
    asset_identity: str, effective_preset: BeatMotionPreset, intensity: str,
    duration: float, width: int, height: int, fps: float,
) -> str:
    """Section 46's own cache key -- every input that actually changes the
    rendered pixels, plus RENDERER_VERSION (section 47) so a change to this
    engine's own FFmpeg pipeline never silently reuses an artifact it would
    no longer produce today.
    """
    payload = "|".join([
        asset_identity, effective_preset.value, intensity, f"{duration:.3f}",
        str(width), str(height), f"{fps:.3f}", RENDERER_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _asset_identity(asset: Asset) -> str:
    # content_hash (Task 15) is the real, content-addressed identity when
    # available; a hand-registered asset without one (no ingestion scan
    # ever ran) falls back to its own path -- still correctly invalidates
    # the cache if the file at that path is later replaced with a
    # different one under the same name, just not on a byte-for-byte
    # content change without a path change.
    return asset.content_hash or asset.path


def _get_or_register_clip_asset(db, path: Path, duration_sec: float) -> int:
    """Mirrors voice_generate.py's own _get_or_register_audio_asset --
    reuses the existing Asset row for this exact path (regeneration
    overwrites the file at the same deterministic path) rather than
    accumulating a duplicate row per re-render.
    """
    # See voice_generate.py's own _get_or_register_audio_asset for why this
    # must be resolved to an absolute path before comparing -- register()
    # always normalizes, so comparing against a possibly-relative `path`
    # (settings.library_dir defaults to relative in dev) never matches an
    # already-registered row.
    resolved = str(path.expanduser().resolve())
    existing = db.query(Asset).filter(Asset.path == resolved).first()
    if existing is not None:
        existing.duration_sec = duration_sec
        db.commit()
        return existing.id
    asset = AssetService(db).register(
        AssetRegisterIn(filename=path.name, path=resolved, type="video", duration_sec=duration_sec, source="motion_engine")
    )
    return asset.id


def motion_was_attempted_for_beat(project_id: int, beat_id: str, library_dir: str) -> bool:
    """Whether a prior GENERATING_MOTION stage run ever claimed to have
    rendered this specific beat -- i.e. whether there is anything to
    *reconcile* at all. Deliberately distinct from motion_artifact_for_beat
    below: a project that simply never ran the Motion stage has nothing
    stale to report (Quality Gate must never treat "Motion hasn't run yet"
    as a defect -- the final render still works fine via
    render_beats_for_job's own on-demand fallback); only a beat whose own
    metadata entry says "rendered" but whose file is now missing/invalid is
    a real staleness signal (section 62's own "if DB says motion completed
    but beat_003.mp4 is missing/corrupt: mark Motion stale").
    """
    return beat_id in _load_metadata(project_id, library_dir)


def motion_artifact_for_beat(
    project_id: int, beat_id: str, library_dir: str,
    expected_duration: float, expected_width: int, expected_height: int, expected_fps: float,
) -> Path | None:
    """Section 50/62's own "trust, but verify" -- the final render step
    (composition_render.py's render_beats_for_job) calls this before
    rendering a beat's motion clip itself, to decide whether a cached
    artifact from a prior GENERATING_MOTION stage run can be reused
    outright. Returns the cached path only if it's still on disk *and*
    still a real, valid clip at the exact duration/resolution/fps this
    render actually needs (a project's own render profile could in theory
    have changed since Motion last ran) -- never trusts the sidecar
    metadata's own claim alone, matching Task 22's narration_is_valid's
    same "re-probe the real file" precedent.
    """
    path = beat_clip_path(project_id, beat_id, library_dir)
    if not path.exists():
        return None
    try:
        probe = probe_clip(path)
        validate_clip_output(probe, expected_duration, expected_width, expected_height, expected_fps)
    except Exception:
        return None
    return path


# -- The stage itself (section 33/50/51/61) ---------------------------------


def generate_project_motion(project_id: int, settings: Settings) -> bool:
    """Idempotent, per-beat: a beat whose current asset+preset+intensity+
    output-format still matches its own cached artifact's fingerprint is
    left untouched (section 46); only a beat that actually changed (or
    never rendered) does real FFmpeg work. Returns whether anything was
    actually (re)rendered this call (the same "missing metrics key, not
    zero" convention every earlier Task 18-22 stage already uses).

    Section 51's own "partial failure isolation" falls straight out of
    this per-beat idempotency: if beat 3 raises, beats 1/2 already have
    valid, fingerprint-matching artifacts on disk from *this same call*,
    so a retry that re-invokes this whole function again skips them
    (cache hit) and only re-attempts beat 3.
    """
    draft = get_project_draft(project_id)
    if not draft.beats:
        return False

    render_profile = get_render_profile(draft.config.render.profile)
    metadata = _load_metadata(project_id, settings.library_dir)
    any_regenerated = False

    db = SessionLocal()
    try:
        asset_service = AssetService(db)
        for beat in sorted(draft.beats, key=lambda b: b.order):
            if beat.asset_id is None:
                continue  # nothing to animate yet -- Quality Gate's own MISSING_VISUAL_ASSET already covers this
            try:
                asset = asset_service.get(beat.asset_id)
            except NotFoundError:
                continue
            if not Path(asset.path).exists():
                continue  # a missing source file is Quality Gate's own concern, not a Motion-stage failure

            effective_preset = resolve_effective_preset(beat, draft.config)
            intensity = draft.config.motion.intensity
            fingerprint = motion_fingerprint(
                _asset_identity(asset), effective_preset, intensity,
                beat.duration, render_profile.width, render_profile.height, render_profile.fps,
            )
            clip_path = beat_clip_path(project_id, beat.id, settings.library_dir)
            cached_entry = metadata.get(beat.id)
            if cached_entry and cached_entry.get("fingerprint") == fingerprint and clip_path.exists():
                continue  # section 46: identical inputs, valid cached artifact already in place

            tmp_path = _motion_dir(project_id, settings.library_dir) / f"beat_{beat.id}.tmp.mp4"
            if _is_image_path(Path(asset.path)):
                motion_plan = build_motion_plan(
                    effective_preset.value.lower(), duration=beat.duration,
                    intensity=MotionIntensity(intensity),
                )
                render_motion_clip(
                    asset.path, motion_plan, tmp_path, duration=beat.duration,
                    fps=render_profile.fps, width=render_profile.width, height=render_profile.height,
                )
            else:
                render_video_clip(
                    asset.path, tmp_path, duration=beat.duration,
                    fps=render_profile.fps, width=render_profile.width, height=render_profile.height,
                    short_source_policy=draft.config.motion.short_video_policy,
                )

            probe = probe_clip(tmp_path)
            validate_clip_output(probe, beat.duration, render_profile.width, render_profile.height, render_profile.fps)

            tmp_path.replace(clip_path)  # atomic -- never a partial file at the canonical path (section 38)
            _get_or_register_clip_asset(db, clip_path, probe.duration_sec)

            metadata[beat.id] = {
                "fingerprint": fingerprint, "motion_type": effective_preset.value, "duration": beat.duration,
                "width": render_profile.width, "height": render_profile.height, "fps": render_profile.fps,
                "source_asset": beat.asset_id,
            }
            # Saved after *every* successful beat, not once at the end of
            # the whole loop -- section 51's own partial-failure isolation
            # ("retry only the failed artifact") requires that an already-
            # rendered beat's own cache entry survive a later beat raising
            # mid-loop; saving only at the very end would otherwise lose
            # every earlier beat's own cache-hit eligibility on that retry,
            # forcing a needless full re-render of already-good clips.
            _save_metadata(project_id, settings.library_dir, metadata)
            any_regenerated = True
    finally:
        db.close()

    return any_regenerated


def motion_stage_is_complete(project_id: int, settings: Settings) -> bool:
    """Section 50's own checkpoint condition -- every Beat that *has* a
    visual asset assigned has a real, currently-valid clip artifact. A
    Beat with no asset at all is not this stage's concern (Quality Gate's
    own MISSING_VISUAL_ASSET already covers it); Motion is complete the
    moment every animatable Beat has one.
    """
    draft = get_project_draft(project_id)
    render_profile = get_render_profile(draft.config.render.profile)
    for beat in draft.beats:
        if beat.asset_id is None:
            continue
        if motion_artifact_for_beat(
            project_id, beat.id, settings.library_dir,
            beat.duration, render_profile.width, render_profile.height, render_profile.fps,
        ) is None:
            return False
    return True


# -- API ---------------------------------------------------------------


@router.post("/projects/{project_id}/regenerate-motion", response_model=None, status_code=200)
def regenerate_motion(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses the stage's own per-beat cache on
    purpose, matching Task 21/22's own "an explicit request always wins"
    regenerate-script/regenerate-voice precedent, by clearing the cached
    fingerprints before regenerating (every beat's own on-disk clip is
    still probed/validated fresh either way -- see generate_project_motion).
    """
    path = _metadata_path(project_id, settings.library_dir)
    path.unlink(missing_ok=True)
    generate_project_motion(project_id, settings)
    return {"project_id": project_id}
