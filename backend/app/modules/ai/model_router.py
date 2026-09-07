"""Smart model routing (Phase 0 -- see the AI Storytelling Studio plan,
sections 8, 9, 21). Pure: a task-kind + the configured provider in, a
routing decision out. No SDK call.

The point of this module is that a caller asks for a *task* ("classify",
"final_polish") and gets told which tier -- and therefore which model and
how much token headroom -- to use, instead of every call site reaching
for the one expensive default (llm_client.ANTHROPIC_MODEL /
llm_client.OPENAI_MODEL). The plan estimates 40-60% LLM cost saved once
cheap-tier models are wired.

Phase 0 status: the routing *structure* is complete and every task is
mapped to a tier, but no cheap/premium models are configured yet, so
`route(...).model` is currently always None ("use the provider's default
model"). Filling TIER_MODEL_MAP (e.g. a Haiku-class / mini-class model
for `cheap`) is a one-line change per entry, done in Phase 4 when routing
is actually wired into the story pipeline's LLM calls.

Lives in app.modules.ai alongside llm_client / image_client / pricing --
intra-module imports are fine (see cost_service.py importing history.py).
"""

from dataclasses import dataclass

from app.modules.ai.llm_client import ANTHROPIC_MODEL, OPENAI_MODEL, OPENAI_REASONING_HEADROOM

TIERS = ("cheap", "standard", "premium")

# task_kind -> tier. Unknown task kinds default to "standard" (safe: never
# silently downgrades a call the router doesn't recognise).
TASK_TIER_MAP: dict[str, str] = {
    # deterministic / trivial classification-shaped work
    "classification": "cheap",
    "scene_director_assist": "cheap",   # scene_director itself is deterministic; this is for any future LLM assist
    "advertiser_screen": "cheap",
    "ypp_screen": "cheap",
    "originality_premise": "cheap",
    "source_triage": "cheap",
    "tag_extract": "cheap",
    # structured drafting
    "content_brief": "standard",
    "chapter_outline": "standard",
    "story_development": "standard",
    "scene_breakdown": "standard",
    "research_extract": "standard",
    "research_verify": "standard",
    "character_bible": "standard",
    "localize_scenes": "standard",
    "localize_metadata": "standard",
    "metadata_rewrite": "standard",
    # quality-critical creative work
    "script": "premium",
    "dialogue": "premium",
    "final_polish": "premium",
    "thumbnail_concept": "premium",
}

# provider -> tier -> explicit model id, or None to mean "use the
# provider's configured default model". Phase 0: all None. When a real
# cheap/premium model is added, set it here ONLY.
TIER_MODEL_MAP: dict[str, dict[str, str | None]] = {
    "anthropic": {"cheap": None, "standard": None, "premium": None},
    "openai": {"cheap": None, "standard": None, "premium": None},
}

# Reasoning/answer token headroom bump per tier, added on top of the
# caller's requested max_tokens. `standard` is the baseline (0). A cheap
# model given a hard structured-output task can still need a little room;
# a premium creative pass benefits from more.
TIER_MAX_TOKEN_BONUS: dict[str, int] = {
    "cheap": 0,
    "standard": 0,
    "premium": 1024,
}


@dataclass(frozen=True)
class RouteDecision:
    tier: str
    # None = caller should use the provider's configured default model
    # (llm_client picks ANTHROPIC_MODEL / OPENAI_MODEL). A string = call
    # that model explicitly.
    model: str | None
    max_tokens_bonus: int
    note: str


def provider_default_model(provider: str) -> str:
    return OPENAI_MODEL if provider == "openai" else ANTHROPIC_MODEL


def route(task_kind: str, provider: str, *, tier_override: str | None = None) -> RouteDecision:
    """Resolve a routing decision. `tier_override` (from
    ModelRoutingProjectConfig.tier_overrides) always wins over
    TASK_TIER_MAP.
    """
    if provider not in TIER_MODEL_MAP:
        raise ValueError(f"Unknown provider {provider!r}, must be one of {tuple(TIER_MODEL_MAP)}")

    tier = tier_override or TASK_TIER_MAP.get(task_kind, "standard")
    if tier not in TIERS:
        raise ValueError(f"Unknown tier {tier!r}, must be one of {TIERS}")

    model = TIER_MODEL_MAP[provider][tier]
    if model is None:
        note = f"{task_kind} -> {tier} (no {tier}-tier model configured; using {provider} default)"
    else:
        note = f"{task_kind} -> {tier} ({model})"

    return RouteDecision(
        tier=tier,
        model=model,
        max_tokens_bonus=TIER_MAX_TOKEN_BONUS[tier],
        note=note,
    )


# Re-exported so a caller that only imports model_router can still reach
# the OpenAI reasoning headroom constant llm_client already applies.
__all__ = ["route", "RouteDecision", "TIERS", "TASK_TIER_MAP", "TIER_MODEL_MAP", "provider_default_model", "OPENAI_REASONING_HEADROOM"]
