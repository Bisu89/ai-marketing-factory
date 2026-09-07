"""Database-backed persistence for the story planning layer (feature 131).

`SessionLocal` per call + `db.expunge` before returning a detached row --
the same shape app.modules.series.service and
app.modules.beat.project_service already use (callers include background
threads, not just request handlers). No cross-module import; no business
rules beyond ownership checks and the state-machine guards a resumable
StoryRun needs (Phase 2 fills those in).
"""

import threading
from datetime import datetime, timezone

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.story.models import (
    CHECKPOINT_COMPLETED,
    CHECKPOINT_FAILED,
    CHECKPOINT_RUNNING,
    CHECKPOINT_SKIPPED,
    STORY_RUN_ACTIVE_STATUSES,
    STORY_RUN_STAGES,
    StoryChannel,
    Episode,
    Story,
    StoryChapter,
    StoryCharacter,
    StoryCheckpoint,
    StoryLocation,
    StoryRun,
    StoryScene,
)

# Guards the "does this story already have an active run" check-then-create
# (a single-process desktop app -- an in-process lock is enough, same as
# app.modules.factory.service._create_lock).
_create_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -- StoryChannel ------------------------------------------------------------


def create_channel(**fields) -> StoryChannel:
    db = SessionLocal()
    try:
        row = StoryChannel(**fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def get_channel(channel_id: int) -> StoryChannel:
    db = SessionLocal()
    try:
        row = db.get(StoryChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_channels() -> list[StoryChannel]:
    db = SessionLocal()
    try:
        rows = db.query(StoryChannel).order_by(StoryChannel.id.desc()).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_channel(channel_id: int, **fields) -> StoryChannel:
    db = SessionLocal()
    try:
        row = db.get(StoryChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_channel(channel_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


# -- Episode ----------------------------------------------------------
#
# `series_id` is stored as a bare int (Series is another module -- see the
# schemas.py note). An orphan Episode is harmless, not an error.


def create_episode(**fields) -> Episode:
    db = SessionLocal()
    try:
        row = Episode(**fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def get_episode(episode_id: int) -> Episode:
    db = SessionLocal()
    try:
        row = db.get(Episode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_episodes_for_series(series_id: int) -> list[Episode]:
    db = SessionLocal()
    try:
        rows = db.query(Episode).filter(Episode.series_id == series_id).order_by(Episode.order).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_episode(episode_id: int, **fields) -> Episode:
    db = SessionLocal()
    try:
        row = db.get(Episode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_episode(episode_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(Episode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


# -- Story ----------------------------------------------------------


def create_story(**fields) -> Story:
    db = SessionLocal()
    try:
        episode_id = fields.get("episode_id")
        if episode_id is not None and db.get(Episode, episode_id) is None:
            raise NotFoundError("Episode", episode_id)
        row = Story(**fields)
        db.add(row)
        db.commit()
        # link back from the episode (a slot has one story)
        if episode_id is not None:
            ep = db.get(Episode, episode_id)
            ep.story_id = row.id
            db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def get_story(story_id: int) -> Story:
    db = SessionLocal()
    try:
        row = db.get(Story, story_id)
        if row is None:
            raise NotFoundError("Story", story_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_stories(*, mode: str | None = None, status: str | None = None) -> list[Story]:
    db = SessionLocal()
    try:
        q = db.query(Story)
        if mode is not None:
            q = q.filter(Story.mode == mode)
        if status is not None:
            q = q.filter(Story.status == status)
        rows = q.order_by(Story.id.desc()).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def patch_story(story_id: int, patch: dict) -> Story:
    db = SessionLocal()
    try:
        row = db.get(Story, story_id)
        if row is None:
            raise NotFoundError("Story", story_id)
        for k, v in patch.items():
            if v is None and k not in ("logline", "genre", "budget_usd", "reference_notes", "episode_id"):
                continue  # a None in a PATCH means "not provided" for most fields
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_story(story_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(Story, story_id)
        if row is None:
            raise NotFoundError("Story", story_id)
        active = db.query(StoryRun).filter(
            StoryRun.story_id == story_id, StoryRun.status.in_(STORY_RUN_ACTIVE_STATUSES)
        ).first()
        if active is not None:
            raise ValidationError(f"Story {story_id} has an active run (#{active.id}); cancel it before deleting.")
        db.delete(row)
        db.commit()
    finally:
        db.close()


# -- Character / Location (children of a Story) ------------------------


def _require_story(db, story_id: int) -> Story:
    row = db.get(Story, story_id)
    if row is None:
        raise NotFoundError("Story", story_id)
    return row


def add_character(story_id: int, **fields) -> StoryCharacter:
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        row = StoryCharacter(story_id=story_id, **fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_characters(story_id: int) -> list[StoryCharacter]:
    db = SessionLocal()
    try:
        rows = db.query(StoryCharacter).filter(StoryCharacter.story_id == story_id).order_by(StoryCharacter.id).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_character(character_id: int, **fields) -> StoryCharacter:
    db = SessionLocal()
    try:
        row = db.get(StoryCharacter, character_id)
        if row is None:
            raise NotFoundError("StoryCharacter", character_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_character(character_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryCharacter, character_id)
        if row is None:
            raise NotFoundError("StoryCharacter", character_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


def add_location(story_id: int, **fields) -> StoryLocation:
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        row = StoryLocation(story_id=story_id, **fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_locations(story_id: int) -> list[StoryLocation]:
    db = SessionLocal()
    try:
        rows = db.query(StoryLocation).filter(StoryLocation.story_id == story_id).order_by(StoryLocation.id).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_location(location_id: int, **fields) -> StoryLocation:
    db = SessionLocal()
    try:
        row = db.get(StoryLocation, location_id)
        if row is None:
            raise NotFoundError("StoryLocation", location_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_location(location_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryLocation, location_id)
        if row is None:
            raise NotFoundError("StoryLocation", location_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


# -- Chapter / Scene -------------------------------------------------


def add_chapter(story_id: int, **fields) -> StoryChapter:
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        row = StoryChapter(story_id=story_id, **fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_chapters(story_id: int) -> list[StoryChapter]:
    db = SessionLocal()
    try:
        rows = db.query(StoryChapter).filter(StoryChapter.story_id == story_id).order_by(StoryChapter.order).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_chapter(chapter_id: int, **fields) -> StoryChapter:
    db = SessionLocal()
    try:
        row = db.get(StoryChapter, chapter_id)
        if row is None:
            raise NotFoundError("StoryChapter", chapter_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_chapter(chapter_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryChapter, chapter_id)
        if row is None:
            raise NotFoundError("StoryChapter", chapter_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


def add_scene(chapter_id: int, **fields) -> StoryScene:
    db = SessionLocal()
    try:
        if db.get(StoryChapter, chapter_id) is None:
            raise NotFoundError("StoryChapter", chapter_id)
        row = StoryScene(chapter_id=chapter_id, **fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_scenes(chapter_id: int) -> list[StoryScene]:
    db = SessionLocal()
    try:
        rows = db.query(StoryScene).filter(StoryScene.chapter_id == chapter_id).order_by(StoryScene.order).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def update_scene(scene_id: int, **fields) -> StoryScene:
    db = SessionLocal()
    try:
        row = db.get(StoryScene, scene_id)
        if row is None:
            raise NotFoundError("StoryScene", scene_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_scene(scene_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryScene, scene_id)
        if row is None:
            raise NotFoundError("StoryScene", scene_id)
        db.delete(row)
        db.commit()
    finally:
        db.close()


def get_chapters_with_scenes(story_id: int) -> list[tuple[StoryChapter, list[StoryScene]]]:
    """Every chapter of a story with its scenes, both in `order`, resolved in
    one session -- the read the Phase 3 story pipeline (scene classification +
    cost estimate) needs. Detached rows.
    """
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        chapters = (
            db.query(StoryChapter)
            .filter(StoryChapter.story_id == story_id)
            .order_by(StoryChapter.order)
            .all()
        )
        out: list[tuple[StoryChapter, list[StoryScene]]] = []
        for chap in chapters:
            scenes = (
                db.query(StoryScene)
                .filter(StoryScene.chapter_id == chap.id)
                .order_by(StoryScene.order)
                .all()
            )
            out.append((chap, scenes))
        db.expunge_all()
        return out
    finally:
        db.close()


def apply_scene_updates(updates: dict[int, dict]) -> int:
    """Write per-scene field patches for many scenes in one transaction --
    used by the Scene Director stage to persist scores + visual_mode. Silently
    skips a scene id that no longer exists (a concurrent delete is harmless
    here). Returns the number of rows updated.
    """
    if not updates:
        return 0
    db = SessionLocal()
    try:
        n = 0
        for scene_id, fields in updates.items():
            row = db.get(StoryScene, scene_id)
            if row is None:
                continue
            for k, v in fields.items():
                setattr(row, k, v)
            n += 1
        db.commit()
        return n
    finally:
        db.close()


# -- Idempotent bulk creates for the planning pipeline (Phase 4) --------
#
# A stage checks "does this story already have characters/chapters/scenes"
# and only calls these when it doesn't -- the same reuse-before-regenerate
# idempotency app.api.v1.endpoints.factory_stages established for beats.


def bulk_add_characters(story_id: int, rows: list[dict]) -> list[StoryCharacter]:
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        created = [StoryCharacter(story_id=story_id, **r) for r in rows]
        db.add_all(created)
        db.commit()
        for c in created:
            db.refresh(c)
        db.expunge_all()
        return created
    finally:
        db.close()


def bulk_add_chapters(story_id: int, rows: list[dict]) -> list[StoryChapter]:
    db = SessionLocal()
    try:
        _require_story(db, story_id)
        created = [StoryChapter(story_id=story_id, **r) for r in rows]
        db.add_all(created)
        db.commit()
        for c in created:
            db.refresh(c)
        db.expunge_all()
        return created
    finally:
        db.close()


def bulk_add_scenes(chapter_id: int, rows: list[dict]) -> list[StoryScene]:
    db = SessionLocal()
    try:
        if db.get(StoryChapter, chapter_id) is None:
            raise NotFoundError("StoryChapter", chapter_id)
        created = [StoryScene(chapter_id=chapter_id, **r) for r in rows]
        db.add_all(created)
        db.commit()
        for s in created:
            db.refresh(s)
        db.expunge_all()
        return created
    finally:
        db.close()


def set_chapter_compiled_project(chapter_id: int, project_id: int | None) -> None:
    db = SessionLocal()
    try:
        row = db.get(StoryChapter, chapter_id)
        if row is None:
            raise NotFoundError("StoryChapter", chapter_id)
        row.compiled_project_id = project_id
        db.commit()
    finally:
        db.close()


def set_episode_compiled_projects(episode_id: int, project_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        row = db.get(Episode, episode_id)
        if row is None:
            raise NotFoundError("Episode", episode_id)
        row.compiled_project_ids_json = list(project_ids)
        db.commit()
    finally:
        db.close()


def merge_story_json(story_id: int, *, story_bible: dict | None = None, style_bible: dict | None = None) -> None:
    """Shallow-merge new keys into story_bible_json / style_bible_json
    without dropping keys an earlier stage already wrote.
    """
    db = SessionLocal()
    try:
        row = db.get(Story, story_id)
        if row is None:
            raise NotFoundError("Story", story_id)
        if story_bible:
            row.story_bible_json = {**(row.story_bible_json or {}), **story_bible}
        if style_bible:
            row.style_bible_json = {**(row.style_bible_json or {}), **style_bible}
        db.commit()
    finally:
        db.close()


# -- StoryRun / StoryCheckpoint --------------------------------------------
#
# A 1:1 mirror of app.modules.factory.service's run + checkpoint helpers
# (same "SessionLocal per call, called from a background thread" shape).


def get_run(run_id: int) -> StoryRun | None:
    db = SessionLocal()
    try:
        row = db.get(StoryRun, run_id)
        if row is not None:
            db.expunge(row)
        return row
    finally:
        db.close()


def list_runs_for_story(story_id: int) -> list[StoryRun]:
    db = SessionLocal()
    try:
        rows = db.query(StoryRun).filter(StoryRun.story_id == story_id).order_by(StoryRun.id.desc()).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def get_checkpoints(run_id: int) -> list[StoryCheckpoint]:
    db = SessionLocal()
    try:
        rows = db.query(StoryCheckpoint).filter(StoryCheckpoint.story_run_id == run_id).order_by(StoryCheckpoint.id).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def list_active_runs() -> list[StoryRun]:
    db = SessionLocal()
    try:
        rows = db.query(StoryRun).filter(StoryRun.status.in_(STORY_RUN_ACTIVE_STATUSES)).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def reconcile_story_runs_on_startup() -> int:
    """Any StoryRun left in an active status when the process died can only
    mean the previous process crashed mid-run -- mark it FAILED so the UI
    can show a Retry (mirrors factory_pipeline.reconcile_factory_runs_on_startup).
    Phase 1: there is no pipeline yet, so this is a no-op in practice, but
    the hook is wired now so Phase 2 doesn't have to touch main.py again.
    """
    reconciled = 0
    db = SessionLocal()
    try:
        for run in db.query(StoryRun).filter(StoryRun.status.in_(STORY_RUN_ACTIVE_STATUSES)).all():
            stuck_stage = run.status if run.status in STORY_RUN_STAGES else run.failed_stage
            run.failed_stage = stuck_stage  # remember where it was, before overwriting
            run.status = "FAILED"
            run.error_code = "STORY_RUN_INTERRUPTED"
            run.error_message = "The application restarted while this run was active."
            run.completed_at = _utcnow()
            for cp in db.query(StoryCheckpoint).filter(
                StoryCheckpoint.story_run_id == run.id, StoryCheckpoint.status == CHECKPOINT_RUNNING
            ).all():
                cp.status = CHECKPOINT_FAILED
                cp.completed_at = _utcnow()
                cp.error_code = "STORY_RUN_INTERRUPTED"
                cp.error_message = "The application restarted while this stage was running."
            reconciled += 1
        db.commit()
    finally:
        db.close()
    return reconciled


def get_active_run_for_story(story_id: int) -> StoryRun | None:
    db = SessionLocal()
    try:
        run = (
            db.query(StoryRun)
            .filter(StoryRun.story_id == story_id, StoryRun.status.in_(STORY_RUN_ACTIVE_STATUSES))
            .order_by(StoryRun.id.desc())
            .first()
        )
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def get_latest_run_for_story(story_id: int) -> StoryRun | None:
    db = SessionLocal()
    try:
        run = db.query(StoryRun).filter(StoryRun.story_id == story_id).order_by(StoryRun.id.desc()).first()
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def create_run(story_id: int, scope: str = "STORY_PLAN") -> tuple[StoryRun, bool]:
    """New run, or the story's already-active one unchanged. `created` tells
    the caller whether it needs to spawn a background execution thread
    (never a second one alongside an existing active run).
    """
    with _create_lock:
        existing = get_active_run_for_story(story_id)
        if existing is not None:
            return existing, False
        db = SessionLocal()
        try:
            if db.get(Story, story_id) is None:
                raise NotFoundError("Story", story_id)
            run = StoryRun(story_id=story_id, scope=scope, status="DRAFT", started_at=_utcnow(), stage_metrics_json={})
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
        run = db.get(StoryRun, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)
        db.commit()
    finally:
        db.close()


def merge_stage_metrics(run_id: int, **timings: float) -> None:
    db = SessionLocal()
    try:
        run = db.get(StoryRun, run_id)
        if run is None:
            return
        run.stage_metrics_json = {**(run.stage_metrics_json or {}), **timings}
        db.commit()
    finally:
        db.close()


def increment_attempt(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(StoryRun, run_id)
        if run is None:
            return
        run.attempt = (run.attempt or 1) + 1
        db.commit()
    finally:
        db.close()


def _get_checkpoint(db, run_id: int, stage: str) -> StoryCheckpoint | None:
    return (
        db.query(StoryCheckpoint)
        .filter(StoryCheckpoint.story_run_id == run_id, StoryCheckpoint.stage == stage)
        .first()
    )


def start_checkpoint(run_id: int, stage: str) -> StoryCheckpoint:
    db = SessionLocal()
    try:
        now = _utcnow()
        cp = _get_checkpoint(db, run_id, stage)
        if cp is None:
            cp = StoryCheckpoint(story_run_id=run_id, stage=stage, status=CHECKPOINT_RUNNING, attempt=1, started_at=now)
            db.add(cp)
        else:
            cp.attempt = (cp.attempt or 1) + 1
            cp.status = CHECKPOINT_RUNNING
            cp.started_at = now
            cp.completed_at = None
            cp.error_code = None
            cp.error_message = None
        db.commit()
        db.refresh(cp)
        db.expunge(cp)
        return cp
    finally:
        db.close()


def complete_checkpoint(run_id: int, stage: str, metadata: dict | None = None) -> None:
    db = SessionLocal()
    try:
        cp = _get_checkpoint(db, run_id, stage)
        if cp is None:
            cp = StoryCheckpoint(story_run_id=run_id, stage=stage, attempt=1, started_at=_utcnow())
            db.add(cp)
        cp.status = CHECKPOINT_COMPLETED
        cp.completed_at = _utcnow()
        if metadata is not None:
            cp.checkpoint_metadata_json = metadata
        db.commit()
    finally:
        db.close()


def skip_checkpoint(run_id: int, stage: str, metadata: dict | None = None) -> None:
    db = SessionLocal()
    try:
        cp = _get_checkpoint(db, run_id, stage)
        now = _utcnow()
        if cp is None:
            cp = StoryCheckpoint(story_run_id=run_id, stage=stage, attempt=1, started_at=now)
            db.add(cp)
        cp.status = CHECKPOINT_SKIPPED
        cp.completed_at = now
        if metadata is not None:
            cp.checkpoint_metadata_json = metadata
        db.commit()
    finally:
        db.close()


def fail_checkpoint(run_id: int, stage: str, error_code: str, error_message: str) -> None:
    db = SessionLocal()
    try:
        cp = _get_checkpoint(db, run_id, stage)
        if cp is None:
            cp = StoryCheckpoint(story_run_id=run_id, stage=stage, attempt=1, started_at=_utcnow())
            db.add(cp)
        cp.status = CHECKPOINT_FAILED
        cp.completed_at = _utcnow()
        cp.error_code = error_code
        cp.error_message = error_message
        db.commit()
    finally:
        db.close()


def force_checkpoint_status(
    run_id: int, stage: str, status: str, error_code: str | None = None, error_message: str | None = None
) -> None:
    db = SessionLocal()
    try:
        cp = _get_checkpoint(db, run_id, stage)
        now = _utcnow()
        if cp is None:
            cp = StoryCheckpoint(story_run_id=run_id, stage=stage, attempt=1, started_at=now)
            db.add(cp)
        cp.status = status
        cp.completed_at = now
        cp.error_code = error_code
        cp.error_message = error_message
        db.commit()
    finally:
        db.close()


def mark_run_failed(run_id: int, stage: str, code: str, message: str) -> None:
    """Single funnel for every failure path -- settles StoryRun and the
    stage's StoryCheckpoint together (mirrors factory_stages._mark_failed).
    """
    set_run_fields(
        run_id, status="FAILED", failed_stage=stage, error_code=code, error_message=message, completed_at=_utcnow(),
    )
    if stage in STORY_RUN_STAGES:
        fail_checkpoint(run_id, stage, code, message)
