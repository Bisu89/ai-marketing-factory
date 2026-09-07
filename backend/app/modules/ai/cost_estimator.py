"""Pre-flight production cost estimate for one Story (AI Storytelling
Studio plan, Phase 0 -- sections 9, 21, 24).

Pure: a description of the production's shape in, a CostEstimate out. No
SDK call, no DB. Lives in app.modules.ai so it can import pricing /
image_client / model_router directly (intra-module, allowed -- see
cost_service.py).

The estimate is deliberately CONSERVATIVE: it prices every LLM call at the
provider's *default* (standard-tier) model, even though model_router will
route some calls to a cheaper tier. Erring high is the right direction for
a budget guard -- actuals should come in at or under the estimate, never
over it by surprise.

"null + why, never a fabricated $0" convention (see pricing.call_cost_usd):
when the video provider isn't priced yet (Phase 0 -- it never is), the
video component and the grand total are reported as None with a note,
never as 0.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.modules.ai.image_client import IMAGE_COST_USD
from app.modules.ai.model_router import provider_default_model
from app.modules.ai.pricing import price_for, video_cost_usd

# Rough proxy for how many words of narration one minute of premium TTS
# covers -- only used for a premium provider (edge_tts / local SAPI5 are
# free). Not a precise timing model (that's the Voice stage's job).
_PREMIUM_TTS_WORDS_PER_MINUTE = 150
# Placeholder premium-TTS rate ($/minute). No premium TTS provider is
# configured; kept here so the shape is right. edge_tts / local = $0.
_PREMIUM_TTS_USD_PER_MINUTE: float | None = None
_FREE_TTS_PROVIDERS = ("local", "edge_tts")


@dataclass
class LlmWorkItem:
    """One bucket of LLM work: N calls of roughly this token size."""

    task_kind: str
    calls: int
    avg_input_tokens: int
    avg_output_tokens: int


@dataclass
class CostEstimateInput:
    # The configured text provider ("anthropic" | "openai").
    provider: str
    # All LLM work for the MASTER language: story development, bible,
    # character bible, chapter outline, scene breakdown, research
    # extract/verify, ypp/advertiser screen, etc.
    llm_work: list[LlmWorkItem] = field(default_factory=list)
    # The LLM work to produce ONE additional localized language
    # (translate bible + translate scenes + localize metadata). Multiplied
    # by (target_language_count - 1).
    llm_work_per_language: list[LlmWorkItem] = field(default_factory=list)

    # New AI images to generate AFTER scene-director reuse + visual density
    # (i.e. STILL / STILL_WITH_MOTION scenes that don't reuse a prior
    # image). Visuals are shared across languages -- generated once.
    image_count: int = 0

    # AI_VIDEO scenes and their total generated length. Shared across
    # languages. `video_provider` is "null" until Phase 10.
    ai_video_count: int = 0
    ai_video_total_seconds: float = 0.0
    video_provider: str = "null"

    # Narration for ONE language. TTS is re-run per language.
    tts_provider: str = "edge_tts"
    tts_word_count: int = 0

    # One billed AI title/description rewrite per language (Package stage).
    package_ai_metadata: bool = False
    package_ai_metadata_tokens: tuple[int, int] = (1200, 400)  # (in, out)

    # 1 == master only. Each extra language re-bills: llm_work_per_language
    # + TTS + package metadata. NEVER re-bills images / video / research.
    target_language_count: int = 1


@dataclass
class CostEstimate:
    llm_usd: float
    image_usd: float
    video_usd: float | None            # None when the provider isn't priced
    tts_usd: float
    render_usd: float                  # always 0.0 -- local ffmpeg
    package_usd: float
    master_usd: float                  # cost for the first (master) language
    per_extra_language_usd: float      # marginal cost of each additional language
    total_usd: float | None            # master + (langs-1) * per_extra ; None if video unknown
    all_prices_confirmed: bool
    breakdown: dict
    notes: list[str] = field(default_factory=list)


def _llm_bucket_cost(items: list[LlmWorkItem], provider: str, at: datetime) -> tuple[float, bool, list[str]]:
    model = provider_default_model(provider)
    entry = price_for(provider, model, at)
    notes: list[str] = []
    if entry is None or entry.input_price_per_1m is None or entry.output_price_per_1m is None:
        notes.append(f"Chưa có giá LLM cho {provider}/{model} -- LLM cost ước tính = 0.")
        return 0.0, False, notes
    total = 0.0
    for it in items:
        total += it.calls * (
            it.avg_input_tokens / 1_000_000 * entry.input_price_per_1m
            + it.avg_output_tokens / 1_000_000 * entry.output_price_per_1m
        )
    if not entry.confirmed:
        notes.append(f"Giá LLM {provider}/{model} là ước tính chưa xác nhận.")
    return round(total, 6), entry.confirmed, notes


def _tts_cost(provider: str, word_count: int) -> tuple[float, bool, list[str]]:
    if provider in _FREE_TTS_PROVIDERS:
        return 0.0, True, []
    if _PREMIUM_TTS_USD_PER_MINUTE is None:
        return 0.0, False, [f"TTS provider {provider!r} chưa có giá -- ước tính = 0."]
    minutes = word_count / _PREMIUM_TTS_WORDS_PER_MINUTE
    return round(minutes * _PREMIUM_TTS_USD_PER_MINUTE, 6), True, []


def estimate_story(inp: CostEstimateInput) -> CostEstimate:
    at = datetime.now(timezone.utc)
    notes: list[str] = []
    confirmed = True

    # -- LLM (master + per-language) --
    master_llm, c1, n1 = _llm_bucket_cost(inp.llm_work, inp.provider, at)
    lang_llm, c2, n2 = _llm_bucket_cost(inp.llm_work_per_language, inp.provider, at)
    notes += n1 + n2
    confirmed = confirmed and c1 and (c2 or not inp.llm_work_per_language)

    # -- Images (once, shared across languages) --
    image_usd = round(inp.image_count * IMAGE_COST_USD, 6)

    # -- Video (once, shared) --
    vc = video_cost_usd(inp.video_provider, inp.ai_video_total_seconds)
    video_usd = vc.cost_usd
    if vc.note:
        notes.append(vc.note)
    if video_usd is not None and not vc.confirmed_price:
        confirmed = False

    # -- TTS (per language) --
    tts_master, tc, tn = _tts_cost(inp.tts_provider, inp.tts_word_count)
    notes += tn
    confirmed = confirmed and tc

    # -- Package AI metadata (per language) --
    package_master = 0.0
    if inp.package_ai_metadata:
        pin, pout = inp.package_ai_metadata_tokens
        pkg, pc, pn = _llm_bucket_cost(
            [LlmWorkItem("metadata_rewrite", 1, pin, pout)], inp.provider, at
        )
        package_master = pkg
        notes += pn
        confirmed = confirmed and pc

    langs = max(1, inp.target_language_count)
    master_usd_val = master_llm + image_usd + (video_usd or 0.0) + tts_master + package_master
    per_extra = lang_llm + tts_master + package_master

    total: float | None
    if video_usd is None:
        total = None
        notes.append("Grand total = None cho tới khi chọn video provider (Phase 10).")
    else:
        total = round(master_usd_val + (langs - 1) * per_extra, 6)

    # De-dupe while preserving order (each _llm_bucket_cost call can add the
    # same "unconfirmed price" note).
    notes = list(dict.fromkeys(notes))

    return CostEstimate(
        llm_usd=round(master_llm + (langs - 1) * lang_llm, 6),
        image_usd=image_usd,
        video_usd=video_usd,
        tts_usd=round(tts_master * langs, 6),
        render_usd=0.0,
        package_usd=round(package_master * langs, 6),
        master_usd=round(master_usd_val, 6),
        per_extra_language_usd=round(per_extra, 6),
        total_usd=total,
        all_prices_confirmed=confirmed,
        breakdown={
            "master_llm_usd": master_llm,
            "per_language_llm_usd": lang_llm,
            "image_count": inp.image_count,
            "image_unit_usd": IMAGE_COST_USD,
            "ai_video_count": inp.ai_video_count,
            "ai_video_total_seconds": inp.ai_video_total_seconds,
            "tts_provider": inp.tts_provider,
            "language_count": langs,
        },
        notes=notes,
    )
