"""Background asset import (Task 15 -- see
docs/features/41-local-asset-ingestion.md). One on-demand background
thread per import/rescan run, spawned exactly like
app.modules.batch.batch_render's beat-generation thread (Task 13) -- not a
second general-purpose queue/worker *service* like VideoComposerService's,
since there's nothing here that benefits from a persistent worker (no
external resource to serialize access to, just local file I/O that's fine
to run once per request). Uses SessionLocal directly (its own session per
call/run), the same "background-thread-compatible" pattern
app.modules.beat.project_service and app.modules.batch.service already use.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.asset.ingest import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    classify_orientation,
    classify_portrait_suitability,
    compute_file_hash,
    extract_audio_metadata,
    extract_image_metadata,
    extract_video_metadata,
    folder_tags_from_path,
    generate_image_thumbnail,
    generate_video_thumbnail,
    infer_category,
    infer_emotion,
    tokenize_filename,
)
from app.modules.asset.models import Asset, AssetImportJob
from app.modules.asset.service import _normalize_tags

logger = logging.getLogger(__name__)

# Commit periodically, not once per 10,000-file import and not once per
# single file either (section 29: "do NOT wrap an entire import in one huge
# transaction... use reasonable batches"). Small enough that a poller (see
# router.py's GET /assets/import/{job_id}) sees real, moving progress every
# couple of seconds even on a fast local disk.
_PROGRESS_COMMIT_INTERVAL = 10

# In-memory cancel signal, checked instead of (not just in addition to) a
# DB read -- same reason app.modules.video_composer.service keeps its own
# _cancel_events dict rather than re-querying the DB from inside a
# long-running job: the import thread's session can sit inside one open
# SQLite transaction across many files between periodic commits (see
# _PROGRESS_COMMIT_INTERVAL above), and a plain SELECT from within that
# transaction is not guaranteed to observe another session's *own* commit
# of `cancel_requested` until this transaction itself ends -- an in-memory
# threading.Event has no such staleness window. cancel_import_job still
# also persists cancel_requested on the row, purely for API/DB visibility.
_CANCEL_EVENTS: dict[int, threading.Event] = {}


def _thumbnails_dir(library_dir: Path) -> Path:
    return library_dir / "_asset" / "thumbnails"


def _discover_folder_files(folder: Path, recursive: bool) -> list[Path]:
    if not folder.is_dir():
        raise ValidationError(f"Not a folder: {folder}")
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in folder.glob(pattern) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def create_import_job(paths: list[str] | None = None, folder: str | None = None, recursive: bool = True) -> int:
    """Discovers the file list up front (so `total_files` in the returned
    job is real, not a guess -- section 26: "do not fake percentages") and
    persists a QUEUED AssetImportJob. Does not itself process anything --
    call start_import_job_in_background() to actually run it.
    """
    if not paths and not folder:
        raise ValidationError("Provide either a list of file paths or a folder to import.")

    import_root: str | None = None
    if folder:
        folder_path = Path(folder).expanduser()
        files = _discover_folder_files(folder_path, recursive)
        source_label = str(folder_path)
        import_root = str(folder_path)
    else:
        files = [Path(p).expanduser() for p in paths]
        source_label = f"{len(files)} file{'s' if len(files) != 1 else ''}"

    if not files:
        raise ValidationError("No supported media files were found to import.")

    db = SessionLocal()
    try:
        job = AssetImportJob(
            status="QUEUED", source_label=source_label, import_root=import_root, total_files=len(files)
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    # The discovered file list itself is only needed by this one run, not
    # persisted on the job row (which is a progress/report summary, not a
    # file manifest) -- stashed in-memory against the job id for the
    # background thread to pick up.
    _PENDING_FILE_LISTS[job_id] = files
    return job_id


_PENDING_FILE_LISTS: dict[int, list[Path]] = {}


def start_import_job_in_background(job_id: int, library_dir: Path) -> None:
    _CANCEL_EVENTS[job_id] = threading.Event()
    thread = threading.Thread(target=_run_import, args=(job_id, library_dir), daemon=True)
    thread.start()


def _is_cancelled(job_id: int) -> bool:
    event = _CANCEL_EVENTS.get(job_id)
    return event is not None and event.is_set()


def _process_one_file(db, path: Path, import_root: Path | None, thumbnails_dir: Path) -> str:
    """Returns "imported" | "duplicate". Raises FileOperationError/
    ValidationError on anything that should count as "failed" -- the caller
    catches and records the reason (section 30: one corrupt file must not
    stop the rest of the import).
    """
    if not path.is_file():
        raise ValidationError(f"File not found: {path}")

    extension = path.suffix.lower()
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        asset_type = "image"
    elif extension in SUPPORTED_VIDEO_EXTENSIONS:
        asset_type = "video"
    elif extension in SUPPORTED_AUDIO_EXTENSIONS:
        asset_type = "audio"
    else:
        raise ValidationError(f"Unsupported file type: {extension or '(no extension)'}")

    resolved_path = path.expanduser().resolve()
    content_hash = compute_file_hash(resolved_path)

    existing = db.query(Asset).filter(Asset.content_hash == content_hash).first()
    if existing is not None:
        return "duplicate"
    # A file registered before Task 15 (no content_hash yet) or via the
    # plain POST /assets endpoint could still be the exact same path --
    # the existing unique(path) constraint already guards that case, caught
    # as an IntegrityError below rather than duplicated here.

    if asset_type == "image":
        metadata = extract_image_metadata(resolved_path)
        width, height, duration_sec = metadata.width, metadata.height, None
        orientation = metadata.orientation
    elif asset_type == "video":
        metadata = extract_video_metadata(resolved_path)
        width, height, duration_sec = metadata.width, metadata.height, metadata.duration_sec
        orientation = classify_orientation(width, height) if width and height else None
    else:
        audio_metadata = extract_audio_metadata(resolved_path)
        width, height, duration_sec = None, None, audio_metadata.duration_sec
        orientation = None

    filename_tokens = tokenize_filename(path.name)
    folder_tags = folder_tags_from_path(resolved_path, import_root) if import_root else []
    combined_tags = _normalize_tags([*filename_tokens, *folder_tags])
    all_tokens = [*filename_tokens, *folder_tags]

    asset = Asset(
        filename=path.name,
        path=str(resolved_path),
        type=asset_type,
        width=width,
        height=height,
        duration_sec=duration_sec,
        filesize_bytes=resolved_path.stat().st_size,
        tags=combined_tags,
        source="LOCAL_IMPORT",
        source_ref=str(import_root) if import_root else None,
        content_hash=content_hash,
        orientation=orientation,
        category=infer_category(all_tokens),
        emotion=infer_emotion(all_tokens),
        status="ACTIVE",
    )
    try:
        # A SAVEPOINT (not the outer transaction) -- db.rollback() would
        # undo *every* row flushed earlier in this batch, not just this
        # one file's insert, since batching means many files share one
        # open transaction between commits (see _run_import). begin_nested()
        # scopes the rollback to exactly this file's own attempted insert.
        with db.begin_nested():
            db.add(asset)
            db.flush()  # assigns asset.id without ending the outer batch transaction
    except IntegrityError:
        # Same physical path already registered (e.g. via the old bare
        # POST /assets, before it had a content_hash) -- exact-content
        # duplicate in every way that matters, just detected by path
        # instead of hash this one time.
        return "duplicate"

    if asset_type == "audio":
        # No thumbnail for audio -- AssetLibraryPage's own AssetTile already
        # renders a dedicated Music icon whenever thumbnail_path is unset
        # (see frontend/src/pages/AssetLibraryPage.tsx), matching every
        # audio row this app has ever registered (voice_generate.py/
        # audio_generate.py's narration/audio_master rows never set one
        # either).
        return "imported"

    thumbnail_dest = thumbnails_dir / f"{asset.id}.jpg"
    try:
        if asset_type == "image":
            generate_image_thumbnail(resolved_path, thumbnail_dest)
        else:
            generate_video_thumbnail(resolved_path, thumbnail_dest)
        asset.thumbnail_path = str(thumbnail_dest)
    except Exception:
        # A missing/failed thumbnail is a cosmetic degradation, not a
        # reason to fail the whole asset -- the file itself is valid (we
        # already successfully extracted its metadata above).
        logger.warning("Thumbnail generation failed for asset %s (%s)", asset.id, resolved_path, exc_info=True)

    return "imported"


def _run_import(job_id: int, library_dir: Path) -> None:
    files = _PENDING_FILE_LISTS.pop(job_id, [])
    thumbnails_dir = _thumbnails_dir(library_dir)
    start = time.monotonic()

    db = SessionLocal()
    try:
        job = db.get(AssetImportJob, job_id)
        if job is None:
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        import_root = Path(job.import_root) if job.import_root else None
        failed_files: list[dict] = []
        cancelled = False

        for index, path in enumerate(files, start=1):
            if _is_cancelled(job_id):
                cancelled = True
                break

            job.current_file = str(path)
            try:
                outcome = _process_one_file(db, path, import_root, thumbnails_dir)
                if outcome == "imported":
                    job.imported_count += 1
                else:
                    job.duplicate_count += 1
            except Exception as exc:
                # No db.rollback() here -- everything up to this point in
                # _process_one_file (hashing, dedup lookup, metadata
                # extraction) is pure file I/O/read-only queries that never
                # dirty the session, and the one real write (the Asset
                # insert) is already scoped to its own SAVEPOINT above, so
                # a failure here has nothing of *this batch's* earlier,
                # still-uncommitted work to undo.
                job.failed_count += 1
                failed_files.append({"path": str(path), "reason": str(exc)})
                logger.info("Asset import failed for %s: %s", path, exc)

            job.processed_files = index
            job.failed_files = failed_files
            if index % _PROGRESS_COMMIT_INTERVAL == 0:
                db.commit()

        job.failed_files = failed_files
        job.status = "CANCELLED" if cancelled else "COMPLETED"
        if cancelled:
            # This thread already holds the write lock right here, so it's
            # the one that actually persists cancel_requested -- see
            # cancel_import_job's own docstring for why the request path
            # itself never tries to write this.
            job.cancel_requested = True
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = time.monotonic() - start
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Asset import job %s crashed", job_id)
        job = db.get(AssetImportJob, job_id)
        if job is not None:
            job.status = "FAILED"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
        _CANCEL_EVENTS.pop(job_id, None)


def get_import_job(job_id: int) -> AssetImportJob:
    db = SessionLocal()
    try:
        job = db.get(AssetImportJob, job_id)
        if job is None:
            raise NotFoundError("AssetImportJob", job_id)
        db.expunge(job)
        return job
    finally:
        db.close()


def cancel_import_job(job_id: int) -> AssetImportJob:
    """Deliberately does *not* write `cancel_requested` to the row here --
    the background thread can be mid-batch holding SQLite's single writer
    lock for up to _PROGRESS_COMMIT_INTERVAL files (see that constant's own
    comment), so a `db.commit()` on this request's connection would block
    until that lock frees up, defeating the whole point of a responsive
    Cancel button. Setting the in-memory event is immediate and lock-free;
    the background thread persists cancel_requested itself, at the exact
    moment it already holds the write lock to record status=CANCELLED
    (see _run_import).
    """
    db = SessionLocal()
    try:
        job = db.get(AssetImportJob, job_id)
        if job is None:
            raise NotFoundError("AssetImportJob", job_id)
        if job.status in ("QUEUED", "RUNNING"):
            event = _CANCEL_EVENTS.get(job_id)
            if event is not None:
                event.set()
        db.expunge(job)
        return job
    finally:
        db.close()


def rescan_library(library_dir: Path) -> dict:
    """Section 25: finds newly-missing files and re-validates previously
    MISSING/INVALID/never-checked ones -- never blindly re-processes every
    already-ACTIVE asset (that would be "re-import everything blindly",
    which section 25 explicitly rules out). A file that comes back after
    being missing gets its metadata refreshed, since it may have been
    replaced by a different file at the same path in the meantime.
    """
    thumbnails_dir = _thumbnails_dir(library_dir)
    counts = {"checked": 0, "now_missing": 0, "now_active": 0, "now_invalid": 0, "unchanged": 0}

    db = SessionLocal()
    try:
        assets = db.query(Asset).all()
        for asset in assets:
            counts["checked"] += 1
            path = Path(asset.path)

            if not path.is_file():
                if asset.status != "MISSING":
                    asset.status = "MISSING"
                    counts["now_missing"] += 1
                else:
                    counts["unchanged"] += 1
                continue

            if asset.status == "ACTIVE":
                counts["unchanged"] += 1
                continue

            # status is MISSING, INVALID, or never set (None -- an asset
            # registered before Task 15 or through the plain POST /assets
            # endpoint) but the file exists right now -- worth a real
            # re-check, never skipped just because it's "probably fine."
            try:
                if asset.type == "image":
                    metadata = extract_image_metadata(path)
                    asset.width, asset.height = metadata.width, metadata.height
                    asset.orientation = metadata.orientation
                elif asset.type == "video":
                    metadata = extract_video_metadata(path)
                    asset.width, asset.height, asset.duration_sec = metadata.width, metadata.height, metadata.duration_sec
                # else: audio (or any other type ingestion doesn't cover --
                # see ingest.py's own module docstring on scope) has no
                # width/height/duration re-probe here; existing on disk is
                # the only thing this task's re-scan claims to verify for
                # a type it was never asked to extract metadata for in the
                # first place (section 4's own image/video-only scope).
                asset.filesize_bytes = path.stat().st_size
                if not asset.content_hash:
                    asset.content_hash = compute_file_hash(path)
                asset.status = "ACTIVE"
                if asset.type in ("image", "video") and (
                    not asset.thumbnail_path or not Path(asset.thumbnail_path).exists()
                ):
                    thumbnail_dest = thumbnails_dir / f"{asset.id}.jpg"
                    if asset.type == "image":
                        generate_image_thumbnail(path, thumbnail_dest)
                    else:
                        generate_video_thumbnail(path, thumbnail_dest)
                    asset.thumbnail_path = str(thumbnail_dest)
                counts["now_active"] += 1
            except Exception:
                asset.status = "INVALID"
                counts["now_invalid"] += 1

        db.commit()
    finally:
        db.close()

    return counts


__all__ = [
    "create_import_job",
    "start_import_job_in_background",
    "get_import_job",
    "cancel_import_job",
    "rescan_library",
    "classify_portrait_suitability",
]
