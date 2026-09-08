"""SearchOrchestrator (brief section 7).

USER QUERY -> expand -> run every engine in PARALLEL -> normalize -> dedup
-> score -> sort. One engine failing never sinks the search; its outcome is
recorded so the UI can show "TikTok  unavailable".

No AI anywhere in this path (brief sections 8 & 9).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.discovery.contracts import EngineOutcome, VideoResult
from app.modules.discovery.dedup import deduplicate
from app.modules.discovery.engines import Engine, build_engines
from app.modules.discovery.engines.base import SearchOptions
from app.modules.discovery.keywords import expand_query, normalize_query
from app.modules.discovery.scoring import ScoreConfig, score_all

logger = logging.getLogger(__name__)

# YouTube's search.list is 100 quota units; Reddit's is free. Cap the
# expanded queries handed to each engine accordingly.
PER_ENGINE_QUERY_CAP = {
    "youtube": 3,
    "reddit": 6,
    "tiktok": 1,
    "instagram": 1,
}
DEFAULT_QUERY_CAP = 4

SORT_KEYS = ("best", "newest", "most_viewed")


@dataclass
class EngineStatus:
    platform: str
    status: str  # ok | unavailable | error
    result_count: int
    error: str | None = None


@dataclass
class SearchOutput:
    query: str
    normalized_query: str
    expanded_queries: list[str]
    results: list[VideoResult]
    engine_statuses: list[EngineStatus] = field(default_factory=list)
    total_before_dedup: int = 0

    @property
    def unique_count(self) -> int:
        return len(self.results)


class SearchOrchestrator:
    def __init__(
        self,
        engines: list[Engine] | None = None,
        *,
        score_config: ScoreConfig | None = None,
        max_workers: int = 4,
    ) -> None:
        self._engines = engines if engines is not None else build_engines()
        self._score_config = score_config or ScoreConfig.default()
        self._max_workers = max_workers

    def search(
        self,
        query: str,
        *,
        limit_per_query: int = 15,
        max_age_days: int | None = 365,
        platforms: list[str] | None = None,
        sort: str = "best",
    ) -> SearchOutput:
        normalized = normalize_query(query)
        expanded = expand_query(normalized)
        wanted = set(platforms) if platforms else None

        engines = [e for e in self._engines if wanted is None or e.platform in wanted]

        outcomes = self._run_engines(engines, normalized, expanded, limit_per_query, max_age_days)

        raw: list[VideoResult] = []
        statuses: list[EngineStatus] = []
        for outcome in outcomes:
            statuses.append(
                EngineStatus(
                    platform=outcome.platform,
                    status=outcome.status,
                    result_count=len(outcome.results),
                    error=outcome.error,
                )
            )
            raw.extend(outcome.results)

        query_terms = _query_terms(expanded)
        scored = score_all(raw, query_terms, self._score_config)
        deduped = deduplicate(scored)
        ordered = _sort_results(deduped, sort)

        return SearchOutput(
            query=query,
            normalized_query=normalized,
            expanded_queries=expanded,
            results=ordered,
            engine_statuses=statuses,
            total_before_dedup=len(scored),
        )

    def _run_engines(
        self,
        engines: list[Engine],
        query: str,
        expanded: list[str],
        limit_per_query: int,
        max_age_days: int | None,
    ) -> list[EngineOutcome]:
        def run(engine: Engine) -> EngineOutcome:
            if not engine.is_configured():
                return EngineOutcome.unavailable(engine.platform, engine.unavailable_reason())
            cap = PER_ENGINE_QUERY_CAP.get(engine.platform, DEFAULT_QUERY_CAP)
            options = SearchOptions(
                limit_per_query=limit_per_query,
                queries=expanded[:cap] or [query],
                max_age_days=max_age_days,
            )
            try:
                return engine.search(query, options)
            except Exception as exc:
                logger.exception("discovery: engine %s crashed", engine.platform)
                return EngineOutcome.failed(engine.platform, f"{engine.platform} search failed: {exc}")

        if not engines:
            return []
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(engines))) as pool:
            return list(pool.map(run, engines))


def _query_terms(expanded: list[str]) -> list[str]:
    terms: list[str] = []
    for phrase in expanded:
        terms.extend(w for w in phrase.split() if len(w) > 2)
    return list(dict.fromkeys(terms))


def _sort_results(results: list[VideoResult], sort: str) -> list[VideoResult]:
    if sort == "newest":
        return sorted(
            results,
            key=lambda v: (v.published_at is not None, v.published_at or _MIN_DT),
            reverse=True,
        )
    if sort == "most_viewed":
        return sorted(results, key=lambda v: (v.views is not None, v.views or 0), reverse=True)
    return sorted(results, key=lambda v: v.viral_score, reverse=True)


_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)
