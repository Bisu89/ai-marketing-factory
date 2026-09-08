"""Per-platform search adapters. Each implements `search(query, options)`
and hides every platform-specific detail from the rest of the app.

Phase 1: reddit + youtube are real; tiktok + instagram are honest
"unavailable" stubs (no compliant public keyword-search API exists for a
distributed desktop product -- see tiktok.py's module docstring).
"""

from app.modules.discovery.engines.base import Engine, SearchOptions
from app.modules.discovery.engines.instagram import InstagramEngine
from app.modules.discovery.engines.reddit import RedditEngine
from app.modules.discovery.engines.tiktok import TikTokEngine
from app.modules.discovery.engines.youtube import YouTubeEngine

__all__ = [
    "Engine",
    "InstagramEngine",
    "RedditEngine",
    "SearchOptions",
    "TikTokEngine",
    "YouTubeEngine",
    "build_engines",
]


def build_engines() -> list[Engine]:
    """All engines, in display order. The orchestrator asks each one
    `is_configured()` and records an "unavailable" outcome for the rest."""
    return [RedditEngine(), YouTubeEngine(), TikTokEngine(), InstagramEngine()]
