"""The platform-independent shapes every engine normalizes into, plus the
rights / download vocabularies.

`VideoResult` is a plain dataclass, not a Pydantic model -- it is an
internal pipeline value (engine -> normalize -> dedup -> score -> persist),
never a request/response body. `schemas.py` has the Pydantic I/O shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# -- Rights -------------------------------------------------------------
#
# The full vocabulary from the brief (section 21). Phase 1 only ever
# *assigns* UNKNOWN, STANDARD_PLATFORM_LICENSE and CREATIVE_COMMONS -- the
# permission-driven states (GRANTED / EXPIRED / ...) are here so the enum
# is stable when the Permission module lands in Phase 3.
RIGHTS_UNKNOWN = "UNKNOWN"
RIGHTS_STANDARD_PLATFORM_LICENSE = "STANDARD_PLATFORM_LICENSE"
RIGHTS_CREATIVE_COMMONS = "CREATIVE_COMMONS"
RIGHTS_PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
RIGHTS_USER_OWNED = "USER_OWNED"
RIGHTS_LICENSED = "LICENSED"
RIGHTS_PERMISSION_GRANTED = "PERMISSION_GRANTED"
RIGHTS_PERMISSION_EXPIRED = "PERMISSION_EXPIRED"
RIGHTS_NOT_ALLOWED = "NOT_ALLOWED"

RIGHTS_STATUSES = (
    RIGHTS_UNKNOWN,
    RIGHTS_STANDARD_PLATFORM_LICENSE,
    RIGHTS_CREATIVE_COMMONS,
    RIGHTS_PUBLIC_DOMAIN,
    RIGHTS_USER_OWNED,
    RIGHTS_LICENSED,
    RIGHTS_PERMISSION_GRANTED,
    RIGHTS_PERMISSION_EXPIRED,
    RIGHTS_NOT_ALLOWED,
)

# The only rights states that permit a download in Phase 1. Everything else
# gets [OPEN SOURCE] / [SAVE] instead of [DOWNLOAD] (brief section 22).
DOWNLOADABLE_RIGHTS = frozenset(
    {
        RIGHTS_CREATIVE_COMMONS,
        RIGHTS_PUBLIC_DOMAIN,
        RIGHTS_USER_OWNED,
        RIGHTS_LICENSED,
        RIGHTS_PERMISSION_GRANTED,
    }
)

# -- Download capability (what the card should show) ------------------
DOWNLOAD_ALLOWED = "ALLOWED"  # rights permit it AND an engine can fetch it
DOWNLOAD_PERMISSION_REQUIRED = "PERMISSION_REQUIRED"  # rights unclear/blocked
DOWNLOAD_UNSUPPORTED = "UNSUPPORTED"  # no legitimate fetch path exists

# -- Platforms --------------------------------------------------------
PLATFORM_REDDIT = "reddit"
PLATFORM_YOUTUBE = "youtube"
PLATFORM_TIKTOK = "tiktok"
PLATFORM_INSTAGRAM = "instagram"
ALL_PLATFORMS = (PLATFORM_REDDIT, PLATFORM_YOUTUBE, PLATFORM_TIKTOK, PLATFORM_INSTAGRAM)


@dataclass
class VideoResult:
    """One normalized candidate. Missing metrics are `None`, never 0 or an
    invented value -- the scorers treat "unknown" and "zero" differently
    (brief sections 10 & 15).
    """

    platform: str
    source_url: str
    title: str

    id: str = ""  # engine-local id; the DB row gets its own autoincrement pk
    description: str | None = None
    thumbnail_url: str | None = None

    creator_name: str | None = None
    creator_url: str | None = None

    published_at: datetime | None = None
    duration_sec: int | None = None

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None

    width: int | None = None
    height: int | None = None

    content_tags: list[str] = field(default_factory=list)

    rights_status: str = RIGHTS_UNKNOWN
    # License attribution text an engine can legitimately fill (CC videos).
    attribution: str | None = None

    # Populated by the scoring pass (0-100 each).
    relevance_score: float = 0.0
    engagement_score: float = 0.0
    recency_score: float = 0.0
    short_form_score: float = 0.0
    content_signal_score: float = 0.0
    viral_score: float = 0.0

    # Dedup bookkeeping -- other platforms the same video was also found on.
    duplicate_of: str | None = None
    also_on: list[str] = field(default_factory=list)

    @property
    def aspect_ratio(self) -> float | None:
        if not self.width or not self.height:
            return None
        return round(self.width / self.height, 3)

    @property
    def engagement_rate(self) -> float | None:
        """(likes + comments + shares) / views, using only the metrics that
        are actually present. Returns None when views is missing or zero.
        """
        if not self.views:
            return None
        interactions = sum(v for v in (self.likes, self.comments, self.shares) if v is not None)
        if self.likes is None and self.comments is None and self.shares is None:
            return None
        return interactions / self.views


@dataclass
class EngineOutcome:
    """What one engine returns to the orchestrator. A failure carries an
    error string and an empty result list -- the orchestrator never lets
    one engine's failure sink the whole search (brief section 7 & 32).
    """

    platform: str
    status: str  # "ok" | "unavailable" | "error"
    results: list[VideoResult] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def ok(cls, platform: str, results: list[VideoResult]) -> EngineOutcome:
        return cls(platform=platform, status="ok", results=results)

    @classmethod
    def unavailable(cls, platform: str, reason: str) -> EngineOutcome:
        return cls(platform=platform, status="unavailable", results=[], error=reason)

    @classmethod
    def failed(cls, platform: str, error: str) -> EngineOutcome:
        return cls(platform=platform, status="error", results=[], error=error)
