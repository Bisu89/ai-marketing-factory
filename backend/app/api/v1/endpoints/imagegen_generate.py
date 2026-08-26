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
from app.core.render_profile import RenderProfile, get_render_profile
from app.db.session import SessionLocal
from app.modules.ai.image_client import (
    IMAGE_COST_USD,
    IMAGE_SIZE_DIMENSIONS,
    IMAGE_SIZE_LANDSCAPE,
    IMAGE_SIZE_PORTRAIT,
    IMAGE_SIZE_SQUARE,
    ImageGenError,
    generate_beat_image,
)
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, ContentProjectConfig, VisualGenerationProjectConfig

logger = logging.getLogger(__name__)


def _image_size_for_profile(profile: RenderProfile) -> str:
    """Real user request: a landscape (16:9) render profile alongside this
    app's original portrait one. Derives which of GPT image models' 3
    supported sizes to request from the profile's own width/height --
    never branches on the profile *name* -- so any future profile (a
    square one, say) is handled correctly without this function changing.
    """
    if profile.width > profile.height:
        return IMAGE_SIZE_LANDSCAPE
    if profile.width < profile.height:
        return IMAGE_SIZE_PORTRAIT
    return IMAGE_SIZE_SQUARE


def _orientation_phrase(image_size: str) -> str:
    if image_size == IMAGE_SIZE_LANDSCAPE:
        return "horizontal 16:9 composition"
    if image_size == IMAGE_SIZE_SQUARE:
        return "square 1:1 composition"
    return "vertical 9:16 composition"

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
    "{orientation}, no text or watermarks in the image."
)


def _visuals_dir(project_id: int, settings: Settings) -> Path:
    return Path(settings.library_dir) / "_imagegen" / f"project_{project_id}"


def _beat_image_path(project_id: int, beat_id: str, settings: Settings) -> Path:
    return _visuals_dir(project_id, settings) / f"beat_{beat_id}.png"


def _image_prompt(
    beat: Beat, content_config: ContentProjectConfig, visual_config: VisualGenerationProjectConfig, image_size: str,
) -> str:
    # Story-to-Scene Analysis (docs/features/103-story-to-scene-analysis.md):
    # visual_description is a real, showable scene description ("what should
    # appear on screen") produced by beat_generate.py's richer prompt --
    # preferred over visual_hint's older 3-10 word label whenever a beat has
    # it. Falls back to visual_hint/narration unchanged for any beat
    # generated before this feature, or authored/edited by hand.
    base = (beat.visual_description or beat.visual_hint or beat.narration or "").strip()
    if not base:
        base = "An establishing shot fitting the surrounding story."
    cinematography = ", ".join(
        part for part in (
            f"location: {beat.location}" if beat.location else None,
            f"time of day: {beat.time_of_day}" if beat.time_of_day else None,
            f"camera: {beat.camera}" if beat.camera else None,
            f"lighting: {beat.lighting}" if beat.lighting else None,
        ) if part
    )
    style_suffix = _STYLE_SUFFIX_TEMPLATE.format(
        tone=content_config.tone, style=content_config.style, orientation=_orientation_phrase(image_size),
    )
    # Template/project-level free-text style guidance (e.g. "watercolor
    # illustration, pastel colors") -- appended rather than replacing the
    # suffix above so the vertical/no-text/consistency instructions always
    # still apply even when a user sets this.
    custom_style = visual_config.image_style_prompt.strip()
    if custom_style:
        style_suffix = f"{style_suffix} {custom_style}"
    prompt = base if base.endswith((".", "!", "?")) else f"{base}."
    if cinematography:
        prompt += f" ({cinematography})."
    return f"{prompt} {style_suffix}"


def _get_or_register_image_asset(db, path: Path, image_size: str) -> int:
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
    width, height = IMAGE_SIZE_DIMENSIONS[image_size]
    asset = AssetService(db).register(
        AssetRegisterIn(
            filename=path.name, path=resolved, type="image",
            width=width, height=height, source="ai_image_generator",
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

    # Real user request: a landscape (16:9) render profile alongside this
    # app's original portrait one. Resolved once per run, not per beat --
    # a project's render profile never changes mid-run.
    image_size = _image_size_for_profile(get_render_profile(draft.config.render.profile))

    updated_by_id: dict[str, Beat] = {}
    db = SessionLocal()
    try:
        for beat in pending:
            output_path = _beat_image_path(project_id, beat.id, settings)
            try:
                prompt = _image_prompt(beat, draft.config.content, draft.config.visual_generation, image_size)
                generate_beat_image(settings.openai_api_key, prompt, output_path, size=image_size)
            except ImageGenError:
                logger.warning(
                    "AI image generation failed for project %s beat %s -- left unassigned.", project_id, beat.id
                )
                continue
            asset_id = _get_or_register_image_asset(db, output_path, image_size)
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
