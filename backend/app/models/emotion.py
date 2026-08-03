from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Emotion(Base):
    """Fixed lookup of the emotional tone a video's content conveys (Vui,
    Cảm động, Hài hước, ...). Same read-only-lookup shape as Category
    (seeded once, listed via GET, never created/edited through the API).
    """

    __tablename__ = "emotion"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
