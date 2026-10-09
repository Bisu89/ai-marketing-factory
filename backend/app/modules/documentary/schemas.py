from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

ArtifactKind = Literal["research", "script", "storyboard", "narration", "render"]


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=2000)
    language: str = "vi"
    budget_usd: float | None = Field(default=None, ge=0)


class GateStatus(BaseModel):
    gate: str
    review_state: str
    status: Literal["pending", "approved", "stale", "rejected"]
    approved_version: int | None
    current_version: int


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    topic: str
    language: str
    state: str
    failed_from_state: str | None
    error_message: str | None
    budget_usd: float | None
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    gates: list[GateStatus]
    next_state: str | None
    blockers: list[str]


class ApprovalIn(BaseModel):
    gate: str
    note: str | None = Field(default=None, max_length=2000)


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gate: str
    decision: str
    artifact_version: int
    note: str | None
    created_at: datetime


class RewindIn(BaseModel):
    to_state: str
    note: str | None = Field(default=None, max_length=2000)


class BumpIn(BaseModel):
    artifact: ArtifactKind


class FailIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# -- research ---------------------------------------------------------------
ClaimStatus = Literal["verified", "disputed", "unverified"]
_http_url = TypeAdapter(AnyHttpUrl)


class SourceIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2000)
    publisher: str | None = Field(default=None, max_length=300)
    author: str | None = Field(default=None, max_length=300)
    published_date: date | None = None
    accessed_date: date | None = None
    excerpt: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        # Stored, never fetched. Still reject file:/javascript: etc. so a
        # saved "source" can never become a local-file or script link.
        if v is None or not v.strip():
            return None
        v = v.strip()
        _http_url.validate_python(v)
        return v


class SourceOut(SourceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int


class ClaimIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    status: ClaimStatus = "unverified"
    uncertainty_note: str | None = Field(default=None, max_length=2000)
    source_ids: list[int] = Field(default_factory=list)


class ClaimOut(BaseModel):
    id: int
    project_id: int
    text: str
    status: ClaimStatus
    uncertainty_note: str | None
    source_ids: list[int]


# -- script -----------------------------------------------------------------
SectionKind = Literal[
    "hook", "context", "timeline", "evidence", "turning_point", "consequences", "conclusion"
]
SECTION_ORDER: tuple[str, ...] = (
    "hook", "context", "timeline", "evidence", "turning_point", "consequences", "conclusion",
)
SECTION_LABELS_VI: dict[str, str] = {
    "hook": "Mở đầu gây chú ý",
    "context": "Bối cảnh lịch sử",
    "timeline": "Dòng thời gian sự kiện",
    "evidence": "Bằng chứng và các cách giải thích",
    "turning_point": "Bước ngoặt",
    "consequences": "Hệ quả",
    "conclusion": "Kết luận và câu hỏi còn bỏ ngỏ",
}


class OutlineItem(BaseModel):
    kind: SectionKind
    summary: str = Field(min_length=1, max_length=1000)
    claim_ids: list[int] = Field(default_factory=list)


class ScriptParagraph(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    # factual=True means the paragraph asserts something about the past and
    # must cite >=1 claim. Framing/transition lines set it False.
    factual: bool = True
    claim_ids: list[int] = Field(default_factory=list)


class ScriptSection(BaseModel):
    kind: SectionKind
    heading: str = Field(min_length=1, max_length=200)
    paragraphs: list[ScriptParagraph]


class ScriptSave(BaseModel):
    outline: list[OutlineItem] = Field(default_factory=list)
    sections: list[ScriptSection] = Field(default_factory=list)


class ScriptGenerate(BaseModel):
    provider: Literal["mock", "llm"] = "mock"


class ScriptOut(BaseModel):
    version: int
    origin: str
    outline: list[OutlineItem]
    sections: list[ScriptSection]
    created_at: datetime
    word_count: int
    estimated_seconds: int
    within_target: bool
    target_seconds: tuple[int, int]


class ReviewIssue(BaseModel):
    code: str
    message: str


class ReviewOut(BaseModel):
    ok: bool
    issues: list[ReviewIssue]
    warnings: list[ReviewIssue] = Field(default_factory=list)
