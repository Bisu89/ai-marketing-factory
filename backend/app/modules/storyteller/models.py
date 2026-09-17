"""Storyteller: paste/upload a script (written externally -- ChatGPT, a
translated novel, anything) -> long-form narrated video, no AI call in
this module at all. Own tables, no FK into any other module -- per
app/modules/README.md, this module must stay fully self-contained, so
"background loop" / "avatar overlay" clips are this module's OWN small
asset table (StorytellerAsset), not a reuse of app.modules.asset.Asset.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STORYTELLER_STATUSES = ("pending", "narrating", "compositing", "completed", "failed")
PENDING_STATUSES = ("pending", "narrating", "compositing")

STORYTELLER_ASSET_KINDS = ("background", "avatar")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StorytellerAsset(Base):
    """A reusable background-loop or avatar-overlay clip, uploaded once and
    picked by id on many episodes. `key_color` is the hex colour ffmpeg's
    colorkey filter should remove for an `avatar` asset (auto-sampled from
    the clip's corner pixel at upload time; nullable/unused for `background`
    assets, which are never keyed)."""

    __tablename__ = "storyteller_asset"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # background | avatar
    media_type: Mapped[str] = mapped_column(String, nullable=False, default="video")  # image | video
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_color: Mapped[str | None] = mapped_column(String, nullable=True)  # "0xRRGGBB", avatar only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


STORYTELLER_LAYOUTS = ("single", "triptych")


class StorytellerEpisode(Base):
    """One narrated long-form episode: pasted/uploaded script -> TTS ->
    (optional) captions -> composited -> final.mp4. Runs on this module's
    own queue + worker thread (StorytellerService), independent of every
    other render engine in this app (VideoComposerService, SceneCutterService,
    ...).

    Two `layout`s:
      "single"   -- one background (loop or still image) + optional avatar
                    overlaid via colour-key, corner-positioned.
      "triptych" -- 3 equal-width panels side by side (left/middle/right
                    asset ids), each an independent clip, no colour-key --
                    the format seen in real competitor "story reading"
                    channels (host panel + an unrelated satisfying/ASMR
                    filler panel + a thematic panel).
    Both layouts optionally burn a top disclaimer line and a bottom
    story-info card (title/author/main character)."""

    __tablename__ = "storyteller_episode"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    voice: Mapped[str] = mapped_column(String, nullable=False, default="vi-VN-HoaiMyNeural")
    narration_rate: Mapped[str] = mapped_column(String, nullable=False, default="+0%")
    burn_captions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    layout: Mapped[str] = mapped_column(String, nullable=False, default="single")

    # layout == "single"
    background_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avatar_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # layout == "triptych"
    left_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    middle_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    right_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # optional overlays, either layout
    disclaimer_text: Mapped[str | None] = mapped_column(String, nullable=True)
    story_title: Mapped[str | None] = mapped_column(String, nullable=True)
    story_author: Mapped[str | None] = mapped_column(String, nullable=True)
    story_character: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    progress_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    narration_path: Mapped[str | None] = mapped_column(String, nullable=True)
    captions_ass_path: Mapped[str | None] = mapped_column(String, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
