"""TikTok engine -- deliberately an "unavailable" stub in Phase 1.

There is no compliant way for a distributed desktop product to search
arbitrary public TikTok videos by keyword:

  - the Research API is limited to approved US/EU academic & non-profit
    institutions and is not licensable for a commercial app;
  - the Display API only returns videos of the *currently authenticated
    user's own account* (this app already uses it that way in
    app.modules.competitor_intelligence);
  - scraping the web / mobile endpoints would mean defeating anti-bot
    measures, which the brief explicitly forbids (sections 5 & 33).

So this engine honestly reports itself unavailable. The interface is real
so that if TikTok ever ships a keyword-search product API, only this file
changes. `search()` returns an `unavailable` outcome -- never an error,
never a crash (brief section 7).
"""

from __future__ import annotations

from app.modules.discovery.contracts import PLATFORM_TIKTOK, EngineOutcome
from app.modules.discovery.engines.base import BaseEngine, SearchOptions

_REASON = (
    "TikTok has no public keyword-search API a desktop app may use. "
    "Open TikTok directly to browse this topic."
)


class TikTokEngine(BaseEngine):
    platform = PLATFORM_TIKTOK

    def is_configured(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return _REASON

    def search(self, query: str, options: SearchOptions) -> EngineOutcome:
        return EngineOutcome.unavailable(self.platform, _REASON)
