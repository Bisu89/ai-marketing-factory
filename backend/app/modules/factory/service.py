"""Database-backed persistence for FactoryRun. Mirrors
app.modules.batch.service's own "SessionLocal per call" shape (called from
both request handlers and a background thread -- see factory_pipeline.py's
_run_project_in_background) for the same reason.
"""

import threading
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.modules.factory.models import (
    CHECKPOINT_COMPLETED,
    CHECKPOINT_FAILED,
    CHECKPOINT_RUNNING,
    CHECKPOINT_SKIPPED,
    FACTORY_RUN_ACTIVE_STATUSES,
    FactoryCheckpoint,
    FactoryRun,
)

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


def increment_attempt(run_id: int) -> None:
    """Called once per retry_run() invocation (Task 19 section 26) -- never
    on the original run (that one starts at attempt=1, see FactoryRun's own
    default) and never on Continue (NEEDS_REVIEW -> QUALITY_CHECK isn't a
    retry of a failed stage).
    """
    db = SessionLocal()
    try:
        run = db.get(FactoryRun, run_id)
        if run is None:
            return
        run.attempt = (run.attempt or 1) + 1
        db.commit()
    finally:
        db.close()


# -- Task 19: per-stage checkpoints -----------------------------------------
#
# Answers "what has definitely completed" independently of FactoryRun.status
# (which only ever holds the *current* stage) -- see models.py's own
# FactoryCheckpoint docstring. One row per (factory_run_id, stage); retrying
# a stage re-enters its existing row (bumping `attempt`) rather than
# appending a new one.


def _get_checkpoint(db, run_id: int, stage: str) -> FactoryCheckpoint | None:
    return (
        db.query(FactoryCheckpoint)
        .filter(FactoryCheckpoint.factory_run_id == run_id, FactoryCheckpoint.stage == stage)
        .first()
    )


def start_checkpoint(run_id: int, stage: str) -> FactoryCheckpoint:
    """Transitions a stage to RUNNING (section 9's "atomic stage
    transitions"). A first entry creates the row at attempt=1; a re-entry
    (this same run retrying the same stage, e.g. via retry_run() replaying
    the pipeline from PREPARING) bumps `attempt` and clears whatever
    error_code/error_message the previous attempt left behind.
    """
    db = SessionLocal()
    try:
        now = _utcnow()
        checkpoint = _get_checkpoint(db, run_id, stage)
        if checkpoint is None:
            checkpoint = FactoryCheckpoint(
                factory_run_id=run_id, stage=stage, status=CHECKPOINT_RUNNING,
                attempt=1, started_at=now,
            )
            db.add(checkpoint)
        else:
            checkpoint.attempt = (checkpoint.attempt or 1) + 1
            checkpoint.status = CHECKPOINT_RUNNING
            checkpoint.started_at = now
            checkpoint.completed_at = None
            checkpoint.error_code = None
            checkpoint.error_message = None
        db.commit()
        db.refresh(checkpoint)
        db.expunge(checkpoint)
        return checkpoint
    finally:
        db.close()


def complete_checkpoint(run_id: int, stage: str, metadata: dict | None = None) -> None:
    """Section 10: only ever called *after* the stage's real output has
    already been persisted and validated by the caller -- this function
    itself does no validation, it just durably records that the caller's
    own validation already passed.
    """
    db = SessionLocal()
    try:
        checkpoint = _get_checkpoint(db, run_id, stage)
        if checkpoint is None:
            checkpoint = FactoryCheckpoint(factory_run_id=run_id, stage=stage, attempt=1, started_at=_utcnow())
            db.add(checkpoint)
        checkpoint.status = CHECKPOINT_COMPLETED
        checkpoint.completed_at = _utcnow()
        if metadata is not None:
            checkpoint.checkpoint_metadata = metadata
        db.commit()
    finally:
        db.close()


def skip_checkpoint(run_id: int, stage: str, metadata: dict | None = None) -> None:
    """PREPARING_VISUALS (section 12's own note: a real but pass-through
    stage in this codebase -- see factory_pipeline.py) uses this instead of
    complete_checkpoint so its checkpoint history honestly reflects "there
    was nothing to do here," not "this stage did work and validated it."
    """
    db = SessionLocal()
    try:
        checkpoint = _get_checkpoint(db, run_id, stage)
        now = _utcnow()
        if checkpoint is None:
            checkpoint = FactoryCheckpoint(factory_run_id=run_id, stage=stage, attempt=1, started_at=now)
            db.add(checkpoint)
        checkpoint.status = CHECKPOINT_SKIPPED
        checkpoint.completed_at = now
        if metadata is not None:
            checkpoint.checkpoint_metadata = metadata
        db.commit()
    finally:
        db.close()


def fail_checkpoint(run_id: int, stage: str, error_code: str, error_message: str) -> None:
    db = SessionLocal()
    try:
        checkpoint = _get_checkpoint(db, run_id, stage)
        if checkpoint is None:
            checkpoint = FactoryCheckpoint(factory_run_id=run_id, stage=stage, attempt=1, started_at=_utcnow())
            db.add(checkpoint)
        checkpoint.status = CHECKPOINT_FAILED
        checkpoint.completed_at = _utcnow()
        checkpoint.error_code = error_code
        checkpoint.error_message = error_message
        db.commit()
    finally:
        db.close()


def force_checkpoint_status(
    run_id: int, stage: str, status: str, error_code: str | None = None, error_message: str | None = None
) -> None:
    """Used only by startup reconciliation (section 21) to settle whichever
    checkpoint was RUNNING when the previous process died -- everything
    else uses the narrower start/complete/skip/fail_checkpoint helpers
    above so a stage function can never silently mark itself COMPLETED
    without going through complete_checkpoint's own "caller already
    validated this" contract.
    """
    db = SessionLocal()
    try:
        checkpoint = _get_checkpoint(db, run_id, stage)
        now = _utcnow()
        if checkpoint is None:
            checkpoint = FactoryCheckpoint(factory_run_id=run_id, stage=stage, attempt=1, started_at=now)
            db.add(checkpoint)
        checkpoint.status = status
        checkpoint.completed_at = now
        checkpoint.error_code = error_code
        checkpoint.error_message = error_message
        db.commit()
    finally:
        db.close()


def get_checkpoints(run_id: int) -> list[FactoryCheckpoint]:
    db = SessionLocal()
    try:
        checkpoints = (
            db.query(FactoryCheckpoint).filter(FactoryCheckpoint.factory_run_id == run_id).order_by(FactoryCheckpoint.id).all()
        )
        db.expunge_all()
        return checkpoints
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
    "increment_attempt",
    "start_checkpoint",
    "complete_checkpoint",
    "skip_checkpoint",
    "fail_checkpoint",
    "force_checkpoint_status",
    "get_checkpoints",
    "list_active_runs",
]
