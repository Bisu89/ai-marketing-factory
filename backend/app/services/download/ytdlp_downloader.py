import threading
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadCancelled as YtdlpStopSignal

from app.services.download.downloader import (
    Downloader,
    DownloadCancelled,
    DownloadPaused,
    ProgressCallback,
)


class YtdlpDownloader(Downloader):
    """Downloads a video via yt-dlp (YouTube, TikTok, Facebook, Instagram, ...).

    yt-dlp owns its own output filename (it needs the real extension), so this
    writes to `f"{destination}.%(ext)s"` and moves the produced file onto the
    exact `destination` path the engine expects once the download finishes --
    resume across pause/retry is handled by yt-dlp's own `.part` file under that
    same template, keyed off the deterministic per-task `destination` stem.
    """

    def __init__(self, format_selector: str = "best"):
        self._format_selector = format_selector

    def download(
        self,
        url: str,
        destination: Path,
        resume_from: int,
        cancel_event: threading.Event,
        pause_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> None:
        del resume_from  # yt-dlp resumes itself via its own .part file

        destination.parent.mkdir(parents=True, exist_ok=True)
        outtmpl = f"{destination}.%(ext)s"

        def hook(d: dict) -> None:
            if cancel_event.is_set() or pause_event.is_set():
                raise YtdlpStopSignal("stopped by app")
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                on_progress(d.get("downloaded_bytes", 0), total, d.get("speed") or 0.0)

        ydl_opts = {
            "outtmpl": outtmpl,
            "format": self._format_selector,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "continuedl": True,
            "retries": 3,
            "progress_hooks": [hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except YtdlpStopSignal:
            if cancel_event.is_set():
                self._cleanup_temp_files(destination)
                raise DownloadCancelled()
            raise DownloadPaused()

        produced = self._find_produced_file(destination)
        if produced is None:
            raise RuntimeError("yt-dlp did not produce an output file")
        if produced != destination:
            produced.replace(destination)

        size = destination.stat().st_size
        on_progress(size, size, 0.0)

    @staticmethod
    def _find_produced_file(destination: Path) -> Path | None:
        matches = [
            path
            for path in destination.parent.glob(f"{destination.name}.*")
            if not path.name.endswith(".part")
        ]
        return matches[0] if matches else None

    @staticmethod
    def _cleanup_temp_files(destination: Path) -> None:
        for path in destination.parent.glob(f"{destination.name}.*"):
            path.unlink(missing_ok=True)
