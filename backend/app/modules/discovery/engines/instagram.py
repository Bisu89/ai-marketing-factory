"""Instagram engine -- deliberately an "unavailable" stub in Phase 1.

The Instagram Graph API only covers content the authenticated user owns or
manages (their own Business/Creator account), plus a heavily rate-limited
hashtag-search that returns no view counts and cannot do free-text keyword
search. There is no compliant public keyword-search API for a distributed
desktop app, and scraping means defeating login/anti-bot controls, which
the brief forbids (sections 6 & 33).

Interface is real; only this file changes if a suitable API appears.
"""

from __future__ import annotations

from app.modules.discovery.contracts import PLATFORM_INSTAGRAM, EngineOutcome
from app.modules.discovery.engines.base import BaseEngine, SearchOptions

_REASON = (
    "Instagram has no public keyword-search API a desktop app may use. "
    "Open Instagram directly to browse this topic."
)


class InstagramEngine(BaseEngine):
    platform = PLATFORM_INSTAGRAM

    def is_configured(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return _REASON

    def search(self, query: str, options: SearchOptions) -> EngineOutcome:
        return EngineOutcome.unavailable(self.platform, _REASON)
