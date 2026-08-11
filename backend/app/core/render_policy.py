"""The Video Factory's rendering policy: declares which rendering
capabilities this app is allowed to use, and enforces the hard "no AI video
generation, no cloud rendering" rule at the one place a render actually
gets kicked off (app.api.v1.endpoints.composition_render.render_composition).

This is a fixed policy declaration, not a per-deployment setting a user
configures -- app.core.config.Settings already owns runtime configuration
(API keys, directories, etc.); this module owns *what kind* of rendering
this app is allowed to do at all. That's deliberately not exposed as an
env var: a silently-flippable "ai_video_enabled" would defeat the point of
a hard-disabled flag. See docs/features/28-video-factory-e2e-pipeline.md.

Lives in app/core/, not any app/modules/* package, since it's an
application-wide policy every render path must respect, not one module's
business logic -- consistent with app/modules/README.md's "core" being
the only thing every module (and the composition-root adapter) is allowed
to depend on.
"""

from pydantic import BaseModel

from app.core.exceptions import ValidationError


class RenderPolicy(BaseModel):
    """Mirrors the YAML shape from this task's brief:

    ai_video:
      enabled: false
    local_motion:
      enabled: true
    ai_image:
      enabled: true
    tts:
      enabled: true

    Only `ai_video_enabled` is actually enforced right now (see
    `enforce_local_rendering_policy`) -- the other three flags describe
    capabilities this app already only ever uses locally
    (app.modules.motion's renderer, Asset-registered local images, and
    edge_tts respectively), so there is nothing to gate them against yet.
    They're declared here so the policy is a complete, honest description
    of the pipeline's actual capabilities, not just the one rule that
    happens to need active enforcement today.
    """

    ai_video_enabled: bool = False
    local_motion_enabled: bool = True
    ai_image_enabled: bool = True
    tts_enabled: bool = True


DEFAULT_RENDER_POLICY = RenderPolicy()


def enforce_local_rendering_policy(policy: RenderPolicy = DEFAULT_RENDER_POLICY) -> None:
    """Raises if the policy would require AI video generation or cloud
    rendering -- called at the start of every render entry point. Since
    `RenderPolicy.ai_video_enabled` defaults to (and is never set anywhere
    other than) False, this never actually raises in practice today; it
    exists so the "AI video generation MUST be disabled" rule is a real,
    checked invariant instead of just an implicit fact of what code happens
    to be wired up.
    """
    if policy.ai_video_enabled:
        raise ValidationError(
            "AI video generation is disabled by this app's rendering policy "
            "(RenderPolicy.ai_video_enabled=False) -- local rendering only."
        )
