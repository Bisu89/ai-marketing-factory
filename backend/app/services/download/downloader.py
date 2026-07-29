import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol


class DownloadPaused(Exception):
    """Raised by a Downloader to signal that pause_event was set mid-download."""


class DownloadCancelled(Exception):
    """Raised by a Downloader to signal that cancel_event was set mid-download."""


class ProgressCallback(Protocol):
    def __call__(self, downloaded_bytes: int, total_bytes: int | None, speed_bps: float) -> None: ...


class Downloader(ABC):
    """Pluggable download backend. A concrete implementation (HTTP, yt-dlp, ...)
    is responsible for writing bytes to `destination`, resuming from
    `resume_from` when the file is already partially downloaded, and checking
    `cancel_event` / `pause_event` frequently enough to react within a fraction
    of a second.
    """

    @abstractmethod
    def download(
        self,
        url: str,
        destination: Path,
        resume_from: int,
        cancel_event: threading.Event,
        pause_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> None: ...
