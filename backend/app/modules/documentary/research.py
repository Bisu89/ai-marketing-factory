"""Research records: manually entered sources and claims, and the claim ->
source links. Nothing is fetched or generated here, so nothing can be
fabricated; a web-search provider can later *propose* rows through the same
service without this layer changing.

Rule enforced on every write: a claim may only be `verified` or `disputed`
while it has at least one linked source. An LLM never sets "verified" --
only a person editing a claim does.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary.models import DocumentaryClaim, DocumentaryClaimSource, DocumentarySource
from app.modules.documentary.schemas import ClaimIn, ClaimOut, ReviewIssue, SourceIn

NEEDS_SOURCE = ("verified", "disputed")


class ResearchService:
    def __init__(self, db: Session):
        self.db = db

    # -- sources -----------------------------------------------------------
    def list_sources(self, project_id: int) -> list[DocumentarySource]:
        return list(
            self.db.scalars(
                select(DocumentarySource).where(DocumentarySource.project_id == project_id).order_by(DocumentarySource.id)
            )
        )

    def _source(self, project_id: int, source_id: int) -> DocumentarySource:
        s = self.db.get(DocumentarySource, source_id)
        if s is None or s.project_id != project_id:
            raise NotFoundError("source", source_id)
        return s

    def add_source(self, project_id: int, data: SourceIn) -> DocumentarySource:
        s = DocumentarySource(project_id=project_id, **data.model_dump())
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def update_source(self, project_id: int, source_id: int, data: SourceIn) -> DocumentarySource:
        s = self._source(project_id, source_id)
        for k, v in data.model_dump().items():
            setattr(s, k, v)
        self.db.commit()
        self.db.refresh(s)
        return s

    def delete_source(self, project_id: int, source_id: int) -> None:
        s = self._source(project_id, source_id)
        linked = list(
            self.db.scalars(select(DocumentaryClaimSource).where(DocumentaryClaimSource.source_id == source_id))
        )
        for link in linked:
            claim = self.db.get(DocumentaryClaim, link.claim_id)
            remaining = [x for x in self._source_ids(claim.id) if x != source_id]
            if claim.status in NEEDS_SOURCE and not remaining:
                raise ValidationError(
                    f"Không thể xóa nguồn: khẳng định #{claim.id} ({claim.status}) sẽ không còn nguồn nào. "
                    "Hãy đổi trạng thái khẳng định về 'unverified' hoặc thêm nguồn khác trước."
                )
        self.db.execute(delete(DocumentaryClaimSource).where(DocumentaryClaimSource.source_id == source_id))
        self.db.delete(s)
        self.db.commit()

    # -- claims ------------------------------------------------------------
    def _source_ids(self, claim_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(DocumentaryClaimSource.source_id)
                .where(DocumentaryClaimSource.claim_id == claim_id)
                .order_by(DocumentaryClaimSource.source_id)
            )
        )

    def _out(self, c: DocumentaryClaim) -> ClaimOut:
        return ClaimOut(
            id=c.id,
            project_id=c.project_id,
            text=c.text,
            status=c.status,
            uncertainty_note=c.uncertainty_note,
            source_ids=self._source_ids(c.id),
        )

    def list_claims(self, project_id: int) -> list[ClaimOut]:
        rows = self.db.scalars(
            select(DocumentaryClaim).where(DocumentaryClaim.project_id == project_id).order_by(DocumentaryClaim.id)
        )
        return [self._out(c) for c in rows]

    def _claim(self, project_id: int, claim_id: int) -> DocumentaryClaim:
        c = self.db.get(DocumentaryClaim, claim_id)
        if c is None or c.project_id != project_id:
            raise NotFoundError("claim", claim_id)
        return c

    def _validate_claim(self, project_id: int, data: ClaimIn) -> list[int]:
        ids = sorted(set(data.source_ids))
        if ids:
            owned = set(
                self.db.scalars(
                    select(DocumentarySource.id).where(
                        DocumentarySource.project_id == project_id, DocumentarySource.id.in_(ids)
                    )
                )
            )
            missing = [i for i in ids if i not in owned]
            if missing:
                raise ValidationError(f"Nguồn không tồn tại trong dự án này: {missing}")
        if data.status in NEEDS_SOURCE and not ids:
            raise ValidationError(
                f"Khẳng định chỉ được đánh dấu '{data.status}' khi có ít nhất một nguồn liên kết."
            )
        return ids

    def _set_links(self, claim_id: int, source_ids: list[int]) -> None:
        self.db.execute(delete(DocumentaryClaimSource).where(DocumentaryClaimSource.claim_id == claim_id))
        for sid in source_ids:
            self.db.add(DocumentaryClaimSource(claim_id=claim_id, source_id=sid))

    def add_claim(self, project_id: int, data: ClaimIn) -> ClaimOut:
        ids = self._validate_claim(project_id, data)
        c = DocumentaryClaim(
            project_id=project_id, text=data.text.strip(), status=data.status, uncertainty_note=data.uncertainty_note
        )
        self.db.add(c)
        self.db.flush()
        self._set_links(c.id, ids)
        self.db.commit()
        return self._out(c)

    def update_claim(self, project_id: int, claim_id: int, data: ClaimIn) -> ClaimOut:
        c = self._claim(project_id, claim_id)
        ids = self._validate_claim(project_id, data)
        c.text, c.status, c.uncertainty_note = data.text.strip(), data.status, data.uncertainty_note
        self._set_links(c.id, ids)
        self.db.commit()
        return self._out(c)

    def delete_claim(self, project_id: int, claim_id: int) -> None:
        c = self._claim(project_id, claim_id)
        self.db.execute(delete(DocumentaryClaimSource).where(DocumentaryClaimSource.claim_id == claim_id))
        self.db.delete(c)
        self.db.commit()

    # -- gate 1 ------------------------------------------------------------
    def review(self, project_id: int) -> list[ReviewIssue]:
        claims = self.list_claims(project_id)
        if not claims:
            return [ReviewIssue(code="no_claims", message="Chưa có khẳng định nào. Hãy thêm ít nhất một khẳng định cùng nguồn.")]
        issues = []
        for c in claims:
            if c.status == "disputed" and not (c.uncertainty_note or "").strip():
                issues.append(
                    ReviewIssue(
                        code="disputed_without_note",
                        message=f"Khẳng định #{c.id} đang tranh cãi nhưng chưa ghi chú các cách giải thích khác nhau.",
                    )
                )
        if not any(c.status in NEEDS_SOURCE for c in claims):
            issues.append(
                ReviewIssue(
                    code="nothing_sourced",
                    message="Chưa có khẳng định nào được liên kết nguồn và đánh dấu verified/disputed.",
                )
            )
        return issues
