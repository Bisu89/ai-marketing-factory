"""Voice Factory (Task 22 -- see docs/features/48-voice-factory-local-tts.md):
the composition-root adapter between the new app.modules.voice (TTS
provider abstraction, audio analysis, beat timing -- all pure, zero
cross-module imports) and app.modules.beat/app.modules.asset. Same
"app/api/v1/endpoints/* may import multiple modules; the modules
themselves may never import each other" shape every earlier Task 18-21
stage adapter (beat_generate.py, content_generate.py) already established.

The key integration decision: a per-beat narration segment is registered
as a real, ordinary local Asset (type="audio") and assigned to
Beat.narration_asset_id -- app.modules.video_composer's existing
narration_mode="local" render path (Task 9, see
docs/features/36-audio-pipeline.md) already knows how to consume this
end-to-end with ZERO changes. This module's own job stops at "produce a
real narration.wav and real per-beat timing, and make it available to the
existing render pipeline" (section 44) -- it never touches FFmpeg
composition/mixing/mux itself.
"""

import hashlib
import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.session import SessionLocal
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, VoiceProjectConfig
from app.modules.voice.audio_analysis import cut_segment, normalize_audio, probe_audio, validate_audio
from app.modules.voice.providers import LocalTTSProvider, get_provider
from app.modules.voice.schemas import BeatTimingInput
from app.modules.voice.timing import compute_beat_timing

logger = logging.getLogger(__name__)
router = APIRouter()

_AUDIO_FILENAME = "narration.wav"
_METADATA_FILENAME = "narration.meta.json"


# -- Storage (section 29/30) -- library_dir/_voice/project_<id>/, matching
# this codebase's own established `_beat`/`_video_composer` underscore-
# prefixed convention for internal artifact directories. -----------------


def _voice_dir(project_id: int, settings: Settings) -> Path:
    return Path(settings.library_dir) / "_voice" / f"project_{project_id}"


def narration_wav_path(project_id: int, settings: Settings) -> Path:
    return _voice_dir(project_id, settings) / _AUDIO_FILENAME


def _metadata_path(project_id: int, settings: Settings) -> Path:
    return _voice_dir(project_id, settings) / _METADATA_FILENAME


def _beat_segment_path(project_id: int, beat_id: str, settings: Settings) -> Path:
    return _voice_dir(project_id, settings) / f"beat_{beat_id}.wav"


# -- Script input + fingerprint (section 8, 30-33) --------------------------


def build_narration_text(beats: list[Beat]) -> str:
    """One continuous script for the whole project, in Beat order (section
    8: always the *current* script -- read fresh from the BeatPlan on
    every call, never a cached AI response). A single space between beats
    keeps word-tokenization aligned with plain `text.split()` counts, which
    the timing algorithm's own word-count weighting/alignment depends on
    (see app.modules.voice.timing).
    """
    ordered = sorted(beats, key=lambda b: b.order)
    parts = [b.narration.strip() for b in ordered if b.narration and b.narration.strip()]
    return " ".join(parts)


def voice_fingerprint(script_text: str, voice: VoiceProjectConfig) -> str:
    """Section 32 -- the same deterministic-hash idea
    content_generate.py's own content_fingerprint already uses, over every
    input that actually affects the synthesized audio. A change to any one
    of them changes the key, so a stale cache is never manually cleaned up
    (section 33) -- it's simply never matched again.
    """
    normalized_text = re.sub(r"\s+", " ", script_text.strip().lower())
    payload = "|".join([
        normalized_text, voice.provider, voice.voice_id, voice.language, f"{voice.speed:.2f}", str(voice.pitch),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_metadata(project_id: int, settings: Settings) -> dict | None:
    path = _metadata_path(project_id, settings)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_metadata(project_id: int, settings: Settings, **fields) -> None:
    """Section 28's own "persist voice metadata" -- provider/voice/language/
    speed/duration/sample_rate/channels/fingerprint, colocated with the WAV
    it describes (never audio *binary* in SQLite, section 28/29 -- this is
    a small JSON sidecar, the filesystem reference itself already lives on
    Beat.narration_asset_id -> Asset.path).
    """
    path = _metadata_path(project_id, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fields, indent=2), encoding="utf-8")


def _get_or_register_audio_asset(db, path: Path, duration_sec: float) -> int:
    """A per-beat segment lives at a deterministic path (section 30: no
    accidental reuse of a stale file -- regeneration always atomically
    replaces the *content* at the same path, see cut_segment's own
    overwrite). Reuses the existing Asset row for that path if one is
    already registered (a second raw `AssetService.register()` call on the
    same path would otherwise hit its own unique-path IntegrityError) --
    never leaves orphaned Asset rows accumulating across regenerations.
    """
    # AssetService.register() always normalizes to an absolute, resolved
    # path before storing (asset/service.py's own _normalize_path) --
    # settings.library_dir defaults to a relative "./data/library" in dev
    # (see config.py's _default_library_dir), so comparing against the raw,
    # possibly-relative `path` here would never match an already-registered
    # row, falling through to register() and hitting a real "already
    # registered for path" IntegrityError on every regeneration. Resolve
    # first so this check matches what's actually stored.
    resolved = str(path.expanduser().resolve())
    existing = db.query(Asset).filter(Asset.path == resolved).first()
    if existing is not None:
        existing.duration_sec = duration_sec
        db.commit()
        return existing.id
    asset = AssetService(db).register(
        AssetRegisterIn(filename=path.name, path=resolved, type="audio", duration_sec=duration_sec, source="voice_factory")
    )
    return asset.id


# -- The stage itself (section 9/10/42) --------------------------------


def generate_project_narration(project_id: int, settings: Settings) -> bool:
    """Mirrors _stage_generate_content/_stage_generate_beats' exact
    idempotent shape (factory_pipeline.py): reuse a valid cached artifact
    whenever the current script + voice settings still match it (section
    17/42), regenerate whenever they don't. Returns whether real synthesis
    actually ran (the same "missing metrics key, not zero" convention
    every earlier stage already uses).
    """
    draft = get_project_draft(project_id)
    if not draft.config.audio.narration_enabled:
        return False  # section 42: narration disabled for this project -- nothing to voice
    if not draft.beats:
        return False  # defensive -- BEATS always runs first in the real pipeline

    full_text = build_narration_text(draft.beats)
    if not full_text.strip():
        return False  # no narration text anywhere -- the Quality Gate's own MISSING_NARRATION already covers this

    voice_config = draft.config.voice
    fingerprint = voice_fingerprint(full_text, voice_config)
    narration_wav = narration_wav_path(project_id, settings)
    metadata = _load_metadata(project_id, settings)
    fingerprint_matches = metadata is not None and metadata.get("fingerprint") == fingerprint and narration_wav.exists()

    already_assigned = all(
        b.narration_asset_id is not None and b.start is not None and b.end is not None for b in draft.beats
    )
    if already_assigned and fingerprint_matches:
        return False  # section 32/58: identical inputs, valid cached artifact, already applied to every beat

    word_timestamps = None
    if fingerprint_matches:
        # The expensive part (real synthesis) can be skipped; the cheap
        # part (per-beat cutting + asset assignment) still needs to run,
        # e.g. a retry that regenerated the audio once already but never
        # finished writing the per-beat Beat fields.
        probe = probe_audio(narration_wav)
    else:
        provider = get_provider(voice_config.provider)
        raw_output = _voice_dir(project_id, settings) / "narration.raw.tmp.wav"
        result = provider.synthesize(full_text, voice_config.voice_id, voice_config.language, voice_config.speed, raw_output)

        tmp_wav = _voice_dir(project_id, settings) / "narration.tmp.wav"
        normalize_audio(Path(result.path), tmp_wav)
        probe = probe_audio(tmp_wav)
        validate_audio(probe)  # raises before anything durable is written -- Task 19's own "validate, then persist" order

        tmp_wav.replace(narration_wav)  # atomic (section 31) -- never a partial file at the canonical path
        Path(result.path).unlink(missing_ok=True)
        word_timestamps = result.word_timestamps or None

    beat_inputs = [BeatTimingInput(beat_id=b.id, text=b.narration or "") for b in draft.beats]
    timings = compute_beat_timing(
        beat_inputs, probe.duration_sec, min_beat_duration=settings.voice_min_beat_duration, word_timestamps=word_timestamps
    )
    timing_by_id = {t.beat_id: t for t in timings}

    db = SessionLocal()
    try:
        updated_beats: list[Beat] = []
        for beat in draft.beats:
            timing = timing_by_id[beat.id]
            segment_path = _beat_segment_path(project_id, beat.id, settings)
            cut_segment(narration_wav, segment_path, timing.start, timing.end)
            asset_id = _get_or_register_audio_asset(db, segment_path, timing.duration)
            updated_beats.append(beat.model_copy(update={
                "narration_asset_id": asset_id, "start": timing.start, "end": timing.end, "duration": timing.duration,
            }))
    finally:
        db.close()

    plan = BeatPlan(
        script_text=draft.script_text, beats=updated_beats, project_name=draft.project_name, config=draft.config,
        idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
    )
    update_project_beat_plan(project_id, plan)

    _save_metadata(
        project_id, settings,
        fingerprint=fingerprint, provider=voice_config.provider, voice_id=voice_config.voice_id,
        language=voice_config.language, speed=voice_config.speed, pitch=voice_config.pitch,
        duration_sec=probe.duration_sec, sample_rate=probe.sample_rate, channels=probe.channels,
        external_api_calls=1 if voice_config.provider == "edge_tts" else 0,
    )
    return True


def narration_is_valid(project_id: int, settings: Settings) -> bool:
    """Section 52's own "restart validation" -- narration.wav must still
    exist and pass the same real validation it did at generation time, not
    merely be present in the DB/checkpoint metadata. Used by
    factory_pipeline.py's crash-recovery reconciliation before trusting a
    Voice checkpoint that claims COMPLETED.
    """
    narration_wav = narration_wav_path(project_id, settings)
    if not narration_wav.exists():
        return False
    try:
        probe = probe_audio(narration_wav)
        validate_audio(probe)
    except Exception:
        return False
    return True


# -- API: explicit "Regenerate Voice" + voice listing (sections 15/45/46) --


@router.post("/projects/{project_id}/regenerate-voice", response_model=None, status_code=200)
def regenerate_voice(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses the stage's own idempotent reuse
    check on purpose (same "an explicit request always wins" precedent
    content_generate.py's own regenerate-script endpoint already
    established), by clearing the cached fingerprint before regenerating.
    """
    _metadata_path(project_id, settings).unlink(missing_ok=True)
    generated = generate_project_narration(project_id, settings)
    if not generated:
        raise ValidationError("Nothing to regenerate -- this project has narration disabled or no narration text.")
    return {"project_id": project_id}


@router.get("/voice/providers/{provider}/voices", response_model=list[dict])
def list_provider_voices(provider: str) -> list[dict]:
    """Section 45/46's own voice picker -- real, installed voices, never a
    hardcoded list (for "local"; edge_tts's own small, fixed voice set is
    already hardcoded in the frontend today, see providers.py's own
    _default_edge_voice docstring, and is out of this endpoint's scope).
    """
    if provider == "local":
        return LocalTTSProvider().list_voices()
    return []
