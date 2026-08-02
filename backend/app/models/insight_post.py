from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.insight_upload import InsightUpload


class InsightPostSnapshot(Base):
    """One row per post per upload -- a 1:1 mapping of the Meta Business Suite
    "Content" CSV export's columns. `distribution` and `period_label` are kept
    as free text rather than numbers/dates: the export can put values like
    "-2.7x" in the distribution column and "Trọn Đời" (Lifetime) in the date
    column, neither of which parse as a plain number/date.
    """

    __tablename__ = "insight_post_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("insight_upload.id"), nullable=False)

    post_id: Mapped[str] = mapped_column(String, nullable=False)
    page_id: Mapped[str] = mapped_column(String, nullable=False)
    page_name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String, nullable=True)
    post_type: Mapped[str | None] = mapped_column(String, nullable=True)
    data_comment: Mapped[str | None] = mapped_column(String, nullable=True)
    period_label: Mapped[str | None] = mapped_column(String, nullable=True)

    avg_seconds_viewed: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distribution: Mapped[str | None] = mapped_column(String, nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    real_followers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_seconds_viewed: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    viewers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    upload: Mapped[InsightUpload] = relationship("InsightUpload", lazy="joined")
