"""VideoProvider abstraction (Phase 0 skeleton -- see the AI Storytelling
Studio plan, sections 8 and 21). Sibling of image_client.py: wrap one
video-generation SDK behind a small, stable surface.

NO real provider is wired yet. The default get_video_provider() returns a
NullVideoProvider whose is_available() is False and whose generate()
raises. The future AI_VIDEO Factory stage (plan Phase 10) is expected to
check is_available() first and degrade any AI_VIDEO scene to
STILL_WITH_MOTION when it is False -- exactly the soft-failure precedent
this codebase already uses for a missing BGM asset, a motion cache miss,
and a flat thumbnail candidate.

Independent of app.modules.ai.llm_client's own text-provider toggle:
video generation is always its own provider choice (Anthropic has no
video API), the same way image_client is always OpenAI regardless of
settings.ai_provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

# Change here only -- nowhere else references a video-provider env var.
# Filled in Phase 10 once a provider is chosen (Kling / Runway / Luma / ...).
VIDEO_PROVIDER_SETTING = "video_provider"


class VideoGenError(Exception):
    """Any failure generating one scene's video clip, including 'no
    provider configured'.
    """


@dataclass
class VideoGenResult:
    path: Path
    cost_usd: float
    provider: str
    model: str
    duration_sec: float


@runtime_checkable
class VideoProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        """True only when a real API key / endpoint is configured. The
        Factory stage checks this before attempting any AI_VIDEO scene.
        """
        ...

    def generate(
        self,
        *,
        prompt: str,
        duration_sec: float,
        output_path: Path,
        reference_image_path: Path | None = None,
        motion_hint: str | None = None,
    ) -> VideoGenResult:
        """Generate one clip and write it atomically to output_path (same
        tmp-then-replace convention image_client.generate_beat_image uses).
        """
        ...


class NullVideoProvider:
    """The default. AI video is opt-in and off until Phase 10."""

    name = "null"

    def is_available(self) -> bool:
        return False

    def generate(
        self,
        *,
        prompt: str,
        duration_sec: float,
        output_path: Path,
        reference_image_path: Path | None = None,
        motion_hint: str | None = None,
    ) -> VideoGenResult:
        raise VideoGenError(
            "No AI video provider is configured. AI_VIDEO scenes fall back to "
            "STILL_WITH_MOTION (deterministic Ken-Burns motion)."
        )


def get_video_provider(settings: object | None = None) -> VideoProvider:
    """Resolve the configured video provider. Phase 0: always
    NullVideoProvider. Phase 10 branches on getattr(settings,
    VIDEO_PROVIDER_SETTING, None) here -- one place, like
    llm_client.resolve_ai_credentials.
    """
    return NullVideoProvider()
