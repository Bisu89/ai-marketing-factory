"""Export bundles. Mounted by router.py."""

import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.session import get_db
from app.modules.documentary.export import ExportService
from app.modules.documentary.service import DocumentaryService

router = APIRouter()


class ExportOut(BaseModel):
    id: int
    render_job_id: int
    path: str
    files: dict
    warnings: list
    created_at: str


def _out(e) -> ExportOut:
    return ExportOut(id=e.id, render_job_id=e.render_job_id, path=e.path, files=e.files, warnings=e.warnings, created_at=e.created_at.isoformat())


def _svc(db: Session, settings: Settings) -> DocumentaryService:
    return DocumentaryService(db, library_root=Path(settings.library_dir))


@router.post("/projects/{project_id}/export", response_model=ExportOut, status_code=201)
def export_project(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _out(_svc(db, settings).export_project(project_id))


@router.get("/projects/{project_id}/exports", response_model=list[ExportOut])
def list_exports(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    return [_out(e) for e in ExportService(db, Path(settings.library_dir)).list(project_id)]


@router.post("/projects/{project_id}/exports/{export_id}/open-folder", status_code=204)
def open_export_folder(project_id: int, export_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Reveal the bundle in the OS file manager (server-resolved path from the DB, never from the request)."""
    _svc(db, settings).get(project_id)
    folder = Path(ExportService(db, Path(settings.library_dir)).get(project_id, export_id).path)
    if not folder.is_dir():
        raise ValidationError(f"Thư mục xuất không còn tồn tại: {folder}")
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606
    elif sys.platform == "darwin":
        os.system(f'open "{folder}"')  # noqa: S605
    else:
        os.system(f'xdg-open "{folder}"')  # noqa: S605
