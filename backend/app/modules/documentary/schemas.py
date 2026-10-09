from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
