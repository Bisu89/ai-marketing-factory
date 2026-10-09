"""Path -> /media URL for documentary files (same rule video_composer.schemas uses: the app serves
the library directory at /media)."""

from pathlib import Path


def media_url(path: Path, library_dir: Path) -> str | None:
    try:
        rel = Path(path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()
