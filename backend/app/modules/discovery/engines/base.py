"""The common engine interface (brief section 2).

`getDetails` / `getCreator` / `getLicenseInfo` / `getDownloadCapability`
from the brief are folded into what `search()` already returns for V1 --
every field the brief lists as coming from those calls is populated on the
`VideoResult` at search time (metadata-first, brief section 27). They stay
as overridable methods so a Phase 3 permission/download flow can enrich a
single selected result without re-searching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.modules.discovery.contracts import EngineOutcome, VideoResult


@dataclass
class SearchOptions:
    limit_per_query: int = 15
    # Expanded queries to actually issue for this engine. The orchestrator
    # trims this per-engine (YouTube quota is far tighter than Reddit's).
    queries: list[str] | None = None
    # Only fetch content newer than this many days when the platform's
    # search API supports a time filter (Reddit does, YouTube via
    # publishedAfter). None = no filter.
    max_age_days: int | None = None


@runtime_checkable
class Engine(Protocol):
    platform: str

    def is_configured(self) -> bool:
        """False when the engine needs credentials/keys the user hasn't
        provided. The orchestrator turns this into an 'unavailable' outcome
        with a helpful reason rather than an error."""
        ...

    def unavailable_reason(self) -> str:
        ...

    def search(self, query: str, options: SearchOptions) -> EngineOutcome:
        ...


class BaseEngine:
    """Small shared helper base -- concrete engines subclass this."""

    platform: str = ""

    def is_configured(self) -> bool:  # pragma: no cover - overridden
        return True

    def unavailable_reason(self) -> str:  # pragma: no cover - overridden
        return f"{self.platform} search is not available"

    def search(self, query: str, options: SearchOptions) -> EngineOutcome:  # pragma: no cover
        raise NotImplementedError

    # -- optional per-result enrichment hooks (Phase 3) ---------------
    def get_details(self, result: VideoResult) -> VideoResult:
        return result

    def get_download_capability(self, result: VideoResult) -> str:
        from app.modules.discovery.contracts import (
            DOWNLOAD_PERMISSION_REQUIRED,
            DOWNLOAD_UNSUPPORTED,
        )

        return DOWNLOAD_UNSUPPORTED if not self.is_configured() else DOWNLOAD_PERMISSION_REQUIRED
