"""AI Image Generation (Task 59 -- "Generate Full by AI"): the composition-
root adapter between app.modules.ai.image_client (pure OpenAI Images API
wrapper) and app.modules.beat/app.modules.asset. Same "app/api/v1/
endpoints/* may import multiple modules; the modules themselves may never
import each other" shape voice_generate.py/motion_generate.py already
established.

The key integration decision (same one voice_generate.py already made for
narration): a generated image is registered as a real, ordinary local
Asset (type="image", source="ai_image_generator") and assigned to
Beat.asset_id -- every downstream stage (Motion, Quality Gate, Render)
already treats any real Asset identically regardless of Asset.source (none
of them special-case it), so this needs ZERO changes anywhere else in the
pipeline. This module's own job stops at "produce a real PNG per beat and
make it available to the existing render pipeline" -- it never touches
FFmpeg/motion/render itself.

Only ever generates for beats that don't already have an asset_id (Task
18's own ASSIGNING_ASSETS precedent: "manual/existing assignment always
wins, this stage only ever adds") -- which is also what makes a retry
free: an already-imaged beat is never re-generated, never re-billed.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.db.session import SessionLocal
from app.modules.ai.image_client import IMAGE_COST_USD, IMAGE_HEIGHT, IMAGE_WIDTH, ImageGenError, generate_beat_image
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, ContentProjectConfig

logger = logging.getLogger(__name__)

# The technical constraints stay fixed and generic on purpose -- the user's
# own stated priority is visual consistency across a whole video over any
# single image looking spectacular, so every BEAT within one project still
# shares the same anchor. But the anchor itself must vary per PROJECT
# (real bug report: selecting a different Template had zero effect on
# "Generate Full by AI" output -- every project's images looked identical
# regardless of Template, because this constant never read the project's
# own template-derived tone/style at all). See _image_prompt below --
# content_config.tone/.style (ContentProjectConfig, set per Template --
# e.g. Emotional Story's "warm and emotional"/"storytelling" vs. Couple
# Story's "tender and reflective"/"relationship story") now folds into the
# suffix instead of being ignored.
_STYLE_SUFFIX_TEMPLATE = (
    "Simple, consistent illustration style matching the rest of this video's visuals, "
    "evoking a {tone} tone in a {style} style, "
    "vertical 9:16 composition, no text or watermarks in the image."
)


def _visuals_dir(project_id: int, settings: Settings) -> Path:
    return Path(settings.library_dir) / "_imagegen" / f"project_{project_id}"


def _beat_image_path(project_id: int, beat_id: str, settings: Settings) -> Path:
    return _visuals_dir(project_id, settings) / f"beat_{beat_id}.png"


def _image_prompt(beat: Beat, content_config: ContentProjectConfig) -> str:
    base = (beat.visual_hint or beat.narration or "").strip()
    if not base:
        base = "An establishing shot fitting the surrounding story."
    style_suffix = _STYLE_SUFFIX_TEMPLATE.format(tone=content_config.tone, style=content_config.style)
    return f"{base}. {style_suffix}"


def _get_or_register_image_asset(db, path: Path) -> int:
    """Section 30 (voice_generate.py's own precedent): a beat's image lives
    at a deterministic path -- reuses the existing Asset row for that path
    if one is already registered (a second raw register() call on the same
    path would otherwise hit its own unique-path IntegrityError), so a
    retry that regenerates the same beat's file never orphans Asset rows.
    """
    # See voice_generate.py's own _get_or_register_audio_asset for why this
    # must be resolved to an absolute path before comparing -- register()
    # always normalizes, so comparing against a possibly-relative `path`
    # (settings.library_dir defaults to relative in dev) never matches an
    # already-registered row.
    resolved = str(path.expanduser().resolve())
    existing = db.query(Asset).filter(Asset.path == resolved).first()
    if existing is not None:
        return existing.id
    asset = AssetService(db).register(
        AssetRegisterIn(
            filename=path.name, path=resolved, type="image",
            width=IMAGE_WIDTH, height=IMAGE_HEIGHT, source="ai_image_generator",
        )
    )
    return asset.id


@dataclass
class ImageGenerationResult:
    generated: bool  # True only when at least one real API call happened (metrics convention)
    image_count: int
    cost_usd: float


def generate_project_images(project_id: int, settings: Settings) -> ImageGenerationResult:
    """Idempotent, same reuse-before-regenerate shape every other Factory
    stage already uses: only beats with asset_id is None are ever touched.
    A per-beat generation failure (content-policy rejection, transient API
    error) is a soft skip -- the beat is simply left unassigned, exactly
    like today's "no local match found" case -- never failing the whole
    stage over one beat (this codebase's established soft-failure
    precedent: BGM-missing, Motion-cache-miss, Thumbnail-fallback-frame).
    """
    draft = get_project_draft(project_id)
    pending = [b for b in draft.beats if b.asset_id is None]
    if not pending:
        return ImageGenerationResult(generated=False, image_count=0, cost_usd=0.0)

    if not settings.openai_api_key:
        raise ImageGenError("No OpenAI API key configured -- add one in Settings to use AI image generation.")

    updated_by_id: dict[str, Beat] = {}
    db = SessionLocal()
    try:
        for beat in pending:
            output_path = _beat_image_path(project_id, beat.id, settings)
            try:
                generate_beat_image(settings.openai_api_key, _image_prompt(beat, draft.config.content), output_path)
            except ImageGenError:
                logger.warning(
                    "AI image generation failed for project %s beat %s -- left unassigned.", project_id, beat.id
                )
                continue
            asset_id = _get_or_register_image_asset(db, output_path)
            updated_by_id[beat.id] = beat.model_copy(update={"asset_id": asset_id})
    finally:
        db.close()

    if not updated_by_id:
        return ImageGenerationResult(generated=False, image_count=0, cost_usd=0.0)

    updated_beats = [updated_by_id.get(b.id, b) for b in draft.beats]
    plan = BeatPlan(
        script_text=draft.script_text, beats=updated_beats, project_name=draft.project_name, config=draft.config,
        idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
    )
    update_project_beat_plan(project_id, plan)

    count = len(updated_by_id)
    return ImageGenerationResult(generated=True, image_count=count, cost_usd=round(count * IMAGE_COST_USD, 4))
