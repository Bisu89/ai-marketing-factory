"""Database-backed persistence for Series -- see models.py's module docstring
for why this module never imports app.modules.beat. Mirrors
app.modules.batch.service's own "SessionLocal per call" shape.
"""

from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.series.models import Series


def create_series(name: str, character_description: str) -> Series:
    db = SessionLocal()
    try:
        series = Series(name=name.strip(), character_description=character_description.strip())
        db.add(series)
        db.commit()
        db.refresh(series)
        db.expunge(series)
        return series
    finally:
        db.close()


def get_series(series_id: int) -> Series:
    db = SessionLocal()
    try:
        series = db.get(Series, series_id)
        if series is None:
            raise NotFoundError("Series", series_id)
        db.expunge(series)
        return series
    finally:
        db.close()


def list_series() -> list[Series]:
    db = SessionLocal()
    try:
        series = db.query(Series).order_by(Series.id.desc()).all()
        db.expunge_all()
        return series
    finally:
        db.close()


def update_series(series_id: int, name: str, character_description: str) -> Series:
    db = SessionLocal()
    try:
        series = db.get(Series, series_id)
        if series is None:
            raise NotFoundError("Series", series_id)
        series.name = name.strip()
        series.character_description = character_description.strip()
        db.commit()
        db.refresh(series)
        db.expunge(series)
        return series
    finally:
        db.close()


# -- AI Storytelling Studio, Phase 1 (feature 131) -- the additive
# channel_id / *_json columns. Kept separate from update_series above so a
# studio patch can never touch name / character_description.
_STUDIO_FIELDS = (
    "channel_id", "narrative_identity", "visual_identity_json",
    "voice_override_json", "metadata_conventions_json",
)


def update_series_studio(series_id: int, **fields) -> Series:
    db = SessionLocal()
    try:
        series = db.get(Series, series_id)
        if series is None:
            raise NotFoundError("Series", series_id)
        for key in _STUDIO_FIELDS:
            if key in fields:
                setattr(series, key, fields[key])
        db.commit()
        db.refresh(series)
        db.expunge(series)
        return series
    finally:
        db.close()
