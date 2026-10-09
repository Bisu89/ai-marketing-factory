"""Documentary project API. Thin: every rule lives in state_machine.py /
service.py, so the backend (not the UI) enforces the approval gates."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.documentary import state_machine as sm
from app.modules.documentary.schemas import (
    ApprovalIn,
    ApprovalOut,
    BumpIn,
    FailIn,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    RewindIn,
)
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
