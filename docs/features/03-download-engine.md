# 03 — Download Engine

**Commit:** `84d9194` "Add background Download Engine (queue, pause/resume/retry/cancel, parallel)"

## What it does

A background job engine that downloads files without blocking the API:
queue, pause, resume, retry, cancel, parallel workers, and live
progress/speed/ETA -- all running on OS threads separate from the FastAPI
event loop.

## Key files

- `app/services/download/downloader.py` — the `Downloader` interface
  (pluggable backend) plus `DownloadPaused`/`DownloadCancelled` signal
  exceptions
- `app/services/download/http_downloader.py` — the original implementation:
  plain HTTP with Range-request resume (superseded as the default by
  `YtdlpDownloader`, see [07](07-detection-download-ytdlp.md), but still the
  interface's reference implementation)
- `app/services/download/engine.py` — `DownloadEngine`: a `queue.Queue` +
  N worker threads (`max_concurrent_downloads`), one `threading.Event` pair
  (pause/cancel) per active task

## How it works

- `enqueue(url, video_id)` creates a `DownloadTask` row and pushes the id
  onto the queue; a free worker thread picks it up
- Pausing sets an event the `Downloader` checks between chunks/hook calls and
  raises `DownloadPaused` to unwind cleanly; the partial file and
  `downloaded_bytes` are preserved so resume continues rather than restarts
- Cancelling deletes the partial file and marks the task `cancelled`
- On process restart, `_recover_pending_tasks()` re-queues anything left
  `queued`/`downloading` from a previous run
- Progress writes to the DB are throttled (1 per 300ms) *except* the final
  write on completion, which is forced through -- otherwise a very fast/small
  download could finish before its first throttled write, leaving
  `downloaded_bytes` stuck below the real file size despite `status=completed`
  (a real bug caught during verification, since fixed)

## Verification approach

No unit test suite yet -- verified by driving the real `DownloadEngine`
against a local Range-supporting HTTP test server (Python's `http.server`
doesn't support Range out of the box; a minimal handler was written for
testing), asserting on actual byte offsets across pause/resume, real file
deletion on cancel, and `max_concurrent` never being exceeded under load.
