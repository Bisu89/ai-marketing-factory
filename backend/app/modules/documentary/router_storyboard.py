"""Storyboard scenes, asset registry and the manual image loop (gate 3).
Mounted under the same /documentary prefix by router.py."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.documentary.assets import AssetService, asset_state
from app.modules.documentary.schemas import (
    AssetImportIn,
    AssetOut,
    AssetPatch,
    AssignIn,
    CsvExportOut,
    FolderImportIn,
    PlanOut,
    ReviewOut,
    SceneOut,
    SceneUpdate,
)
from app.modules.documentary.service import DocumentaryService
from app.modules.documentary.storyboard import StoryboardService

router = APIRouter()


def _assets(db: Session, settings: Settings) -> AssetService:
    return AssetService(db, Path(settings.library_dir))


def _scene_out(scene, assets_by_id) -> SceneOut:
    return SceneOut(
        id=scene.id,
        scene_key=scene.scene_key,
        order_index=scene.order_index,
        section_kind=scene.section_kind,
        narration_text=scene.narration_text,
        claim_ids=scene.claim_ids,
        visual_objective=scene.visual_objective,
        visual_preset=scene.visual_preset,
        asset_strategy=scene.asset_strategy,
        image_group=scene.image_group,
        asset_id=scene.asset_id,
        asset_state=asset_state(scene, assets_by_id.get(scene.asset_id)),
        on_screen_text=scene.on_screen_text,
        motion_notes=scene.motion_notes,
        sfx_cues=scene.sfx_cues,
        expected_duration=scene.expected_duration,
        actual_duration=scene.actual_duration,
        render_status=scene.render_status,
        user_edited=scene.user_edited,
    )


def _by_id(db: Session, settings: Settings, project_id: int) -> dict:
    return {a.id: a for a in _assets(db, settings).list(project_id)}


@router.post("/projects/{project_id}/storyboard/plan", response_model=PlanOut)
def plan_storyboard(project_id: int, db: Session = Depends(get_db)):
    return DocumentaryService(db).plan_storyboard(project_id)


@router.get("/projects/{project_id}/scenes", response_model=list[SceneOut])
def list_scenes(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    DocumentaryService(db).get(project_id)
    by_id = _by_id(db, settings, project_id)
    return [_scene_out(s, by_id) for s in StoryboardService(db).list(project_id)]


@router.put("/projects/{project_id}/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    project_id: int, scene_id: int, body: SceneUpdate, db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    scene = StoryboardService(db).update(project_id, scene_id, body.model_dump(exclude_none=True))
    svc.storyboard_changed(project_id)
    return _scene_out(scene, _by_id(db, settings, project_id))


@router.put("/projects/{project_id}/scenes/{scene_id}/asset", response_model=list[SceneOut])
def assign_asset(
    project_id: int, scene_id: int, body: AssignIn, db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    changed = _assets(db, settings).assign(project_id, scene_id, body.asset_id)
    svc.storyboard_changed(project_id)
    by_id = _by_id(db, settings, project_id)
    return [_scene_out(s, by_id) for s in changed]


@router.get("/projects/{project_id}/assets", response_model=list[AssetOut])
def list_assets(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    DocumentaryService(db).get(project_id)
    return _assets(db, settings).list(project_id)


@router.post("/projects/{project_id}/assets/import", response_model=AssetOut, status_code=201)
def import_asset(
    project_id: int, body: AssetImportIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    DocumentaryService(db).get(project_id)
    asset, _ = _assets(db, settings).import_file(
        project_id, Path(body.path), origin=body.origin, license=body.license, attribution=body.attribution,
        source_url=body.source_url, tags=body.tags,
    )
    return asset


@router.post("/projects/{project_id}/assets/{asset_id}/approve", response_model=AssetOut)
def approve_asset(
    project_id: int, asset_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    out = _assets(db, settings).approve(project_id, asset_id)
    svc.storyboard_changed(project_id)
    return out


@router.post("/projects/{project_id}/assets/{asset_id}/reject", response_model=AssetOut)
def reject_asset(
    project_id: int, asset_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    out = _assets(db, settings).reject(project_id, asset_id)
    svc.storyboard_changed(project_id)
    return out


@router.patch("/projects/{project_id}/assets/{asset_id}", response_model=AssetOut)
def patch_asset(
    project_id: int, asset_id: int, body: AssetPatch, db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    out = _assets(db, settings).update_metadata(project_id, asset_id, body.model_dump(exclude_none=True))
    svc.storyboard_changed(project_id)
    return out


@router.get("/projects/{project_id}/assets/review", response_model=ReviewOut)
def assets_review(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    DocumentaryService(db).get(project_id)
    issues = _assets(db, settings).review(project_id)
    return ReviewOut(ok=not issues, issues=issues)


@router.get("/projects/{project_id}/images/export-csv", response_model=CsvExportOut)
def export_image_csv(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    DocumentaryService(db).get(project_id)
    text, info = _assets(db, settings).export_csv(project_id)
    return CsvExportOut(filename=f"documentary_{project_id}_scenes.csv", csv=text, **info)


@router.get("/projects/{project_id}/images/export-csv/download")
def download_image_csv(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    DocumentaryService(db).get(project_id)
    text, _ = _assets(db, settings).export_csv(project_id)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="documentary_{project_id}_scenes.csv"'},
    )


@router.post("/projects/{project_id}/images/import-folder")
def import_image_folder(
    project_id: int, body: FolderImportIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    svc = DocumentaryService(db)
    svc.get(project_id)
    report = _assets(db, settings).import_folder(project_id, Path(body.folder))
    if report["imported"]:
        svc.storyboard_changed(project_id)
    return report
