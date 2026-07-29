import threading
import time
from pathlib import Path

import httpx

from app.services.download.downloader import (
    Downloader,
    DownloadCancelled,
    DownloadPaused,
    ProgressCallback,
)

CHUNK_SIZE = 64 * 1024
PROGRESS_INTERVAL_SEC = 0.2


def _resolve_total_bytes(response: httpx.Response, resume_from: int) -> int | None:
    content_range = response.headers.get("Content-Range")
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total.isdigit():
            return int(total)

    content_length = response.headers.get("Content-Length")
    if content_length is not None and content_length.isdigit():
        return resume_from + int(content_length)

    return None


class HttpDownloader(Downloader):
    """Downloads a direct file URL over HTTP(S), resuming via Range requests
    when the server supports it. Falls back to a full restart otherwise.
    """

    def __init__(self, timeout_sec: float = 30.0, chunk_size: int = CHUNK_SIZE, throttle_sec_per_chunk: float = 0.0):
        self._timeout_sec = timeout_sec
        self._chunk_size = chunk_size
        self._throttle_sec_per_chunk = throttle_sec_per_chunk

    def download(
        self,
        url: str,
        destination: Path,
        resume_from: int,
        cancel_event: threading.Event,
        pause_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)

        headers = {}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=self._timeout_sec) as response:
            if response.status_code == 416:
                # Requested range not satisfiable: the file on disk is already complete.
                on_progress(resume_from, resume_from, 0.0)
                return

            resumed = resume_from > 0 and response.status_code == 206
            write_mode = "ab" if resumed else "wb"
            effective_resume = resume_from if resumed else 0

            response.raise_for_status()
            total_bytes = _resolve_total_bytes(response, effective_resume)

            downloaded = effective_resume
            start_time = time.monotonic()
            last_report = 0.0

            with open(destination, write_mode) as f:
                for chunk in response.iter_bytes(chunk_size=self._chunk_size):
                    if cancel_event.is_set():
                        raise DownloadCancelled()
                    if pause_event.is_set():
                        raise DownloadPaused()

                    f.write(chunk)
                    downloaded += len(chunk)

                    if self._throttle_sec_per_chunk:
                        time.sleep(self._throttle_sec_per_chunk)

                    now = time.monotonic()
                    if now - last_report >= PROGRESS_INTERVAL_SEC:
                        elapsed = now - start_time
                        speed = (downloaded - effective_resume) / elapsed if elapsed > 0 else 0.0
                        on_progress(downloaded, total_bytes, speed)
                        last_report = now

            elapsed = time.monotonic() - start_time
            speed = (downloaded - effective_resume) / elapsed if elapsed > 0 else 0.0
            on_progress(downloaded, total_bytes, speed)
