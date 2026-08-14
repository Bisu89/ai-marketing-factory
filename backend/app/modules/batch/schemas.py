"""Batch domain contracts + the script parser (Task 13 -- see
docs/features/40-batch-video-creation.md). Pure, no DB/FastAPI/other-module
dependency -- the parser in particular is exercised directly by unit tests
with no server/DB involved at all.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.batch.models import BATCH_ITEM_STATUSES, BATCH_STATUSES

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
    items: list[BatchItemOut] = Field(default_factory=list)


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


assert set(BATCH_STATUSES) == {"DRAFT", "PROCESSING", "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED"}
# 9 original (Task 13) + NEEDS_REVIEW (Task 16 -- see
# docs/features/42-content-quality-gate.md).
assert len(BATCH_ITEM_STATUSES) == 10
