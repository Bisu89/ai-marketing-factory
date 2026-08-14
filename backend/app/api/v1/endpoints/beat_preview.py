"""Single-Beat motion preview: an Asset (image) + a Beat.motion_preset +
duration -> one MP4 clip via the existing local motion renderer
(app.modules.motion.renderer.render_motion_clip -- see
docs/features/23-local-motion-renderer.md). This is NOT final multi-beat
composition -- that is a later task; this only ever produces one clip for
one beat, synchronously, for the Visual step's "Preview motion" button.

Per app/modules/README.md, no module may import another module. This
adapter necessarily touches three: app.modules.asset (resolve asset_id ->
an image path), app.modules.beat (BeatMotionPreset, for request
validation), and app.modules.motion (build_motion_plan + render_motion_clip).
Per this codebase's established "composition root" convention (see
composition_render.py, beat_generate.py), that crossing lives here at the
HTTP layer, not inside any one module.

There is no server-side Beat store to look up a "beat_id" from -- a
BeatPlan lives entirely in beats.json + frontend state (see
docs/features/31-beat-editor-crud-persistence.md), never a DB row. So,
mirroring composition_render.py's own CompositionRenderRequest (the caller
sends the plan's data, not an id for the backend to look up), this
endpoint's request body carries exactly the data a preview needs
(asset_id, motion_preset, duration) rather than a beat_id path param.
"""

import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.asset.service import AssetService
from app.modules.beat.schemas import BeatMotionPreset
from app.modules.motion.renderer import DEFAULT_FPS, DEFAULT_HEIGHT, DEFAULT_WIDTH, render_motion_clip
from app.modules.motion.service import build_motion_plan

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_media_url(file_path: Path, library_dir: Path) -> str:
    # Mirrors app/modules/video_composer/schemas.py's _to_media_url exactly
    # -- the existing /media StaticFiles mount (app/main.py) already serves
    # anything under library_dir, so a preview written there needs no new
    # file-serving endpoint (unlike Asset.path, which can point outside
    # library_dir -- see docs/features/32-asset-library-beat-visual-assignment.md's
    # GET /assets/{id}/file).
    rel = file_path.resolve().relative_to(library_dir.resolve())
    return "/media/" + rel.as_posix()


def get_asset_service(db: Session = Depends(get_db)) -> AssetService:
    return AssetService(db)


class BeatPreviewRequest(BaseModel):
    asset_id: int
    motion_preset: BeatMotionPreset = BeatMotionPreset.STATIC
    duration: float = 4.0

    @field_validator("duration")
    @classmethod
    def _duration_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("duration must be > 0")
        return value


class BeatPreviewResult(BaseModel):
    preview_media_url: str
    duration: float
    width: int
    height: int
    fps: float
    render_time_seconds: float


@router.post("/beats/preview", response_model=BeatPreviewResult, status_code=201)
def render_beat_preview(
    payload: BeatPreviewRequest,
    service: AssetService = Depends(get_asset_service),
    settings: Settings = Depends(get_settings),
) -> BeatPreviewResult:
    asset = service.get_image(payload.asset_id)
    # BeatMotionPreset's 6 uppercase values are a strict subset of
    # MotionPresetName's 9 lowercase values, same spelling -- see
    # app/modules/beat/schemas.py's module docstring.
    motion_plan = build_motion_plan(payload.motion_preset.value.lower(), duration=payload.duration)

    library_dir = Path(settings.library_dir)
    output_path = library_dir / "_beat" / "previews" / f"preview_{uuid4().hex}.mp4"

    start = time.monotonic()
    render_motion_clip(
        asset.path,
        motion_plan,
        output_path,
        duration=payload.duration,
        fps=DEFAULT_FPS,
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
    )
    render_seconds = time.monotonic() - start
    logger.info("Rendered beat preview for asset %s in %.2fs", asset.id, render_seconds)

    return BeatPreviewResult(
        preview_media_url=_to_media_url(output_path, library_dir),
        duration=payload.duration,
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        fps=DEFAULT_FPS,
        render_time_seconds=round(render_seconds, 2),
    )
