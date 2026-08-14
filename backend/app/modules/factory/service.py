"""Database-backed persistence for FactoryRun. Mirrors
app.modules.batch.service's own "SessionLocal per call" shape (called from
both request handlers and a background thread -- see factory_pipeline.py's
_run_project_in_background) for the same reason.
"""

import threading
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.modules.factory.models import FACTORY_RUN_ACTIVE_STATUSES, FactoryRun

# Guards "does project X already have an active run" check-then-create
# (section 44/45: a simple in-process guard is enough for a single-process
# desktop app -- no distributed locking). One lock for all projects, not
# per-project: run creation is rare and fast, so serializing it briefly
# across projects is not a real bottleneck, and it avoids ever having to
# grow/clean up a per-project lock dict.
_create_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_run(run_id: int) -> FactoryRun | None:
    db = SessionLocal()
    try:
        run = db.get(FactoryRun, run_id)
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def get_active_run_for_project(project_id: int) -> FactoryRun | None:
    db = SessionLocal()
    try:
        run = (
            db.query(FactoryRun)
            .filter(FactoryRun.project_id == project_id, FactoryRun.status.in_(FACTORY_RUN_ACTIVE_STATUSES))
            .order_by(FactoryRun.id.desc())
            .first()
        )
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def get_latest_run_for_project(project_id: int) -> FactoryRun | None:
    """Unlike get_active_run_for_project, also returns a terminal
    (COMPLETED/FAILED/CANCELLED) run -- used by the frontend to show "Video
    Ready"/"Production Failed" after the run has already finished, not just
    while it's in flight.
    """
    db = SessionLocal()
    try:
        run = db.query(FactoryRun).filter(FactoryRun.project_id == project_id).order_by(FactoryRun.id.desc()).first()
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def create_run(project_id: int) -> tuple[FactoryRun, bool]:
    """Creates a new run, or returns the project's already-active one
    unchanged (section 43/44: never two active runs for the same project).
    The `created` flag tells the caller (factory_pipeline.py) whether it
    actually needs to spawn a new background execution thread -- reusing
    an existing run must never spawn a second one alongside whatever (if
    anything) is already driving it.
    """
    with _create_lock:
        existing = get_active_run_for_project(project_id)
        if existing is not None:
            return existing, False

        db = SessionLocal()
        try:
            run = FactoryRun(project_id=project_id, status="PREPARING", started_at=_utcnow(), metrics={})
            db.add(run)
            db.commit()
            db.refresh(run)
            db.expunge(run)
            return run, True
        finally:
            db.close()


def set_run_fields(run_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        run = db.get(FactoryRun, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)
        db.commit()
    finally:
        db.close()


def merge_metrics(run_id: int, **timings: float) -> None:
    """Adds/overwrites named seconds-elapsed entries in FactoryRun.metrics
    without clobbering ones already recorded by an earlier stage in the
    same run (see models.py's own docstring on why a missing key, not a
    zero, means "this stage didn't run this time").
    """
    db = SessionLocal()
    try:
        run = db.get(FactoryRun, run_id)
        if run is None:
            return
        merged = dict(run.metrics or {})
        merged.update(timings)
        run.metrics = merged
        db.commit()
    finally:
        db.close()


def list_active_runs() -> list[FactoryRun]:
    """Used by startup reconciliation (section 46-48) -- every run still
    in an active status when the process starts is either genuinely
    running (impossible right after a fresh process start -- there is no
    persisted "worker" for a factory run, see factory_pipeline.py's own
    docstring) or was interrupted by a crash/restart.
    """
    db = SessionLocal()
    try:
        runs = db.query(FactoryRun).filter(FactoryRun.status.in_(FACTORY_RUN_ACTIVE_STATUSES)).all()
        db.expunge_all()
        return runs
    finally:
        db.close()


__all__ = [
    "get_run",
    "get_active_run_for_project",
    "get_latest_run_for_project",
    "create_run",
    "set_run_fields",
    "merge_metrics",
    "list_active_runs",
]
