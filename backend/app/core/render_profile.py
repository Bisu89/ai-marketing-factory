"""Named render profiles for the Video Factory pipeline: a single source of
truth for output resolution/fps/codecs instead of these values being
hardcoded independently in the frontend (per scene) and wherever the
backend validates a finished render. See
docs/features/37-e2e-pipeline-hardening.md.

Lives in app/core/ (not app/modules/*) for the same reason
app.core.render_policy does: it's an application-wide rendering constraint
every render path should agree on, not one module's business logic.

Only the *values* are centralized here. The frontend still sends an
OutputFormat per Scene (app.modules.composition.schemas.OutputFormat) --
that per-scene shape is Composition's own, deliberately-flexible contract
(see that module's docstring) and isn't being redesigned by this task. What
changes is that `render_composition()` now stamps every scene's
output_format from the requested profile before rendering, so a caller only
has to name a profile once instead of repeating width/height/fps on every
scene by hand.
"""

from pydantic import BaseModel

from app.core.exceptions import ValidationError


class RenderProfile(BaseModel):
    name: str
    width: int
    height: int
    fps: float
    video_codec: str = "h264"
    audio_codec: str = "aac"
    pixel_format: str = "yuv420p"


SOCIAL_VERTICAL = RenderProfile(name="SOCIAL_VERTICAL", width=1080, height=1920, fps=30.0)
PREVIEW = RenderProfile(name="PREVIEW", width=720, height=1280, fps=24.0)

RENDER_PROFILES: dict[str, RenderProfile] = {
    profile.name: profile for profile in (SOCIAL_VERTICAL, PREVIEW)
}

DEFAULT_RENDER_PROFILE_NAME = SOCIAL_VERTICAL.name


def get_render_profile(name: str) -> RenderProfile:
    profile = RENDER_PROFILES.get(name)
    if profile is None:
        raise ValidationError(
            f"Unknown render profile {name!r}. Available profiles: {sorted(RENDER_PROFILES)}"
        )
    return profile
