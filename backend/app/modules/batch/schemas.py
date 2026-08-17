"""Batch domain contracts + the script parser (Task 13 -- see
docs/features/40-batch-video-creation.md). Pure, no DB/FastAPI/other-module
dependency -- the parser in particular is exercised directly by unit tests
with no server/DB involved at all.
"""

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.modules.batch.models import BATCH_ITEM_STATUSES, BATCH_ITEM_TERMINAL_STATUSES, BATCH_STATUSES

# A line containing only "---" (optional surrounding whitespace) marks a
# new script -- see docs/features/40-batch-video-creation.md's "text file
# format". re.MULTILINE so ^/$ anchor to each line, not the whole string.
_SEPARATOR_RE = re.compile(r"(?m)^[ \t]*---[ \t]*$")


def parse_scripts(raw_text: str) -> list[str]:
    """One script per `---`-separated block; the whole input is one script
    if no separator line is present at all. Normalizes line endings first
    (CRLF/CR -> LF) so a Windows-authored .txt file behaves identically to
    a Unix one. Trims each block and drops any that are blank (an empty
    section between two separators, or a leading/trailing separator) --
    never invents content, never merges/dedupes distinct non-empty blocks
    (two identical scripts pasted twice produce two entries, not one; see
    docs/features/40-batch-video-creation.md section 31).
    """
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    if _SEPARATOR_RE.search(normalized):
        blocks = _SEPARATOR_RE.split(normalized)
    else:
        blocks = [normalized]
    return [block.strip() for block in blocks if block.strip()]


class BatchItemOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    index: int
    script_text: str
    project_id: int | None
    status: str
    error_message: str | None
    render_job_id: int | None
    # Computed only by the composition root's GET /batches/{id} (needs
    # app.modules.asset -- see app/api/v1/endpoints/batch_render.py) --
    # None from the plain, pure GET /batches list view. Never a stored
    # column: render eligibility can change the moment a user assigns a
    # missing asset, so it's always recomputed fresh, never stale.
    eligible: bool | None = None
    ineligible_reason: str | None = None
    # Task 16 (see docs/features/42-content-quality-gate.md) -- same
    # "computed fresh by the composition root, never stale, None outside
    # GET /batches/{id}" shape as eligible/ineligible_reason above. Plain
    # str/int (not a real app.modules.quality.QualityReport import) --
    # this module must never import app.modules.quality.
    quality_status: str | None = None
    quality_score: int | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    template_id: str | None
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[BatchItemOut] = Field(default_factory=list)

    # Task 20 section 32/34/52 -- real, measured progress counts (never a
    # fabricated ETA -- see that section's own explicit "do not display a
    # percentage/time remaining without a defensible calculation"). Derived
    # purely from `items`, so this stays accurate for both the old
    # script-based flow and the new Factory Batch Engine without either
    # needing to maintain a separate counter.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress(self) -> dict[str, int]:
        counts = {"total": len(self.items)}
        for status in BATCH_ITEM_STATUSES:
            counts[status] = sum(1 for item in self.items if item.status == status)
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def videos_per_hour(self) -> float | None:
        """None (never 0 or a guess) until there is at least one real
        completed video and real elapsed wall-clock time to divide by --
        section 33's "do not implement fake ETA" applies just as much to a
        fabricated rate.
        """
        completed = sum(1 for item in self.items if item.status == "COMPLETED")
        if completed == 0 or self.created_at is None:
            return None
        # SQLite round-trips DateTime(timezone=True) as naive (see Task 19's
        # own finding on this) -- strip tzinfo on both sides so "now" (which
        # datetime.now(timezone.utc) always returns aware) can be subtracted
        # from a value that came back from the DB either way.
        started = self.created_at.replace(tzinfo=None)
        end = (self.completed_at or datetime.now(timezone.utc)).replace(tzinfo=None)
        elapsed_hours = (end - started).total_seconds() / 3600.0
        if elapsed_hours <= 0:
            return None
        return round(completed / elapsed_hours, 2)


class CreateBatchRequest(BaseModel):
    name: str
    template_id: str
    scripts_text: str

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Batch name must not be blank")
        return value


class BatchPreviewItem(BaseModel):
    index: int
    project_name: str
    script_preview: str


class BatchPreview(BaseModel):
    template_id: str
    script_count: int
    items: list[BatchPreviewItem]


assert set(BATCH_STATUSES) == {
    "DRAFT", "PROCESSING", "PAUSED", "PAUSED_AFTER_RESTART",
    "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED",
}
# 9 original (Task 13) + NEEDS_REVIEW (Task 16) + RUNNING (Task 20).
assert len(BATCH_ITEM_STATUSES) == 11
assert BATCH_ITEM_TERMINAL_STATUSES == ("COMPLETED", "FAILED", "SKIPPED", "CANCELLED")
