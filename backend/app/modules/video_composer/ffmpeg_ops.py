"""Thin ffmpeg / ffprobe subprocess helpers for the Video Composer's render
path. Extracted verbatim from `VideoComposerService` (P2 refactor).

No cancellation hook here -- these run to completion via `subprocess.run`;
the render worker cancels at phase boundaries, not mid-ffmpeg.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_ffmpeg(args: list[str]) -> None:
    # -nostdin + stdin=DEVNULL: ffmpeg reads stdin by default for
    # interactive key commands; run as a subprocess with an inherited/piped
    # stdin that never delivers EOF, it can block indefinitely on certain
    # inputs instead of failing fast (confirmed as a real, reproducible hang
    # while building app/modules/motion/renderer.py -- see
    # docs/features/23-local-motion-renderer.md's "Real bugs").
    command = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[-2000:]}")


def probe_duration(path: Path) -> float:
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return float(result.stdout.strip())


def probe_video_info(path: Path) -> tuple[int, int, float]:
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "csv=p=0:s=x",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    width_str, height_str, fps_str = result.stdout.strip().split("x")
    num, _, den = fps_str.partition("/")
    fps = float(num) / float(den or 1)
    return int(width_str), int(height_str), fps


def escape_for_ffmpeg_filter(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:")
