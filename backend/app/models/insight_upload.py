from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InsightUpload(Base):
    """One row per CSV file uploaded on the Insights page -- each upload is a
    snapshot of a Meta Business Suite content-performance export at the time
    it was pulled. Rows inside it are cumulative/lifetime totals per post as
    of that moment, so comparing totals across uploads is how growth trends
    are read (see InsightPostSnapshot).
    """

    __tablename__ = "insight_upload"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
