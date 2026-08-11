from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CAPTION_PRESETS = ("emotional", "cinematic", "word_highlight", "big_statement", "quote")

VIDEO_COMPOSE_STATUSES = (
    "queued",
    "merging",
    "narrating",
    "subtitling",
    "mixing_audio",
    "finalizing",
    "completed",
    "failed",
)


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

    # User-chosen destination folder for the final video. None means "use
    # the default location" (library/_video_composer/job_<id>/output/) --
    # same convention as SceneCutJob.requested_output_dir.
    requested_output_dir: Mapped[str | None] = mapped_column(String, nullable=True)

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
