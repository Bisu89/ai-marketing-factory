"""Project lifecycle + approval gates. All rules live in state_machine.py;
this layer only reads/writes rows and applies them."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary import state_machine as sm
from app.modules.documentary.models import DocumentaryApproval, DocumentaryProject
from app.modules.documentary.narration import NarrationService
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import GateStatus, ProjectCreate, ProjectDetail, ProjectOut, ScriptSave
from app.modules.documentary.script import ScriptService
from app.modules.documentary.storyboard import StoryboardService

DEMO_TITLE = "[MẪU] Dự án demo — không phải nội dung lịch sử đã kiểm chứng"
DEMO_TOPIC = (
    "Dự án mẫu để thử quy trình. Nội dung chỉ là chỗ giữ chỗ (placeholder), "
    "không chứa bất kỳ khẳng định lịch sử nào được coi là đã xác minh."
)


class DocumentaryService:
    def __init__(self, db: Session, library_root: Path | None = None):
        self.db = db
        self.library_root = library_root  # None -> settings.library_dir (tests pass a temp dir)

    # -- projects ---------------------------------------------------------
    def create(self, data: ProjectCreate, *, is_demo: bool = False) -> DocumentaryProject:
        p = DocumentaryProject(
            title=data.title.strip(),
            topic=data.topic.strip(),
            language=data.language,
            budget_usd=data.budget_usd,
            is_demo=is_demo,
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def create_demo(self) -> DocumentaryProject:
        existing = self.db.scalars(
            select(DocumentaryProject).where(DocumentaryProject.is_demo.is_(True))
        ).first()
        if existing:
            return existing
        return self.create(ProjectCreate(title=DEMO_TITLE, topic=DEMO_TOPIC), is_demo=True)

    def get(self, project_id: int) -> DocumentaryProject:
        p = self.db.get(DocumentaryProject, project_id)
        if p is None:
            raise NotFoundError("documentary project", project_id)
        return p

    def list(self) -> list[DocumentaryProject]:
        return list(
            self.db.scalars(select(DocumentaryProject).order_by(DocumentaryProject.updated_at.desc()))
        )

    def history(self, project_id: int) -> list[DocumentaryApproval]:
        self.get(project_id)
        return list(
            self.db.scalars(
                select(DocumentaryApproval)
                .where(DocumentaryApproval.project_id == project_id)
                .order_by(DocumentaryApproval.id)
            )
        )

    # -- gate status -------------------------------------------------------
    def _latest(self, project_id: int, gate: str) -> DocumentaryApproval | None:
        return self.db.scalars(
            select(DocumentaryApproval)
            .where(DocumentaryApproval.project_id == project_id, DocumentaryApproval.gate == gate)
            .order_by(DocumentaryApproval.id.desc())
        ).first()

    def _version(self, p: DocumentaryProject, gate: str) -> int:
        return getattr(p, sm.GATES[gate][1])

    def gate_statuses(self, p: DocumentaryProject) -> list[GateStatus]:
        out = []
        for gate in sm.GATE_ORDER:
            latest = self._latest(p.id, gate)
            current = self._version(p, gate)
            if latest is None or latest.decision == "revoked":
                status, approved = "pending", None
            elif latest.decision == "rejected":
                status, approved = "rejected", None
            elif latest.artifact_version != current:
                status, approved = "stale", latest.artifact_version
            else:
                status, approved = "approved", latest.artifact_version
            out.append(
                GateStatus(
                    gate=gate,
                    review_state=sm.GATES[gate][0],
                    status=status,
                    approved_version=approved,
                    current_version=current,
                )
            )
        return out

    def valid_gates(self, p: DocumentaryProject) -> set[str]:
        return {g.gate for g in self.gate_statuses(p) if g.status == "approved"}

    def detail(self, p: DocumentaryProject) -> ProjectDetail:
        valid = self.valid_gates(p)
        next_state, blockers = None, []
        if p.state != sm.FAILED and p.state != sm.STATES[-1]:
            target = sm.STATES[sm.state_index(p.state) + 1]
            next_state = target
            blockers = [g for g in sm.required_gates(target) if g not in valid]
        return ProjectDetail(
            **ProjectOut.model_validate(p).model_dump(),
            gates=self.gate_statuses(p),
            next_state=next_state,
            blockers=blockers,
        )

    # -- transitions -------------------------------------------------------
    def advance(self, project_id: int) -> DocumentaryProject:
        p = self.get(project_id)
        p.state = sm.check_advance(p.state, self.valid_gates(p))
        self.db.commit()
        self.db.refresh(p)
        return p

    def _record(self, p: DocumentaryProject, gate: str, decision: str, note: str | None) -> None:
        self.db.add(
            DocumentaryApproval(
                project_id=p.id,
                gate=gate,
                decision=decision,
                artifact_version=self._version(p, gate),
                note=note,
            )
        )

    def approve(self, project_id: int, gate: str, note: str | None = None) -> DocumentaryProject:
        p = self.get(project_id)
        review_state = sm.gate_state(gate)
        if p.state != review_state:
            raise ValidationError(
                f"Cổng '{gate}' chỉ được duyệt khi dự án ở trạng thái '{review_state}' (hiện tại: '{p.state}')."
            )
        self._check_gate(p, gate)
        self._record(p, gate, "approved", note)
        self.db.commit()
        self.db.refresh(p)
        return p

    def _root(self) -> Path:
        from app.core.config import get_settings

        return self.library_root or Path(get_settings().library_dir)

    def _check_gate(self, p: DocumentaryProject, gate: str) -> None:
        """Content checks a gate needs beyond "you are in the right state"."""
        if gate == "research":
            issues = ResearchService(self.db).review(p.id)
        elif gate == "script":
            issues = ScriptService(self.db).review(p.id).issues
        elif gate == "storyboard_assets":
            from app.core.config import get_settings
            from app.modules.documentary.assets import AssetService

            issues = AssetService(self.db, self._root()).review(p.id)
        elif gate == "narration_timing":
            issues = NarrationService(self.db, self._root()).review(p.id)
        else:
            return
        if issues:
            raise ValidationError(f"Chưa thể duyệt cổng '{gate}': " + "; ".join(i.message for i in issues))

    def reject(self, project_id: int, gate: str, note: str | None = None) -> DocumentaryProject:
        p = self.get(project_id)
        review_state = sm.gate_state(gate)
        if p.state != review_state:
            raise ValidationError(
                f"Cổng '{gate}' chỉ được từ chối khi dự án ở trạng thái '{review_state}' (hiện tại: '{p.state}')."
            )
        self._record(p, gate, "rejected", note)
        self.db.commit()
        self.db.refresh(p)
        return p

    def _revoke(self, p: DocumentaryProject, gates: list[str], note: str) -> None:
        live = {g.gate for g in self.gate_statuses(p) if g.status in ("approved", "stale")}
        for gate in gates:
            if gate in live:
                self._record(p, gate, "revoked", note)

    def rewind(self, project_id: int, to_state: str, note: str | None = None) -> DocumentaryProject:
        p = self.get(project_id)
        if p.state == sm.FAILED:
            raise ValidationError("Dự án đang ở trạng thái lỗi — hãy tiếp tục (resume) trước.")
        if to_state == "draft":
            raise ValidationError("Không thể quay về 'draft'.")
        if sm.state_index(to_state) >= sm.state_index(p.state):
            raise ValidationError("Chỉ có thể quay lại một trạng thái trước đó.")
        self._revoke(p, sm.gates_invalidated_by_rewind(to_state), note or f"Quay lại '{to_state}'")
        p.state = to_state
        self.db.commit()
        self.db.refresh(p)
        return p

    def bump_artifact(self, project_id: int, artifact: str) -> DocumentaryProject:
        """An approved artifact was edited. Its version increments, its own
        approval and every downstream approval are revoked (never silently
        reused), and a project already past that stage goes back to it."""
        p = self.get(project_id)
        gate = sm.ARTIFACT_GATE.get(artifact)
        if gate is None:
            raise ValidationError(f"Loại artifact không hợp lệ: {artifact!r}")
        self._revoke(p, sm.gates_invalidated_by_artifact(artifact), f"Artifact '{artifact}' đã thay đổi")
        column = sm.GATES[gate][1]
        setattr(p, column, getattr(p, column) + 1)
        review_state = sm.gate_state(gate)
        if p.state in sm.STATES and sm.state_index(p.state) > sm.state_index(review_state):
            p.state = review_state
        self.db.commit()
        self.db.refresh(p)
        return p

    def fail(self, project_id: int, message: str) -> DocumentaryProject:
        p = self.get(project_id)
        if p.state in (sm.FAILED, "exported"):
            raise ValidationError(f"Không thể đánh dấu lỗi từ trạng thái '{p.state}'.")
        p.failed_from_state = p.state
        p.error_message = message
        p.state = sm.FAILED
        self.db.commit()
        self.db.refresh(p)
        return p

    def resume(self, project_id: int) -> DocumentaryProject:
        p = self.get(project_id)
        if p.state != sm.FAILED or not p.failed_from_state:
            raise ValidationError("Dự án không ở trạng thái lỗi.")
        p.state = p.failed_from_state
        p.failed_from_state = None
        p.error_message = None
        self.db.commit()
        self.db.refresh(p)
        return p

    # -- research / script edits (each invalidates what depends on it) ---------
    def research_changed(self, project_id: int) -> None:
        self.bump_artifact(project_id, "research")

    def save_script(self, project_id: int, data: ScriptSave, origin: str):
        p = self.get(project_id)
        scripts = ScriptService(self.db)
        scripts._check_claim_refs(p.id, data)  # validate before bumping the version
        p = self.bump_artifact(project_id, "script")
        return scripts.save(p, data, origin)

    def plan_storyboard(self, project_id: int) -> dict:
        p = self.get(project_id)
        if "script" not in self.valid_gates(p):
            raise ValidationError("Cần duyệt kịch bản (cổng 'script') trước khi lập storyboard.")
        result = StoryboardService(self.db).plan(p)
        # New/removed scenes make any storyboard approval stale; an identical
        # re-plan changes nothing. Upstream (research/script) is never touched.
        if result["created"] or result["removed"]:
            self.bump_artifact(project_id, "storyboard")
        return result

    def storyboard_changed(self, project_id: int) -> None:
        self.bump_artifact(project_id, "storyboard")

    # -- narration (expensive: needs gate 3) ---------------------------------------
    def plan_narration(self, project_id: int) -> dict:
        self.get(project_id)
        result = NarrationService(self.db, self._root()).plan(project_id)
        if result["created"] or result["removed"]:
            self.bump_artifact(project_id, "narration")
        return result

    def generate_narration(self, project_id: int, backend: str, only: list[str] | None, confirm: bool) -> dict:
        p = self.get(project_id)
        if "storyboard_assets" not in self.valid_gates(p):
            raise ValidationError("Cần duyệt cổng storyboard_assets trước khi tạo audio (bước tốn chi phí).")
        result = NarrationService(self.db, self._root()).generate(p, backend, only=only, confirm=confirm)
        if result["generated"]:
            self.bump_artifact(project_id, "narration")
        return result
