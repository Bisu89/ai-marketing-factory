"""Task 10 -- AI Cost Tracking: the one place a text-generation model's
$/token price lives. Generalizes the same "single named constant" shape
llm_client.py's ANTHROPIC_MODEL/OPENAI_MODEL and image_client.py's
IMAGE_COST_USD already use, but as a small table -- provider/model/price
all vary independently, and a re-price shouldn't silently rewrite the
cost of calls already billed at the old rate (see effective_from below).

Neither claude-sonnet-5 nor gpt-5.6-luna has pricing this codebase can
verify against a live provider pricing page today (2026-08) -- unlike
IMAGE_COST_USD, which the user independently confirmed against OpenAI's
own table (see docs/features/59-ai-image-generation.md). Per explicit
user direction (Task 10), the two entries below are seeded with rough
reference estimates instead of being left null, so cost reporting has
real numbers to show from day one -- but they are estimates, not
confirmed prices, and are labelled as such. Replace with the real
negotiated/published rate here -- nowhere else -- once confirmed.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PriceEntry:
    provider: str
    model: str
    input_price_per_1m: float | None  # USD per 1,000,000 input tokens
    output_price_per_1m: float | None  # USD per 1,000,000 output tokens
    effective_from: datetime
    confirmed: bool  # False = estimate, not verified against a real pricing page


# Ordered oldest -> newest per (provider, model). price_for() picks the
# latest entry with effective_from <= the call's own created_at, so
# re-pricing a model going forward never rewrites the cost of historical
# calls that were actually billed at the old rate.
PRICE_TABLE: list[PriceEntry] = [
    PriceEntry(
        provider="anthropic",
        model="claude-sonnet-5",
        # Estimate based on the public per-token rate the Claude Sonnet
        # tier has historically been priced at ($3 / $15 per 1M in/out).
        # Not confirmed for this specific model/date -- see module docstring.
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        confirmed=False,
    ),
    PriceEntry(
        provider="openai",
        model="gpt-5.6-luna",
        # Rough placeholder in line with recent flagship-tier OpenAI chat
        # pricing -- this specific model has no public pricing page this
        # codebase can check. Lowest-confidence entry in this table.
        input_price_per_1m=5.00,
        output_price_per_1m=15.00,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        confirmed=False,
    ),
]


def price_for(provider: str, model: str, at: datetime) -> PriceEntry | None:
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    candidates = [e for e in PRICE_TABLE if e.provider == provider and e.model == model and e.effective_from <= at]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.effective_from)


@dataclass
class CallCost:
    cost_usd: float | None
    note: str | None  # set whenever cost_usd is None -- why it couldn't be computed
    confirmed_price: bool  # False when cost_usd was computed from an unconfirmed estimate


def call_cost_usd(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None, at: datetime
) -> CallCost:
    """Never fabricates a cost: returns cost_usd=None + an explanatory
    note when pricing isn't configured or token counts are missing --
    same "null + why, never guessed" convention Task 07/08's
    VideoPerformance fields already use.
    """
    entry = price_for(provider, model, at)
    if entry is None:
        return CallCost(None, f"Chưa có cấu hình giá cho {provider}/{model}.", False)
    if entry.input_price_per_1m is None or entry.output_price_per_1m is None:
        return CallCost(None, f"Giá cho {provider}/{model} chưa được điền.", False)
    if input_tokens is None or output_tokens is None:
        return CallCost(None, "Lệnh gọi này không có input_tokens/output_tokens để tính chi phí.", False)
    cost = (input_tokens / 1_000_000) * entry.input_price_per_1m + (output_tokens / 1_000_000) * entry.output_price_per_1m
    return CallCost(round(cost, 6), None, entry.confirmed)
