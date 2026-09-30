"""Small media fixtures shared by the Factory stage tests (formerly defined
in the removed test_batch_render.py)."""

import shutil
from pathlib import Path

from PIL import Image

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_solid_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (320, 320)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path
