"""Documentary project API. Thin: every rule lives in state_machine.py /
service.py, so the backend (not the UI) enforces the approval gates."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.modules.documentary import state_machine as sm
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import (
    ApprovalIn,
    ApprovalOut,
    BumpIn,
    ClaimIn,
    ClaimOut,
    FailIn,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ReviewOut,
    RewindIn,
    ScriptGenerate,
    ScriptOut,
    ScriptSave,
    SourceIn,
    SourceOut,
)
from app.modules.documentary.script import ScriptService
from app.modules.documentary.script_providers import available_providers
from app.modules.documentary.service import DocumentaryService

router = APIRouter(prefix="/documentary")


def _svc(db: Session = Depends(get_db)) -> DocumentaryService:
    return DocumentaryService(db)


@router.get("/workflow")
def workflow():
    return {
        "states": list(sm.ALL_STATES),
        "gates": [{"gate": g, "review_state": sm.GATES[g][0]} for g in sm.GATE_ORDER],
    }


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(svc: DocumentaryService = Depends(_svc)):
    return svc.list()


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_project(body: ProjectCreate, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.create(body))


@router.post("/projects/demo", response_model=ProjectDetail)
def create_demo_project(svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.create_demo())


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.get(project_id))


@router.get("/projects/{project_id}/approvals", response_model=list[ApprovalOut])
def approval_history(project_id: int, svc: DocumentaryService = Depends(_svc)):
    return svc.history(project_id)


@router.post("/projects/{project_id}/advance", response_model=ProjectDetail)
def advance(project_id: int, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.advance(project_id))


@router.post("/projects/{project_id}/approve", response_model=ProjectDetail)
def approve(project_id: int, body: ApprovalIn, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.approve(project_id, body.gate, body.note))


@router.post("/projects/{project_id}/reject", response_model=ProjectDetail)
def reject(project_id: int, body: ApprovalIn, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.reject(project_id, body.gate, body.note))


@router.post("/projects/{project_id}/rewind", response_model=ProjectDetail)
def rewind(project_id: int, body: RewindIn, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.rewind(project_id, body.to_state, body.note))


@router.post("/projects/{project_id}/artifact-changed", response_model=ProjectDetail)
def artifact_changed(project_id: int, body: BumpIn, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.bump_artifact(project_id, body.artifact))


@router.post("/projects/{project_id}/fail", response_model=ProjectDetail)
def fail(project_id: int, body: FailIn, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.fail(project_id, body.message))


@router.post("/projects/{project_id}/resume", response_model=ProjectDetail)
def resume(project_id: int, svc: DocumentaryService = Depends(_svc)):
    return svc.detail(svc.resume(project_id))


# -- research (gate 1) --------------------------------------------------------
def _research(project_id: int, db: Session) -> tuple[ResearchService, DocumentaryService]:
    svc = DocumentaryService(db)
    svc.get(project_id)  # 404 for an unknown project
    return ResearchService(db), svc


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def list_sources(project_id: int, db: Session = Depends(get_db)):
    research, _ = _research(project_id, db)
    return research.list_sources(project_id)


@router.post("/projects/{project_id}/sources", response_model=SourceOut, status_code=201)
def add_source(project_id: int, body: SourceIn, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    out = research.add_source(project_id, body)
    svc.research_changed(project_id)
    return out


@router.put("/projects/{project_id}/sources/{source_id}", response_model=SourceOut)
def update_source(project_id: int, source_id: int, body: SourceIn, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    out = research.update_source(project_id, source_id, body)
    svc.research_changed(project_id)
    return out


@router.delete("/projects/{project_id}/sources/{source_id}", status_code=204)
def delete_source(project_id: int, source_id: int, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    research.delete_source(project_id, source_id)
    svc.research_changed(project_id)


@router.get("/projects/{project_id}/claims", response_model=list[ClaimOut])
def list_claims(project_id: int, db: Session = Depends(get_db)):
    research, _ = _research(project_id, db)
    return research.list_claims(project_id)


@router.post("/projects/{project_id}/claims", response_model=ClaimOut, status_code=201)
def add_claim(project_id: int, body: ClaimIn, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    out = research.add_claim(project_id, body)
    svc.research_changed(project_id)
    return out


@router.put("/projects/{project_id}/claims/{claim_id}", response_model=ClaimOut)
def update_claim(project_id: int, claim_id: int, body: ClaimIn, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    out = research.update_claim(project_id, claim_id, body)
    svc.research_changed(project_id)
    return out


@router.delete("/projects/{project_id}/claims/{claim_id}", status_code=204)
def delete_claim(project_id: int, claim_id: int, db: Session = Depends(get_db)):
    research, svc = _research(project_id, db)
    research.delete_claim(project_id, claim_id)
    svc.research_changed(project_id)


@router.get("/projects/{project_id}/research/review", response_model=ReviewOut)
def research_review(project_id: int, db: Session = Depends(get_db)):
    research, _ = _research(project_id, db)
    issues = research.review(project_id)
    return ReviewOut(ok=not issues, issues=issues)


# -- script (gate 2) ------------------------------------------------------------
@router.get("/providers")
def providers():
    return {"script": available_providers()}


@router.get("/projects/{project_id}/script", response_model=ScriptOut)
def current_script(project_id: int, db: Session = Depends(get_db)):
    DocumentaryService(db).get(project_id)
    scripts = ScriptService(db)
    row = scripts.current_row(project_id)
    if row is None:
        raise NotFoundError("script", project_id)
    return scripts.to_out(row)


@router.get("/projects/{project_id}/script/history", response_model=list[ScriptOut])
def script_history(project_id: int, db: Session = Depends(get_db)):
    DocumentaryService(db).get(project_id)
    scripts = ScriptService(db)
    return [scripts.to_out(r) for r in scripts.history(project_id)]


@router.put("/projects/{project_id}/script", response_model=ScriptOut)
def save_script(project_id: int, body: ScriptSave, db: Session = Depends(get_db)):
    svc = DocumentaryService(db)
    return ScriptService(db).to_out(svc.save_script(project_id, body, "manual"))


@router.post("/projects/{project_id}/script/outline", response_model=ScriptOut)
def generate_outline(project_id: int, body: ScriptGenerate, db: Session = Depends(get_db)):
    svc = DocumentaryService(db)
    scripts = ScriptService(db)
    draft = scripts.generate_outline(svc.get(project_id), body.provider)
    return scripts.to_out(svc.save_script(project_id, draft, body.provider))


@router.post("/projects/{project_id}/script/generate", response_model=ScriptOut)
def generate_script(project_id: int, body: ScriptGenerate, db: Session = Depends(get_db)):
    svc = DocumentaryService(db)
    scripts = ScriptService(db)
    draft = scripts.generate_script(svc.get(project_id), body.provider)
    return scripts.to_out(svc.save_script(project_id, draft, body.provider))


@router.get("/projects/{project_id}/script/review", response_model=ReviewOut)
def script_review(project_id: int, db: Session = Depends(get_db)):
    DocumentaryService(db).get(project_id)
    return ScriptService(db).review(project_id)

from app.modules.documentary.router_storyboard import router as _storyboard_router  # noqa: E402

router.include_router(_storyboard_router)

from app.modules.documentary.router_narration import router as _narration_router  # noqa: E402

router.include_router(_narration_router)
