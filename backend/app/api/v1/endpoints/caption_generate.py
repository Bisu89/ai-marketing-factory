"""Caption Engine (Task 25 -- see docs/features/51-caption-engine.md): the
composition-root adapter between app.modules.caption (pure segmentation +
ASS serialization, see that module's own docstrings) and app.modules.beat.
Same composition-root shape as voice_generate.py/motion_generate.py/
audio_generate.py.

No ASR, no AI caption API, no live TTS word-boundary call -- captions are
derived entirely from each Beat's own already-final narration text and
absolute [start, end] timing window (settled by Task 22's Voice stage),
exactly matching this task's own "the factory already knows Script + Beat
timing, do not regenerate that from a cloud service" instruction.

Deliberately produces a standalone project-level artifact (`captions.ass`)
and does NOT touch composition_render.py/video_composer's own existing,
separate live caption-burning path -- final video composition is a later
task (per the pipeline diagram), matching the exact same scoping decision
Task 24's audio_master.wav already established for this same reason.
"""

import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.voice_generate import load_word_timestamps
from app.core.config import Settings, get_settings
from app.core.render_profile import get_render_profile
from app.modules.beat.project_service import get_project_draft
from app.modules.beat.schemas import Beat, CaptionsProjectConfig
from app.modules.caption.ass_writer import ENGINE_VERSION, build_ass_content, validate_ass_content
from app.modules.caption.schemas import (
    CAPTION_TIMING_INVALID,
    CaptionError,
    CaptionSegment,
    CaptionSegmentationConfig,
    CaptionWordTiming,
)
from app.modules.caption.segmentation import split_beat_into_segments
from app.modules.voice.schemas import WordTiming

logger = logging.getLogger(__name__)
router = APIRouter()

_METADATA_FILENAME = "captions.meta.json"
_OUTPUT_FILENAME = "captions.ass"


# -- Storage -- library_dir/_captions/project_<id>/, matching Task 22-24's
# own _voice/_motion/_audio/project_<id>/ convention. ---------------------


def _captions_dir(project_id: int, library_dir: str) -> Path:
    return Path(library_dir) / "_captions" / f"project_{project_id}"


def captions_ass_path(project_id: int, library_dir: str) -> Path:
    return _captions_dir(project_id, library_dir) / _OUTPUT_FILENAME


def _metadata_path(project_id: int, library_dir: str) -> Path:
    return _captions_dir(project_id, library_dir) / _METADATA_FILENAME


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


# -- Segmentation adapter (section 4/11/15/16) ------------------------------


def _segmentation_config(config: CaptionsProjectConfig) -> CaptionSegmentationConfig:
    return CaptionSegmentationConfig(
        max_words=config.max_words, max_chars=config.max_chars,
        min_duration_sec=config.min_duration_sec, max_duration_sec=config.max_duration_sec,
        reading_speed_wps=config.reading_speed_wps,
    )


def build_caption_segments(
    beats: list[Beat], config: CaptionsProjectConfig, word_timestamps: list[WordTiming] | None = None,
) -> list[CaptionSegment]:
    """Section 11/15: only Beats with real, Voice-settled timing
    (`start`/`end` both set) are captioned -- a beat Voice hasn't reached
    yet has nothing authoritative to time captions against, and is simply
    skipped (not an error; the stage as a whole reports "nothing to
    caption yet" via generate_project_captions' own empty-segments check).

    Task 62: word_timestamps (this project's own real, measured per-word
    timing, if this project's Voice stage captured any -- see
    load_word_timestamps) is sliced per-Beat by a running word-count
    cursor -- the SAME sequential-count slicing
    voice.timing._timing_from_word_timestamps already used to derive each
    Beat's own start/end in the first place (see build_narration_text's
    own "join every non-blank Beat's narration, in order"). This is
    deliberately NOT a `beat.start <= w.start < beat.end` time-window
    filter: a real bug found verifying this feature -- Voice's own
    min-duration rebalancing (_rebalance_minimum_duration) can shift a
    Beat's final time boundaries away from where its own words actually
    are, so filtering by time silently dropped/misassigned words at a
    beat boundary, undercounting a Beat's own real words and falling back
    to the estimate for it. Cursor slicing is exact by construction --
    it's the same partition Voice itself already computed.
    """
    seg_config = _segmentation_config(config)
    segments: list[CaptionSegment] = []
    cursor = 0
    for beat in sorted(beats, key=lambda b: b.order):
        has_narration = bool(beat.narration and beat.narration.strip())
        count = len(beat.narration.split()) if has_narration else 0

        beat_words: list[CaptionWordTiming] | None = None
        if word_timestamps and has_narration:
            candidate = word_timestamps[cursor:cursor + count]
            if len(candidate) == count:
                beat_words = [CaptionWordTiming(text=w.text, start=w.start, end=w.end) for w in candidate]
        # Advance regardless of whether this Beat ends up captioned below
        # (e.g. Voice hasn't settled its start/end yet) -- the cursor must
        # track build_narration_text's own inclusion rule exactly, or
        # every Beat after a skipped one would slice the wrong words.
        cursor += count

        if beat.start is None or beat.end is None:
            continue
        if not has_narration:
            continue
        segments.extend(
            split_beat_into_segments(beat.id, beat.narration, beat.start, beat.end, seg_config, words=beat_words)
        )
    return segments


def _validate_segment_continuity(segments: list[CaptionSegment], beats_by_id: dict[str, Beat]) -> None:
    """Section 14/15/30: no accidental overlap, strictly inside the owning
    Beat's own window, non-empty text. Raises CaptionError(CAPTION_TIMING_INVALID)
    on the first violation found -- never silently ships invalid timing.
    """
    by_beat: dict[str, list[CaptionSegment]] = {}
    for segment in segments:
        if not segment.text.strip():
            raise CaptionError(CAPTION_TIMING_INVALID, f"Caption segment {segment.id} has empty text.")
        if segment.start < 0 or segment.end <= segment.start:
            raise CaptionError(CAPTION_TIMING_INVALID, f"Caption segment {segment.id} has invalid timing ({segment.start}..{segment.end}).")
        beat = beats_by_id.get(segment.beat_id)
        if beat is not None and beat.start is not None and beat.end is not None:
            if segment.start < beat.start - 1e-6 or segment.end > beat.end + 1e-6:
                raise CaptionError(
                    CAPTION_TIMING_INVALID,
                    f"Caption segment {segment.id} ({segment.start:.2f}..{segment.end:.2f}) escapes its own "
                    f"Beat {beat.id}'s window ({beat.start:.2f}..{beat.end:.2f}).",
                )
        by_beat.setdefault(segment.beat_id, []).append(segment)

    for beat_id, group in by_beat.items():
        ordered = sorted(group, key=lambda s: s.start)
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.start < prev.end - 1e-6:
                raise CaptionError(
                    CAPTION_TIMING_INVALID,
                    f"Caption segments {prev.id} and {cur.id} in Beat {beat_id} overlap "
                    f"({prev.start:.2f}..{prev.end:.2f} vs {cur.start:.2f}..{cur.end:.2f}).",
                )


# -- Fingerprint (section 36/37) --------------------------------------------


def caption_fingerprint(narration_identity: str, config: CaptionsProjectConfig) -> str:
    """Section 37's own cache key -- every input that actually changes the
    generated ASS, plus ENGINE_VERSION so a change to this engine's own
    output format never silently reuses an artifact it would no longer
    produce today.
    """
    payload = "|".join([
        narration_identity, config.preset, str(config.max_words), str(config.max_chars),
        f"{config.min_duration_sec:.3f}", f"{config.max_duration_sec:.3f}", str(config.max_lines),
        f"{config.reading_speed_wps:.3f}", ENGINE_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _narration_identity(beats: list[Beat], word_timestamps: list[WordTiming] | None) -> str:
    # Section 16/38/39: Beat.narration (the final, possibly manually-edited
    # script text) + Beat.start/end (Voice-settled timing) together are
    # the *whole* input this stage depends on -- a script edit or a Voice-
    # driven timing change both change this string, and nothing else does.
    # Task 62: word_timestamps also folded in -- real per-word timing
    # newly becoming available (or changing) for an otherwise-unchanged
    # script/Beat-timing must still invalidate the cache, since it changes
    # this stage's own output (real acoustic positioning vs. the weighted
    # estimate).
    parts = [f"{b.id}:{b.narration or ''}:{b.start}:{b.end}" for b in sorted(beats, key=lambda x: x.order)]
    words_part = "|".join(f"{w.text}:{w.start}:{w.end}" for w in word_timestamps) if word_timestamps else ""
    return "|".join(parts) + "##" + words_part


# -- The stage itself (section 32/33/40/46/47) -------------------------


def generate_project_captions(project_id: int, settings: Settings) -> bool:
    """Idempotent: identical Beat narration/timing + caption config reuses
    the cached artifact untouched (section 37); only a real change
    triggers real regeneration. Returns whether a real ASS file was
    actually (re)written this call (the same "missing metrics key, not
    zero" convention every earlier Task 21-24 stage already uses).

    Section 46: captions_enabled=False skips cleanly, no ASS file at all
    (never an empty placeholder). Section 32: a Beat whose timing Voice
    hasn't settled yet simply isn't captioned this call -- not a failure;
    a later call (once Voice has run) picks it up naturally via the
    fingerprint no longer matching.
    """
    draft = get_project_draft(project_id)
    caption_config = draft.config.captions
    if not caption_config.enabled:
        return False
    if not draft.beats:
        return False

    word_timestamps = load_word_timestamps(project_id, settings)
    narration_identity = _narration_identity(draft.beats, word_timestamps)
    fingerprint = caption_fingerprint(narration_identity, caption_config)
    output_path = captions_ass_path(project_id, settings.library_dir)
    metadata = _load_metadata(project_id, settings.library_dir)

    if metadata and metadata.get("fingerprint") == fingerprint and output_path.exists():
        return False  # section 37: identical inputs, valid cached artifact already in place

    segments = build_caption_segments(draft.beats, caption_config, word_timestamps)
    if not segments:
        return False  # nothing captionable yet (no beat has settled timing, or no narration text)

    beats_by_id = {b.id: b for b in draft.beats}
    _validate_segment_continuity(segments, beats_by_id)

    render_profile = get_render_profile(draft.config.render.profile)
    font_size = max(28, int(render_profile.height * 0.045))
    content = build_ass_content(
        segments, render_profile.width, render_profile.height, font_size,
        preset=caption_config.preset, max_lines=caption_config.max_lines, max_chars=caption_config.max_chars,
    )
    validate_ass_content(content)  # raises before anything durable is written

    captions_dir = _captions_dir(project_id, settings.library_dir)
    captions_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = captions_dir / "captions.tmp.ass"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(output_path)  # atomic -- never a partial file at the canonical path

    _save_metadata(
        project_id, settings.library_dir,
        fingerprint=fingerprint, engine_version=ENGINE_VERSION, preset=caption_config.preset,
        segment_count=len(segments), beat_count=len({s.beat_id for s in segments}),
    )
    return True


def captions_is_valid(project_id: int, settings: Settings) -> bool:
    """Section 51's own "restart validation" -- captions.ass must still
    exist and pass real structural validation, not merely be present in
    checkpoint metadata. Used by factory_pipeline.py's crash-recovery
    reconciliation.
    """
    path = captions_ass_path(project_id, settings.library_dir)
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        validate_ass_content(content)
    except Exception:
        return False
    return True


def captions_was_attempted(project_id: int, library_dir: str) -> bool:
    """Whether a prior Caption stage run ever claimed to have produced
    this project's captions.ass -- mirrors motion_generate.py's own
    motion_was_attempted_for_beat / audio_generate.py's own
    audio_was_attempted: a project that never ran this stage (or has
    captions disabled) has nothing stale to reconcile.
    """
    return _load_metadata(project_id, library_dir) is not None


# -- API -----------------------------------------------------------------


@router.post("/projects/{project_id}/regenerate-captions", response_model=None, status_code=200)
def regenerate_captions(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses the stage's own cache on purpose,
    matching Task 21-24's own "an explicit request always wins"
    regenerate-* precedent.
    """
    _metadata_path(project_id, settings.library_dir).unlink(missing_ok=True)
    generated = generate_project_captions(project_id, settings)
    return {"project_id": project_id, "generated": generated}
