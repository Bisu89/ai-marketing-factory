"""Script-generation provider interface. The module itself ships only the
offline MockScriptProvider; the LLM-backed one lives in a composition root
(app/api/v1/endpoints/documentary_llm.py) because modules may not import
app.modules.ai. It registers itself here via `register_provider`.

A provider only ever *arranges* the claims it is given. It must not add
historical facts of its own -- every factual paragraph it returns has to cite
claim ids from `ScriptContext.claims`, and the service rejects anything else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.exceptions import ValidationError
from app.modules.documentary.schemas import (
    SECTION_LABELS_VI,
    SECTION_ORDER,
    OutlineItem,
    ScriptParagraph,
    ScriptSection,
)


@dataclass(frozen=True)
class ClaimView:
    id: int
    text: str
    status: str
    uncertainty_note: str | None
    source_titles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScriptContext:
    title: str
    topic: str
    language: str
    claims: list[ClaimView]


class ScriptProvider(ABC):
    name: str

    @abstractmethod
    def make_outline(self, ctx: ScriptContext) -> list[OutlineItem]: ...

    @abstractmethod
    def make_script(self, ctx: ScriptContext, outline: list[OutlineItem]) -> list[ScriptSection]: ...


class MockScriptProvider(ScriptProvider):
    """Deterministic, offline, free. Spreads the supplied claims over the
    seven sections in order and quotes them verbatim; the connecting lines
    are labelled placeholders and flagged factual=False. Invents nothing."""

    name = "mock"

    def make_outline(self, ctx: ScriptContext) -> list[OutlineItem]:
        n = len(SECTION_ORDER)
        buckets: list[list[int]] = [[] for _ in range(n)]
        for i, c in enumerate(ctx.claims):
            buckets[i * n // max(len(ctx.claims), 1)].append(c.id)
        return [
            OutlineItem(
                kind=kind,
                summary=f"[MẪU] {SECTION_LABELS_VI[kind]} — chủ đề: {ctx.topic}",
                claim_ids=buckets[i],
            )
            for i, kind in enumerate(SECTION_ORDER)
        ]

    def make_script(self, ctx: ScriptContext, outline: list[OutlineItem]) -> list[ScriptSection]:
        by_id = {c.id: c for c in ctx.claims}
        sections = []
        for item in outline:
            paragraphs = [
                ScriptParagraph(
                    text=f"[MẪU — viết lại bằng giọng kể] {SECTION_LABELS_VI[item.kind]}.",
                    factual=False,
                )
            ]
            for cid in item.claim_ids:
                c = by_id[cid]
                text = c.text
                if c.status == "disputed":
                    text = f"Theo một số tài liệu, {c.text[:1].lower()}{c.text[1:]}"
                    if c.uncertainty_note:
                        text += f" Tuy nhiên: {c.uncertainty_note}"
                paragraphs.append(ScriptParagraph(text=text, factual=True, claim_ids=[cid]))
            sections.append(ScriptSection(kind=item.kind, heading=SECTION_LABELS_VI[item.kind], paragraphs=paragraphs))
        return sections


_REGISTRY: dict[str, ScriptProvider] = {"mock": MockScriptProvider()}


def register_provider(provider: ScriptProvider) -> None:
    _REGISTRY[provider.name] = provider


def get_provider(name: str) -> ScriptProvider:
    p = _REGISTRY.get(name)
    if p is None:
        raise ValidationError(
            f"Provider kịch bản '{name}' chưa được cấu hình. Dùng 'mock' hoặc cấu hình API key AI trong Cài đặt."
        )
    return p


def available_providers() -> list[str]:
    return sorted(_REGISTRY)
