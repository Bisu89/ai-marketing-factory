"""Reclaim disk from the per-beat intermediate artifacts the Factory
pipeline registers as ordinary Assets -- the `voice_factory` narration
segments (`_voice/project_<id>/beat_*.wav`, Task 22) and `motion_engine`
clips (`_motion/project_<id>/beat_*.mp4`, Task 23). One set per project,
so a channel with hundreds of finished videos ends up with thousands of
these rows cluttering the Asset Library and their files eating disk, even
though every one of them is a deterministic, regenerable cache -- the
Voice / Motion / Audio stages rebuild whatever is missing on the next
render (see each stage's own "reuse a valid cached artifact ... regenerate
whenever it doesn't match" contract).

Two entry points, one core (`perform_cleanup`):
- `POST /assets/cleanup-generated` -- on demand, from the Asset Library UI.
- `sweep_stale_render_cache` -- the age-gated automatic sweep run at
  startup + every 24h (see app/main.py), controlled by
  `settings.render_cache_retention_days` (0 = off).

Composition root (same shape as produced_videos.py / dashboard.py): reads
app.modules.asset (Asset), app.modules.beat (Project), app.modules.batch
(BatchItem) and app.modules.video_composer (VideoComposeJob) -- none of
which import each other -- and joins them here. Only ever touches a
project whose render is genuinely finished (>=1 COMPLETED render job, no
QUEUED/RUNNING one), so it can never delete a file out from under an
active or not-yet-run render. Never touches a user's own imported media
(`source="LOCAL_IMPORT"` etc.) -- only the pipeline's own generated
sources below.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.session import SessionLocal, get_db
from app.modules.asset.models import Asset
from app.modules.batch.models import BatchItem
from app.modules.beat.models import Project
from app.modules.video_composer.models import COARSE_STATUS, VideoComposeJob

logger = logging.getLogger(__name__)
router = APIRouter()

# The `Asset.source` values the Factory pipeline stamps on its own
# per-beat intermediates (see voice_generate.py / motion_generate.py /
# imagegen_generate.py). `ai_image_generator` is deliberately NOT in the
# default set -- an AI image costs real money and, unlike the deterministic
# voice/motion passes, regenerates to a *different* image -- but is allowed
# if a caller explicitly asks for it.
GENERATED_SOURCES = ("voice_factory", "motion_engine", "ai_image_generator")
DEFAULT_SOURCES = ("voice_factory", "motion_engine")

# Per-project cache directories under library_dir/. When delete_files is
# set and a project is eligible, the whole directory is removed (its
# unregistered sidecars -- narration.wav, *.meta.json, audio_master.wav --
# are regenerable too), not just the files that had Asset rows. _imagegen
# is only swept when `ai_image_generator` is explicitly in `sources`.
_CACHE_SUBDIRS = ("_voice", "_motion", "_audio")
_AI_IMAGE_SUBDIR = "_imagegen"

_PROJECT_DIR_RE = re.compile(
    r"[/\\]_(?:voice|motion|audio|imagegen)[/\\]project_(\d+)[/\\]", re.IGNORECASE
)


class CleanupGeneratedRequest(BaseModel):
    model_config = {"extra": "forbid"}

    sources: list[str] = Field(default_factory=lambda: list(DEFAULT_SOURCES))
    # Also unlink the files (and remove the now-regenerable per-project
    # _voice/_motion/_audio cache dirs), not just unregister the Asset
    # rows. False = DB-only, exactly like the Asset Library's own Delete.
    delete_files: bool = True
    # Report what would be cleaned without changing anything.
    dry_run: bool = False
    # Only clean projects whose render finished at least this many days
    # ago (matches the automatic sweep's own gate). None / 0 = no age gate.
    older_than_days: int | None = None


class CleanupSkipped(BaseModel):
    no_completed_render: int = 0  # project never finished a render (or never rendered at all)
    render_in_progress: int = 0   # project has a QUEUED/RUNNING render right now
    too_recent: int = 0           # finished, but within the older_than_days window
    unparseable_path: int = 0     # asset path didn't contain a project_<id> segment


class CleanupGeneratedResult(BaseModel):
    dry_run: bool
    projects_cleaned: list[int]
    assets_unregistered: int
    files_deleted: int
    bytes_freed: int
    megabytes_freed: float
    skipped: CleanupSkipped


def _eligible_project_ids(
    db: Session, completed_before: datetime | None = None
) -> tuple[set[int], set[int], set[int]]:
    """(eligible, in_progress, too_recent). A project is eligible when at
    least one of its render jobs coarse-resolves to COMPLETED and none
    resolve to QUEUED/RUNNING. When `completed_before` is given, an
    otherwise-eligible project whose most recent completion is at or after
    that cutoff (or has no recorded completion time) lands in `too_recent`
    instead. `in_progress` is the subset blocked by an active render.
    """
    job_ids_by_project: dict[int, set[int]] = {}
    for p in db.query(Project).filter(Project.render_job_id.isnot(None)).all():
        job_ids_by_project.setdefault(p.id, set()).add(p.render_job_id)
    for it in db.query(BatchItem).filter(
        BatchItem.project_id.isnot(None), BatchItem.render_job_id.isnot(None)
    ).all():
        job_ids_by_project.setdefault(it.project_id, set()).add(it.render_job_id)

    if not job_ids_by_project:
        return set(), set(), set()

    all_job_ids = {jid for ids in job_ids_by_project.values() for jid in ids}
    jobs_by_id = {
        j.id: j for j in db.query(VideoComposeJob).filter(VideoComposeJob.id.in_(all_job_ids)).all()
    }

    eligible: set[int] = set()
    in_progress: set[int] = set()
    too_recent: set[int] = set()
    for pid, jids in job_ids_by_project.items():
        jobs = [jobs_by_id[jid] for jid in jids if jid in jobs_by_id]
        statuses = {COARSE_STATUS.get(j.status, "QUEUED") for j in jobs}
        if statuses & {"QUEUED", "RUNNING"}:
            in_progress.add(pid)
            continue
        if "COMPLETED" not in statuses:
            continue
        if completed_before is not None:
            done_times = [
                _as_utc(j.completed_at)
                for j in jobs
                if COARSE_STATUS.get(j.status, "QUEUED") == "COMPLETED" and j.completed_at is not None
            ]
            if not done_times or max(done_times) >= completed_before:
                too_recent.add(pid)
                continue
        eligible.add(pid)
    return eligible, in_progress, too_recent


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _project_id_from_path(path: str) -> int | None:
    m = _PROJECT_DIR_RE.search(path)
    return int(m.group(1)) if m else None


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def perform_cleanup(
    db: Session,
    settings: Settings,
    *,
    sources: list[str],
    delete_files: bool,
    dry_run: bool,
    older_than_days: int | None = None,
) -> CleanupGeneratedResult:
    unknown = [s for s in sources if s not in GENERATED_SOURCES]
    if unknown:
        raise ValidationError(f"Unknown generated source(s) {unknown}; allowed: {list(GENERATED_SOURCES)}")
    if not sources:
        raise ValidationError("sources must not be empty")

    cutoff = None
    if older_than_days and older_than_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    eligible, in_progress, too_recent = _eligible_project_ids(db, cutoff)

    assets = db.query(Asset).filter(Asset.source.in_(sources)).all()

    skipped = CleanupSkipped()
    to_delete: list[Asset] = []
    cleaned_projects: set[int] = set()
    for asset in assets:
        pid = _project_id_from_path(asset.path)
        if pid is None:
            skipped.unparseable_path += 1
        elif pid in in_progress:
            skipped.render_in_progress += 1
        elif pid in too_recent:
            skipped.too_recent += 1
        elif pid not in eligible:
            skipped.no_completed_render += 1
        else:
            to_delete.append(asset)
            cleaned_projects.add(pid)

    commit = not dry_run
    counted: set[Path] = set()
    bytes_freed = 0
    files_deleted = 0
    for asset in to_delete:
        file_path = Path(asset.path)
        if delete_files and file_path.is_file():
            try:
                size = file_path.stat().st_size
            except OSError:
                size = 0
            if commit:
                try:
                    file_path.unlink()
                except OSError:
                    logger.warning("cleanup-generated: could not delete %s", file_path)
                    continue
            counted.add(_safe_resolve(file_path))
            bytes_freed += size
            files_deleted += 1
        if commit:
            db.delete(asset)

    if delete_files:
        subdirs = list(_CACHE_SUBDIRS)
        if "ai_image_generator" in sources:
            subdirs.append(_AI_IMAGE_SUBDIR)
        swept_bytes, swept_files = _sweep_cache_dirs(settings, cleaned_projects, subdirs, counted, commit)
        bytes_freed += swept_bytes
        files_deleted += swept_files
    if commit:
        db.commit()

    return CleanupGeneratedResult(
        dry_run=dry_run,
        projects_cleaned=sorted(cleaned_projects),
        assets_unregistered=len(to_delete),
        files_deleted=files_deleted,
        bytes_freed=bytes_freed,
        megabytes_freed=round(bytes_freed / (1024 * 1024), 1),
        skipped=skipped,
    )


@router.post("/assets/cleanup-generated", response_model=CleanupGeneratedResult)
def cleanup_generated_assets(
    payload: CleanupGeneratedRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CleanupGeneratedResult:
    return perform_cleanup(
        db, settings,
        sources=payload.sources,
        delete_files=payload.delete_files,
        dry_run=payload.dry_run,
        older_than_days=payload.older_than_days,
    )


def sweep_stale_render_cache(settings: Settings) -> CleanupGeneratedResult | None:
    """The automatic age-gated sweep (startup + every 24h -- see
    app/main.py). No-op when `render_cache_retention_days` is 0. Never
    touches AI images. Its own DB session (runs off the request path).
    """
    days = settings.render_cache_retention_days
    if not days or days <= 0:
        return None
    db = SessionLocal()
    try:
        result = perform_cleanup(
            db, settings,
            sources=list(DEFAULT_SOURCES),
            delete_files=True,
            dry_run=False,
            older_than_days=days,
        )
    finally:
        db.close()
    if result.assets_unregistered or result.files_deleted:
        logger.info(
            "render-cache auto-sweep: freed %s MB from %d finished project(s) older than %d days",
            result.megabytes_freed, len(result.projects_cleaned), days,
        )
    return result


def _sweep_cache_dirs(
    settings: Settings, project_ids: set[int], subdirs: list[str], exclude: set[Path], commit: bool
) -> tuple[int, int]:
    """Account for (and, when commit, remove) each cleaned project's
    `subdirs` directories wholesale -- the leftover unregistered sidecars
    (narration.wav, *.meta.json, audio_master.wav) are regenerable caches
    too. Files already accounted for via their Asset row are in `exclude`
    and never double-counted. Best-effort: a dir that's already gone, or
    one that won't delete, is skipped silently. Returns (extra_bytes,
    extra_files) reclaimed beyond the registered files.
    """
    library_dir = Path(settings.library_dir)
    extra_bytes = 0
    extra_files = 0
    for pid in project_ids:
        for subdir in subdirs:
            d = library_dir / subdir / f"project_{pid}"
            if not d.is_dir():
                continue
            for f in d.rglob("*"):
                if not f.is_file() or _safe_resolve(f) in exclude:
                    continue
                try:
                    size = f.stat().st_size
                except OSError:
                    continue
                if commit:
                    try:
                        f.unlink()
                    except OSError:
                        continue
                extra_bytes += size
                extra_files += 1
            if commit:
                for sub in sorted((p for p in d.rglob("*") if p.is_dir()), reverse=True):
                    try:
                        sub.rmdir()
                    except OSError:
                        pass
                try:
                    d.rmdir()
                except OSError:
                    pass
    return extra_bytes, extra_files
