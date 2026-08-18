"""Audio Master (Task 24 -- see docs/features/50-audio-master.md): the
composition-root adapter between app.modules.audio (pure AudioMixPlan +
FFmpeg mixing + deterministic BGM selection, see that module's own
docstrings) and app.modules.beat/app.modules.asset. Same composition-root
shape as voice_generate.py/motion_generate.py.

Reuses voice_generate.py's own narration_wav_path() directly rather than
re-deriving Voice's storage convention -- a composition-root file
importing another composition-root file is already an established pattern
in this codebase (quality_gate.py's own docstring: "app/api/v1/endpoints/
factory_pipeline.py -- another composition root -- reuses this directly";
composition_render.py already imports motion_generate.py the same way).

Deliberately produces a standalone project-level artifact
(`audio_master.wav`) and nothing else -- it does NOT touch
composition_render.py/video_composer's own existing, separate narration+
music+ducking mix at final-render time (final video composition is
explicitly out of this task's scope; a later COMPOSITE task is what would
wire this artifact into the final render, per the pipeline diagram).
"""

import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.voice_generate import narration_wav_path
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.asset.models import Asset
from app.modules.asset.service import AssetService
from app.modules.audio.renderer import MIX_VERSION, probe_audio, render_audio_master, validate_audio_master
from app.modules.audio.schemas import BGM_NOT_FOUND, AudioError, AudioMixPlan, BgmCandidate
from app.modules.audio.service import select_bgm
from app.modules.beat.project_service import get_project_draft

logger = logging.getLogger(__name__)
router = APIRouter()

_METADATA_FILENAME = "audio_master.meta.json"
_OUTPUT_FILENAME = "audio_master.wav"

# Per-beat narration segments (Task 22) and Motion clips (Task 23) already
# register themselves as ordinary Assets with these `source` values -- BGM
# candidates are real, ordinary type="audio" Assets too (section 5: reuse
# the existing catalog, no separate music database), so this is what
# distinguishes "a user's own BGM track" from "an artifact this pipeline
# generated for itself."
_GENERATED_AUDIO_SOURCES = ("voice_factory", "audio_master")


# -- Storage -- library_dir/_audio/project_<id>/, matching Task 22/23's own
# _voice/_motion/project_<id>/ convention. -------------------------------


def _audio_dir(project_id: int, library_dir: str) -> Path:
    return Path(library_dir) / "_audio" / f"project_{project_id}"


def audio_master_path(project_id: int, library_dir: str) -> Path:
    return _audio_dir(project_id, library_dir) / _OUTPUT_FILENAME


def _metadata_path(project_id: int, library_dir: str) -> Path:
    return _audio_dir(project_id, library_dir) / _METADATA_FILENAME


def _load_metadata(project_id: int, library_dir: str) -> dict | None:
    path = _metadata_path(project_id, library_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_metadata(project_id: int, library_dir: str, **fields) -> None:
    path = _metadata_path(project_id, library_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fields, indent=2), encoding="utf-8")


# -- BGM candidates + fingerprint (section 5/26/27) --------------------


def _bgm_candidates(db) -> list[BgmCandidate]:
    rows = (
        db.query(Asset)
        .filter(Asset.type == "audio")
        .filter(~Asset.source.in_(_GENERATED_AUDIO_SOURCES))
        .all()
    )
    return [
        BgmCandidate(asset_id=row.id, path=row.path, duration_sec=row.duration_sec, tags=list(row.tags or []))
        for row in rows
        if row.effective_status == "ACTIVE"
    ]


def _asset_identity(asset: Asset) -> str:
    # Same convention motion_generate.py's own _asset_identity already
    # uses -- content_hash (Task 15) when available, else the path itself.
    return asset.content_hash or asset.path


def _file_identity(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def audio_fingerprint(
    narration_identity: str, bgm_identity: str | None, narration_volume: float, bgm_volume: float,
    ducking_enabled: bool, ducking_ratio: float, fade_in_sec: float, fade_out_sec: float,
) -> str:
    """Section 26/27's own cache key -- every input that actually changes
    the rendered audio, plus MIX_VERSION so a change to this engine's own
    FFmpeg pipeline never silently reuses an artifact it would no longer
    produce today.
    """
    payload = "|".join([
        narration_identity, bgm_identity or "none", f"{narration_volume:.3f}", f"{bgm_volume:.3f}",
        str(ducking_enabled), f"{ducking_ratio:.3f}", f"{fade_in_sec:.3f}", f"{fade_out_sec:.3f}", MIX_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_bgm_asset(project_id: int, config, db) -> Asset | None:
    """Manual override (section 8) > deterministic auto-selection (section
    7/36/37) > off (section 9, via `music_enabled=False` -- handled by the
    caller before this is ever reached). Raises AudioError(BGM_NOT_FOUND)
    only when a *manual* selection references a real, specific asset that
    no longer exists -- that's a genuine user-facing problem needing
    attention, unlike AUTO finding nothing suitable (section 33/34: never
    block the factory over that).
    """
    audio_config = config.audio
    if audio_config.bgm_mode == "MANUAL":
        if audio_config.bgm_asset_id is None:
            return None
        try:
            asset = AssetService(db).get(audio_config.bgm_asset_id)
        except NotFoundError as exc:
            raise AudioError(BGM_NOT_FOUND, f"Selected BGM asset {audio_config.bgm_asset_id} no longer exists.") from exc
        return asset

    candidates = _bgm_candidates(db)
    picked = select_bgm(candidates, config.content.tone, seed=project_id)
    if picked is None:
        return None
    return db.get(Asset, picked.asset_id)


# -- The stage itself (section 4/30/31/32/47) -------------------------------


def generate_project_audio_master(project_id: int, settings: Settings) -> bool:
    """Idempotent: identical narration + BGM selection + volume/ducking/
    fade config reuses the cached artifact untouched (section 27); only a
    real change triggers a real ffmpeg mix. Returns whether anything was
    actually (re)mixed this call (the same "missing metrics key, not zero"
    convention every earlier Task 21-23 stage already uses).

    A missing `narration.wav` is treated as "nothing to master yet," not a
    failure -- Voice's own stage already has every legitimate reason a
    project might not have one yet (no beats, no narration text, narration
    disabled), and re-deriving those conditions here would duplicate
    Voice's own logic. Section 47's "narration required" only kicks in
    once a narration.wav genuinely exists but fails validation.
    """
    draft = get_project_draft(project_id)
    narration_path = narration_wav_path(project_id, settings)
    if not narration_path.exists():
        return False

    narration_probe = probe_audio(narration_path)
    target_duration = narration_probe.duration_sec

    config = draft.config
    audio_config = config.audio
    metadata = _load_metadata(project_id, settings.library_dir)
    output_path = audio_master_path(project_id, settings.library_dir)

    db = SessionLocal()
    try:
        bgm_asset = None
        bgm_missing = False
        if audio_config.music_enabled:
            bgm_asset = resolve_bgm_asset(project_id, config, db)
            if bgm_asset is None and audio_config.bgm_mode == "AUTO":
                bgm_missing = True

        bgm_path = bgm_asset.path if bgm_asset is not None and Path(bgm_asset.path).exists() else None
        if bgm_asset is not None and bgm_path is None:
            bgm_missing = True  # a resolved asset row whose file is gone -- same "missing" outcome as none found

        narration_identity = _file_identity(narration_path)
        bgm_identity = _asset_identity(bgm_asset) if bgm_path else None
        fingerprint = audio_fingerprint(
            narration_identity, bgm_identity, 1.0, audio_config.music_volume,
            audio_config.ducking, audio_config.ducking_ratio, audio_config.fade_in_sec, audio_config.fade_out_sec,
        )

        if metadata and metadata.get("fingerprint") == fingerprint and output_path.exists():
            return False  # section 27: identical inputs, valid cached artifact already in place

        plan = AudioMixPlan(
            narration_path=str(narration_path), target_duration=target_duration, bgm_path=bgm_path,
            narration_volume=1.0, bgm_volume=audio_config.music_volume,
            ducking_enabled=audio_config.ducking, ducking_ratio=audio_config.ducking_ratio,
            fade_in_sec=audio_config.fade_in_sec, fade_out_sec=audio_config.fade_out_sec,
        )
        tmp_path = _audio_dir(project_id, settings.library_dir) / "audio_master.tmp.wav"
        render_audio_master(plan, tmp_path)

        probe = probe_audio(tmp_path)
        validate_audio_master(probe, target_duration)  # raises before anything durable is written

        tmp_path.replace(output_path)  # atomic -- never a partial file at the canonical path (section 24)

        _save_metadata(
            project_id, settings.library_dir,
            fingerprint=fingerprint, mix_version=MIX_VERSION, duration_sec=probe.duration_sec,
            sample_rate=probe.sample_rate, channels=probe.channels,
            narration_artifact=str(narration_path), bgm_artifact=bgm_path, bgm_asset_id=bgm_asset.id if bgm_asset else None,
            bgm_missing=bgm_missing, bgm_missing_policy=audio_config.bgm_missing_policy,
        )
        return True
    finally:
        db.close()


def audio_master_is_valid(project_id: int, settings: Settings) -> bool:
    """Section 55's own "restart validation" -- audio_master.wav must
    still exist and pass the same real validation it did at generation
    time, not merely be present in checkpoint metadata. Used by
    factory_pipeline.py's crash-recovery reconciliation.
    """
    path = audio_master_path(project_id, settings.library_dir)
    if not path.exists():
        return False
    narration_path = narration_wav_path(project_id, settings)
    if not narration_path.exists():
        return False
    try:
        narration_probe = probe_audio(narration_path)
        probe = probe_audio(path)
        validate_audio_master(probe, narration_probe.duration_sec)
    except Exception:
        return False
    return True


def audio_was_attempted(project_id: int, library_dir: str) -> bool:
    """Whether a prior Audio stage run ever claimed to have produced this
    project's audio_master -- mirrors motion_generate.py's own
    motion_was_attempted_for_beat: a project that never ran this stage has
    nothing stale to reconcile, matching that same reasoning exactly.
    """
    return _load_metadata(project_id, library_dir) is not None


# -- API -----------------------------------------------------------------


@router.post("/projects/{project_id}/regenerate-audio-master", response_model=None, status_code=200)
def regenerate_audio_master(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses the stage's own cache on purpose,
    matching Task 21/22/23's own "an explicit request always wins"
    regenerate-* precedent.
    """
    _metadata_path(project_id, settings.library_dir).unlink(missing_ok=True)
    generated = generate_project_audio_master(project_id, settings)
    return {"project_id": project_id, "generated": generated}
