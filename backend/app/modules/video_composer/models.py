from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CAPTION_PRESETS = ("emotional", "cinematic", "word_highlight", "big_statement", "quote")

VIDEO_COMPOSE_STATUSES = (
    "queued",
    "rendering_beats",
    "merging",
    "narrating",
    "subtitling",
    "mixing_audio",
    "finalizing",
    # Task 26 (see docs/features/52-final-composer.md) -- the Final
    # Composer's own single one-pass phase: concat + captions + watermark +
    # audio mux + encode, all in one ffmpeg call. Only entered when
    # VideoComposeJob.audio_master_path is set (a Factory-driven render);
    # every other job still goes through merging/narrating/subtitling/
    # mixing_audio/finalizing exactly as before, unchanged.
    "composing_final",
    "validating",
    "completed",
    "failed",
    "cancelled",
)

# Coarse status (Task 11 -- see docs/features/38-render-job-hardening.md):
# every fine-grained status above collapses to exactly one of these 5. The
# fine statuses remain the persisted source of truth (existing tests, the
# progress UI, and _recover_pending_jobs all key off them) -- this mapping
# is purely a derived, API-facing view (see VideoComposeJobOut.job_status).
COARSE_STATUS = {
    "queued": "QUEUED",
    "rendering_beats": "RUNNING",
    "merging": "RUNNING",
    "narrating": "RUNNING",
    "subtitling": "RUNNING",
    "mixing_audio": "RUNNING",
    "finalizing": "RUNNING",
    "composing_final": "RUNNING",
    "validating": "RUNNING",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
}

# Render phase (Task 11): the 7-phase vocabulary the brief asks for.
# PREFLIGHT has no entry -- it runs synchronously before a job row even
# exists (see composition_render.py's render_composition), so it's never a
# job's own persisted phase; the frontend shows "Preparing..." for that
# window instead (see docs/features/38-render-job-hardening.md).
RENDER_PHASE = {
    "rendering_beats": "RENDER_BEATS",
    "merging": "COMPOSE_VIDEO",
    "narrating": "BUILD_AUDIO",
    "mixing_audio": "BUILD_AUDIO",
    "subtitling": "BURN_CAPTIONS",
    "finalizing": "BURN_CAPTIONS",
    # Task 26 -- one honest label for the Final Composer's own single pass
    # (concat + captions + watermark + audio mux + encode at once), distinct
    # from the older multi-pass COMPOSE_VIDEO/BURN_CAPTIONS phases above,
    # which it never enters.
    "composing_final": "FINAL_COMPOSITION",
    "validating": "VALIDATE_OUTPUT",
}

# A RUNNING job interrupted by a crash is recovered into this state on next
# startup (see VideoComposerService._recover_pending_jobs) -- never
# silently re-queued: an ffmpeg process killed mid-encode can leave
# corrupt/partial intermediates (unlike a resumable HTTP download), so a
# fresh, explicit user Retry is safer than an automatic re-run.
RENDER_INTERRUPTED_ERROR_CODE = "RENDER_INTERRUPTED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoComposeJob(Base):
    """One "merge many clips into a final video" run: concatenates uploaded
    clips (in user-chosen order) with a swipe-left transition between each
    pair (skipped for a single clip -- see VideoComposerService._run_job),
    overlays a fixed title, generates narration (voice/language chosen by the
    caller, see app/modules/video_composer/router.py) + burned-in karaoke
    subtitles from a typed script, and optionally mixes in background
    music. Its own table, no FK into the core Video/Channel schema --
    these aren't Library videos, just standalone compositions -- per the
    app/modules/ extensibility convention.
    """

    __tablename__ = "video_compose_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    script_text: Mapped[str] = mapped_column(String, nullable=False)
    voice: Mapped[str] = mapped_column(String, nullable=False, default="en-US-GuyNeural")

    music_path: Mapped[str | None] = mapped_column(String, nullable=True)
    music_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    transition_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    burn_subtitles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Audio/caption controls (Epic: Video Factory audio + captions). Kept as
    # job-level columns, not request-time-only parameters, so a crash mid-job
    # can still be recovered and re-rendered with the same settings by
    # _recover_pending_jobs() -- the same reasoning voice/music_volume/etc.
    # are already columns, not just constructor arguments.
    narration_volume: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # Mirrors ffmpeg's own sidechaincompress "ratio" parameter directly
    # (1.0 = no ducking, 20.0 = ffmpeg's own maximum) -- see
    # VideoComposerService._mix_audio.
    music_ducking_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    fade_in_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fade_out_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    caption_preset: Mapped[str] = mapped_column(String, nullable=False, default="emotional")
    # One row per SFX cue: [{"path": str, "start_sec": float, "volume": float}, ...].
    # A JSON column, not a child table, matching the precedent in
    # app/modules/asset/models.py (Asset.tags/extra_metadata) for small,
    # non-relational per-row structured data that doesn't need its own
    # queryable identity.
    sfx_cues: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Audio pipeline (Video Factory Epic, Task 36). "tts" (default) is the
    # existing, unchanged behavior: one composition-wide script_text/voice
    # fed to edge_tts. "local" builds a per-beat narration timeline from
    # already-recorded audio files instead -- no network call. "none" skips
    # narration audio entirely (silence for the whole video). Every caller
    # that predates this column (the plain upload-based Video Composer
    # flow) gets "tts" via the column default, so its behavior is
    # unchanged with zero migration.
    narration_mode: Mapped[str] = mapped_column(String, nullable=False, default="tts")
    # One entry per beat, in order: [{"duration": float, "path": str|null}, ...]
    # -- only used when narration_mode="local". Same "JSON column, not a
    # child table" reasoning as sfx_cues above.
    beat_narration_specs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # User-chosen destination folder for the final video. None means "use
    # the default location" (library/_video_composer/job_<id>/output/) --
    # same convention as SceneCutJob.requested_output_dir.
    requested_output_dir: Mapped[str | None] = mapped_column(String, nullable=True)

    # End-to-end pipeline hardening (Task 10 -- see
    # docs/features/37-e2e-pipeline-hardening.md). render_profile names
    # which app.core.render_profile.RenderProfile this job's output must
    # match (checked by _validate_final_output). preflight_seconds is timed
    # by the composition-root adapter (app/api/v1/endpoints/composition_render.py)
    # *before* this job even exists (preflight is a fast, synchronous check
    # run before the job row is created, so a bad request fails immediately
    # instead of queuing a doomed job) -- passed in at create time rather
    # than timed here. beat_render_seconds is now timed by the worker
    # itself (Task 11 moved beat rendering off the request thread and onto
    # the worker -- see RENDER_BEATS in RENDER_PHASE above). Both are None
    # for jobs created via the plain upload-based Video Composer flow.
    render_profile: Mapped[str] = mapped_column(String, nullable=False, default="SOCIAL_VERTICAL")
    preflight_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    beat_render_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Render job hardening (Task 11). The full original render request
    # (CompositionRenderRequest as a plain dict: plan/asset_paths/
    # narration_asset_paths/profile) -- lets the worker do the actual
    # per-beat motion rendering itself (composition_render.render_beats_for_job,
    # injected into VideoComposerService as `beat_renderer`, mirroring how
    # app/services/download/engine.py's DownloadEngine takes a pluggable
    # `Downloader` -- see app/main.py) instead of blocking the HTTP request,
    # and lets retry_job() rebuild an equivalent fresh request. None for
    # plain-upload jobs (already have real clips, nothing to re-render) and
    # for jobs created before this task.
    composition_request_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Bare int, no FK (the same "cross-reference within this app without a
    # relationship" convention this codebase already uses for cross-module
    # references -- here it's simply informational, not worth a real FK for
    # a same-table self-reference). Set on a job created via retry_job().
    previous_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Live progress during the RENDER_BEATS phase only -- {"current": 3,
    # "total": 5}. Both None outside that phase. Only ever set to real,
    # known counts (never a guessed/interpolated percentage).
    render_progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    render_progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Final Composer (Task 26 -- see docs/features/52-final-composer.md).
    # When set, this job is entirely driven by already-produced Factory
    # artifacts: no TTS, no local-narration timeline, no _mix_audio -- this
    # file is used directly as the sole final audio track (section 12/30).
    # A sibling of narration_mode "tts"/"local" -- this is
    # narration_mode="precomposed"; every other narration_mode value keeps
    # the original multi-pass pipeline (_run_job branches on this exact
    # value) with zero behavior change.
    audio_master_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # When set (only meaningful together with audio_master_path, and only
    # burned in when burn_subtitles=True), this pre-built ASS file is used
    # directly instead of one generated from word-boundary timing -- no
    # word timestamps exist for a precomposed Audio Master (see
    # app.modules.caption's own module docstring, Task 25).
    captions_ass_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Optional watermark overlay (section 18-23). Position is one of
    # top-left/top-right/bottom-left/bottom-right; opacity in (0, 1];
    # scale is the watermark's target width as a fraction of the output
    # video's own width; margins are in pixels, keeping the mark off the
    # frame edge (section 22's own "safe area").
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    watermark_path: Mapped[str | None] = mapped_column(String, nullable=True)
    watermark_position: Mapped[str] = mapped_column(String, nullable=False, default="bottom-right")
    watermark_opacity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    watermark_scale: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    watermark_margin_x: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    watermark_margin_y: Mapped[int] = mapped_column(Integer, nullable=False, default=24)

    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    subtitle_srt_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clips: Mapped[list["VideoComposeClip"]] = relationship(
        "VideoComposeClip", back_populates="job", order_by="VideoComposeClip.position"
    )

    @property
    def clip_count(self) -> int:
        return len(self.clips)


class VideoComposeClip(Base):
    """One input clip for a VideoComposeJob, in merge order (0-based)."""

    __tablename__ = "video_compose_clip"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("video_compose_job.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    job: Mapped[VideoComposeJob] = relationship("VideoComposeJob", back_populates="clips")
