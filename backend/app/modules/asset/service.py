"""Business logic for the local Asset library: register/search/lookup/
delete. Synchronous, no background worker -- every operation here is a fast
local DB read/write and a `Path.exists()` check, the same shape as
app/modules/ai/story's synchronous service. Deliberately does not shell out
to ffprobe to auto-detect width/height/duration -- see
docs/features/20-asset-module.md for why -- so this module has no external
process dependency at all, only SQLAlchemy + the standard library.
"""

from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn


def _normalize_path(raw_path: str) -> Path:
    """Resolve to an absolute path so the same physical file registered as
    "./clip.mp4" and "C:/repo/clip.mp4" is recognized as one asset, not two.
    """
    return Path(raw_path).expanduser().resolve()


def _normalize_tags(tags: list[str]) -> list[str]:
    """Trim whitespace, drop blanks, and de-dupe case-insensitively while
    keeping the first-seen casing -- so "Woman" and "woman" collapse to one
    tag instead of silently double-counting in search scoring.
    """
    seen: dict[str, str] = {}
    for tag in tags:
        cleaned = tag.strip()
        if not cleaned:
            continue
        seen.setdefault(cleaned.lower(), cleaned)
    return list(seen.values())


def _score_asset(asset: Asset, terms: list[str]) -> int:
    """Deterministic keyword scoring -- no embeddings/vector search. An
    exact tag match counts more than a partial tag match, which counts more
    than a filename/source substring hit, so a search for ["woman"] ranks an
    asset tagged exactly "woman" above one merely named "woman_portrait.jpg".
    """
    tags_lower = [tag.lower() for tag in asset.tags]
    filename_lower = asset.filename.lower()
    source_lower = (asset.source or "").lower()

    score = 0
    for term in terms:
        if term in tags_lower:
            score += 3
        elif any(term in tag for tag in tags_lower):
            score += 2
        if term in filename_lower:
            score += 1
        if term in source_lower:
            score += 1
    return score


class AssetService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, payload: AssetRegisterIn) -> Asset:
        resolved_path = _normalize_path(payload.path)
        if not resolved_path.exists():
            raise ValidationError(f"File not found: {resolved_path}")
        if not resolved_path.is_file():
            raise ValidationError(f"Not a file: {resolved_path}")

        asset = Asset(
            filename=payload.filename,
            path=str(resolved_path),
            type=payload.type,
            width=payload.width,
            height=payload.height,
            duration_sec=payload.duration_sec,
            filesize_bytes=resolved_path.stat().st_size,
            tags=_normalize_tags(payload.tags),
            source=payload.source,
            source_ref=payload.source_ref,
            extra_metadata=payload.extra_metadata,
        )
        self.db.add(asset)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationError(f"An asset is already registered for path: {resolved_path}") from exc
        self.db.refresh(asset)
        return asset

    def get(self, asset_id: int) -> Asset:
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            raise NotFoundError("Asset", asset_id)
        return asset

    def delete(self, asset_id: int) -> None:
        asset = self.get(asset_id)
        self.db.delete(asset)
        self.db.commit()

    def search(self, query: list[str] | None = None, asset_type: str | None = None) -> list[Asset]:
        db_query = self.db.query(Asset)
        if asset_type is not None:
            db_query = db_query.filter(Asset.type == asset_type)
        assets = db_query.all()

        terms = [term.strip().lower() for term in (query or []) if term and term.strip()]
        if not terms:
            return sorted(assets, key=lambda asset: asset.created_at, reverse=True)

        matched = [(asset, _score_asset(asset, terms)) for asset in assets]
        matched = [(asset, score) for asset, score in matched if score > 0]
        matched.sort(key=lambda pair: (-pair[1], -pair[0].created_at.timestamp(), pair[0].id))
        return [asset for asset, _ in matched]
