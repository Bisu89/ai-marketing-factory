"""Script versions: save, generate (outline, then full script), and the
factual review that gate 2 depends on."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.modules.documentary.models import DocumentaryProject, DocumentaryScript, DocumentarySource
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import (
    SECTION_ORDER,
    OutlineItem,
    ReviewIssue,
    ReviewOut,
    ScriptOut,
    ScriptSave,
    ScriptSection,
)
from app.modules.documentary.script_providers import ClaimView, ScriptContext, get_provider

# Estimate only. Real timing comes from measured narration audio (Phase 4);
# this is Vietnamese syllables (~ whitespace tokens) per second of calm
# documentary narration, used just to warn early about an off-target length.
SYLLABLES_PER_SECOND = 3.3
TARGET_SECONDS = (8 * 60, 10 * 60)


def word_count(sections: list[ScriptSection]) -> int:
    return sum(len(p.text.split()) for s in sections for p in s.paragraphs)


class ScriptService:
    def __init__(self, db: Session):
        self.db = db
        self.research = ResearchService(db)

    # -- reading -----------------------------------------------------------
    def history(self, project_id: int) -> list[DocumentaryScript]:
        return list(
            self.db.scalars(
                select(DocumentaryScript)
                .where(DocumentaryScript.project_id == project_id)
                .order_by(DocumentaryScript.id)
            )
        )

    def current_row(self, project_id: int) -> DocumentaryScript | None:
        return self.db.scalars(
            select(DocumentaryScript)
            .where(DocumentaryScript.project_id == project_id)
            .order_by(DocumentaryScript.id.desc())
        ).first()

    def to_out(self, row: DocumentaryScript) -> ScriptOut:
        sections = [ScriptSection.model_validate(s) for s in row.sections]
        words = word_count(sections)
        seconds = round(words / SYLLABLES_PER_SECOND)
        return ScriptOut(
            version=row.version,
            origin=row.origin,
            outline=[OutlineItem.model_validate(o) for o in row.outline],
            sections=sections,
            created_at=row.created_at,
            word_count=words,
            estimated_seconds=seconds,
            within_target=TARGET_SECONDS[0] <= seconds <= TARGET_SECONDS[1],
            target_seconds=TARGET_SECONDS,
        )

    # -- writing -----------------------------------------------------------
    def _check_claim_refs(self, project_id: int, data: ScriptSave) -> None:
        known = {c.id for c in self.research.list_claims(project_id)}
        used = {cid for o in data.outline for cid in o.claim_ids}
        used |= {cid for s in data.sections for p in s.paragraphs for cid in p.claim_ids}
        unknown = sorted(used - known)
        if unknown:
            raise ValidationError(f"Kịch bản tham chiếu khẳng định không tồn tại trong dự án: {unknown}")
        kinds = [s.kind for s in data.sections]
        if len(kinds) != len(set(kinds)):
            raise ValidationError("Mỗi phần của kịch bản (hook, context, ...) chỉ được xuất hiện một lần.")

    def save(self, project: DocumentaryProject, data: ScriptSave, origin: str) -> DocumentaryScript:
        """Append a new version. The caller (DocumentaryService) bumps the
        project's script_version first and passes the project in, so the row's
        version always equals the number an approval would record."""
        self._check_claim_refs(project.id, data)
        row = DocumentaryScript(
            project_id=project.id,
            version=project.script_version,
            origin=origin,
            outline=[o.model_dump() for o in data.outline],
            sections=[s.model_dump() for s in data.sections],
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # -- generation ----------------------------------------------------------
    def context(self, project: DocumentaryProject) -> ScriptContext:
        titles = {s.id: s.title for s in self.db.scalars(select(DocumentarySource).where(DocumentarySource.project_id == project.id))}
        claims = [
            ClaimView(
                id=c.id,
                text=c.text,
                status=c.status,
                uncertainty_note=c.uncertainty_note,
                source_titles=[titles[i] for i in c.source_ids if i in titles],
            )
            for c in self.research.list_claims(project.id)
        ]
        if not claims:
            raise ValidationError("Cần có ít nhất một khẳng định (research) trước khi tạo kịch bản.")
        return ScriptContext(title=project.title, topic=project.topic, language=project.language, claims=claims)

    def generate_outline(self, project: DocumentaryProject, provider_name: str) -> ScriptSave:
        ctx = self.context(project)
        outline = get_provider(provider_name).make_outline(ctx)
        return ScriptSave(outline=outline, sections=[])

    def generate_script(self, project: DocumentaryProject, provider_name: str) -> ScriptSave:
        row = self.current_row(project.id)
        if row is None or not row.outline:
            raise ValidationError("Hãy tạo dàn ý (outline) trước khi tạo kịch bản đầy đủ.")
        outline = [OutlineItem.model_validate(o) for o in row.outline]
        ctx = self.context(project)
        sections = get_provider(provider_name).make_script(ctx, outline)
        return ScriptSave(outline=outline, sections=sections)

    # -- gate 2 ------------------------------------------------------------
    def review(self, project_id: int) -> ReviewOut:
        row = self.current_row(project_id)
        if row is None or not row.sections:
            return ReviewOut(
                ok=False,
                issues=[ReviewIssue(code="no_script", message="Chưa có kịch bản đầy đủ (mới có dàn ý hoặc chưa có gì).")],
            )
        project = self.db.get(DocumentaryProject, project_id)
        if row.version != project.script_version:
            return ReviewOut(
                ok=False,
                issues=[
                    ReviewIssue(
                        code="stale_script",
                        message=f"Bản kịch bản mới nhất (v{row.version}) cũ hơn phiên bản hiện tại (v{project.script_version}); hãy lưu lại kịch bản.",
                    )
                ],
            )
        out = self.to_out(row)
        claims = {c.id: c for c in self.research.list_claims(project_id)}
        issues: list[ReviewIssue] = []
        present = {s.kind for s in out.sections}
        for kind in SECTION_ORDER:
            if kind not in present:
                issues.append(ReviewIssue(code="missing_section", message=f"Thiếu phần '{kind}'."))
        for s in out.sections:
            for i, p in enumerate(s.paragraphs, 1):
                where = f"{s.kind} §{i}"
                if p.factual and not p.claim_ids:
                    issues.append(
                        ReviewIssue(code="uncited_claim", message=f"{where}: đoạn khẳng định sự kiện nhưng chưa liên kết khẳng định/nguồn nào.")
                    )
                for cid in p.claim_ids:
                    c = claims.get(cid)
                    if c is None:
                        issues.append(ReviewIssue(code="missing_claim", message=f"{where}: khẳng định #{cid} đã bị xóa."))
                    elif c.status == "unverified":
                        issues.append(
                            ReviewIssue(code="unverified_claim", message=f"{where}: khẳng định #{cid} chưa được xác minh.")
                        )
                    elif not c.source_ids:
                        issues.append(ReviewIssue(code="unsourced_claim", message=f"{where}: khẳng định #{cid} không có nguồn."))
        warnings = []
        if not out.within_target:
            warnings.append(
                ReviewIssue(
                    code="duration_estimate",
                    message=(
                        f"Ước tính {out.estimated_seconds}s ({out.word_count} từ), ngoài mục tiêu "
                        f"{TARGET_SECONDS[0]}–{TARGET_SECONDS[1]}s. Đây chỉ là ước tính; độ dài thật đo từ audio ở bước narration."
                    ),
                )
            )
        if row.origin == "mock":
            warnings.append(ReviewIssue(code="mock_origin", message="Kịch bản được tạo bởi provider mock (nội dung mẫu)."))
        return ReviewOut(ok=not issues, issues=issues, warnings=warnings)
