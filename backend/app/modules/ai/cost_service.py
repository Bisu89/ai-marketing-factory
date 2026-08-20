"""Task 10 -- AI Cost Tracking, core layer: turns raw AIGenerationHistory
rows into priced AICallCost entries plus per-provider/model/month/story
aggregates, using pricing.py. Stays inside the `ai` module boundary --
AIGenerationHistory and StoryJob/StoryVersion are all sub-packages of
this same module (see history.py's own docstring), so joining them here
isn't a module-isolation violation. Cross-module rollups (cost per
ContentBatch, cost per produced video) live in the composition root,
app/api/v1/endpoints/ai_costs.py, which alone may import content_batch/
factory/video_composer alongside this.

Never duplicates AIGenerationHistory's own input_tokens/output_tokens --
cost is always computed live from those columns + pricing.py, per this
task's own "do not duplicate token history" instruction.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.ai.history import AIGenerationHistory
from app.modules.ai.pricing import call_cost_usd
from app.modules.ai.story.models import StoryVersion


@dataclass
class AICallCost:
    id: int
    kind: str
    job_id: int | None
    video_id: int
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    cost_usd: float | None
    cost_note: str | None
    confirmed_price: bool
    created_at: datetime


def all_call_costs(db: Session) -> list[AICallCost]:
    rows = db.query(AIGenerationHistory).order_by(AIGenerationHistory.created_at.asc()).all()
    results = []
    for row in rows:
        cc = call_cost_usd(row.provider, row.model, row.input_tokens, row.output_tokens, row.created_at)
        results.append(
            AICallCost(
                id=row.id,
                kind=row.kind,
                job_id=row.job_id,
                video_id=row.video_id,
                provider=row.provider,
                model=row.model,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                latency_ms=row.latency_ms,
                cost_usd=cc.cost_usd,
                cost_note=cc.note,
                confirmed_price=cc.confirmed_price,
                created_at=row.created_at,
            )
        )
    return results


@dataclass
class GroupCost:
    """`unpriced_call_count` calls are excluded from total_cost_usd
    entirely (never estimated as $0) -- see AICallCost.cost_usd's own
    "null, never guessed" convention. `all_confirmed=False` means at
    least one contributing price is pricing.py's own unconfirmed
    estimate, not a verified provider rate.
    """

    label: str
    total_cost_usd: float
    call_count: int
    unpriced_call_count: int
    all_confirmed: bool


def _group(calls: list[AICallCost], key_fn) -> list[GroupCost]:
    buckets: dict[str, list[AICallCost]] = defaultdict(list)
    for c in calls:
        buckets[key_fn(c)].append(c)
    out = []
    for label, items in buckets.items():
        priced = [c for c in items if c.cost_usd is not None]
        out.append(
            GroupCost(
                label=label,
                total_cost_usd=round(sum(c.cost_usd for c in priced), 6),
                call_count=len(items),
                unpriced_call_count=len(items) - len(priced),
                all_confirmed=all(c.confirmed_price for c in priced) if priced else False,
            )
        )
    out.sort(key=lambda g: g.total_cost_usd, reverse=True)
    return out


def cost_by_provider(calls: list[AICallCost]) -> list[GroupCost]:
    return _group(calls, lambda c: c.provider)


def cost_by_model(calls: list[AICallCost]) -> list[GroupCost]:
    return _group(calls, lambda c: f"{c.provider}/{c.model}")


def cost_by_month(calls: list[AICallCost]) -> list[GroupCost]:
    return sorted(_group(calls, lambda c: c.created_at.strftime("%Y-%m")), key=lambda g: g.label)


@dataclass
class StoryCost:
    story_job_id: int
    video_id: int
    total_cost_usd: float
    call_count: int
    unpriced_call_count: int


def cost_by_story(db: Session, calls: list[AICallCost]) -> list[StoryCost]:
    """One StoryJob's total = its own "story"-kind call(s) plus the
    "quality_score" cost of every StoryVersion under it -- a quality_score
    row's job_id points at story_version.id, not story_job.id (see
    AIGenerationHistory's own docstring), so it's remapped via StoryVersion
    before grouping.
    """
    version_to_job = {v.id: v.story_job_id for v in db.query(StoryVersion.id, StoryVersion.story_job_id).all()}

    by_job: dict[int, list[AICallCost]] = defaultdict(list)
    for c in calls:
        if c.kind == "story" and c.job_id is not None:
            by_job[c.job_id].append(c)
        elif c.kind == "quality_score" and c.job_id is not None:
            job_id = version_to_job.get(c.job_id)
            if job_id is not None:
                by_job[job_id].append(c)

    results = []
    for job_id, items in by_job.items():
        priced = [c for c in items if c.cost_usd is not None]
        results.append(
            StoryCost(
                story_job_id=job_id,
                video_id=items[0].video_id,
                total_cost_usd=round(sum(c.cost_usd for c in priced), 6),
                call_count=len(items),
                unpriced_call_count=len(items) - len(priced),
            )
        )
    results.sort(key=lambda s: s.total_cost_usd, reverse=True)
    return results
