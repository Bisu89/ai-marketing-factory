from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.emotion import Emotion
from app.models.platform import Platform

PLATFORMS = ["youtube", "tiktok", "facebook", "instagram"]
CATEGORIES = ["Couple", "Family", "Military", "Proposal", "Transformation", "Comedy", "Other"]
EMOTIONS = ["Vui", "Cảm động", "Hài hước", "Buồn", "Kịch tính", "Trung tính"]


def seed_initial_data(db: Session) -> None:
    """Idempotent: safe to call on every startup."""
    existing_platforms = {p.name for p in db.query(Platform).all()}
    for name in PLATFORMS:
        if name not in existing_platforms:
            db.add(Platform(name=name))

    existing_categories = {c.name for c in db.query(Category).all()}
    for name in CATEGORIES:
        if name not in existing_categories:
            db.add(Category(name=name))

    existing_emotions = {e.name for e in db.query(Emotion).all()}
    for name in EMOTIONS:
        if name not in existing_emotions:
            db.add(Emotion(name=name))

    db.commit()
