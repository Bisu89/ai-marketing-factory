"""On-demand background video sync -- one thread per run, exactly the
lightweight shape app.modules.asset.import_service uses (see that module's
own docstring: "nothing here that benefits from a persistent worker, no
external resource to serialize access to beyond simple rate limiting").
Not a persistent queue/pool -- a sync is a short, bounded, on-demand pull
of the connected account's own video list.
"""

import logging
import threading
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.modules.competitor_intelligence import service, tiktok_client
from app.modules.competitor_intelligence.models import TikTokAccountLink

logger = logging.getLogger(__name__)

# One sync at a time per account -- a second "Sync now" click while one is
# already running is a no-op (see is_syncing), not a queued second run.
_SYNCING: set[int] = set()
_syncing_lock = threading.Lock()


def is_syncing(account_link_id: int) -> bool:
    with _syncing_lock:
        return account_link_id in _SYNCING


def start_sync_in_background(account_link_id: int, client_key: str, client_secret: str) -> bool:
    with _syncing_lock:
        if account_link_id in _SYNCING:
            return False
        _SYNCING.add(account_link_id)
    thread = threading.Thread(target=_run_sync, args=(account_link_id, client_key, client_secret), daemon=True)
    thread.start()
    return True


def _run_sync(account_link_id: int, client_key: str, client_secret: str) -> None:
    db = SessionLocal()
    try:
        account = db.get(TikTokAccountLink, account_link_id)
        if account is None:
            return
        try:
            access_token = service.get_valid_access_token(db, account, client_key, client_secret)
        except Exception:
            logger.exception("TikTok token refresh failed during sync for account %s", account_link_id)
            return

        cursor: int | None = None
        total_synced = 0
        for _ in range(20):  # hard cap -- never an unbounded loop even if has_more never clears
            page = tiktok_client.fetch_video_list(access_token, cursor=cursor, max_count=20)
            videos = page.get("videos", [])
            if videos:
                total_synced += service.upsert_videos(db, account_link_id, videos)
            if not page.get("has_more"):
                break
            cursor = page.get("cursor")

        account = db.get(TikTokAccountLink, account_link_id)
        if account is not None:
            account.last_synced_at = datetime.now(timezone.utc)
            db.commit()
        logger.info("TikTok sync finished for account %s: %d videos", account_link_id, total_synced)
    except Exception:
        logger.exception("TikTok sync failed for account %s", account_link_id)
    finally:
        db.close()
        with _syncing_lock:
            _SYNCING.discard(account_link_id)
