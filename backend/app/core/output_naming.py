"""Human-readable names for render output folders and final video files.

Real user report: every render landed in a bare `job_<id>` folder holding an
identically named `video_hoan_chinh.mp4` (Storyteller: `episodes/<id>/final.mp4`),
so finding one particular video meant opening folders one by one. Output
folders and final videos are now named `<prefix>_<id>_<title>` -- the id
keeps them unique and sortable, the title makes them findable.

Existing folders are always reused as-is (legacy bare `job_<id>`, or a
labeled one created under an earlier title), so a job's working files never
split across two folders when its title changes mid-run (Chinese Drama dub
jobs get their real title only after translation) or after an upgrade.
Every consumer reads the final video back from the path stored on its own
DB row, never by reconstructing this name.
"""
from __future__ import annotations

import re
from pathlib import Path

_WINDOWS_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}
# Kept short on purpose: the label appears twice in the final video's path
# (folder + filename) and Windows' default MAX_PATH is still 260.
MAX_LABEL_LEN = 50


def safe_label(text: str | None) -> str | None:
    """`text` stripped of characters Windows forbids in a filename, whitespace
    collapsed, truncated to MAX_LABEL_LEN. None when nothing usable is left.
    Unicode (Vietnamese diacritics etc.) is kept -- NTFS and ffmpeg both
    handle it, and a stripped-accent title is harder to recognize.
    """
    safe = _WINDOWS_UNSAFE_CHARS.sub("", text or "")
    safe = re.sub(r"\s+", " ", safe).strip(" .")[:MAX_LABEL_LEN].rstrip(" .")
    if not safe or safe.upper() in _WINDOWS_RESERVED_NAMES:
        return None
    return safe


def labeled_name(prefix: str, item_id: int, label: str | None) -> str:
    """`<prefix>_<id>_<label>` (`<id>_<label>` for an empty prefix), or just
    `<prefix>_<id>` when `label` has nothing usable in it."""
    parts = [p for p in (prefix, str(item_id), safe_label(label)) if p]
    return "_".join(parts)


def find_labeled_dir(parent: Path, prefix: str, item_id: int) -> Path | None:
    """The folder already on disk for this id -- the bare `<prefix>_<id>`
    (legacy) or any `<prefix>_<id>_<label>` -- or None."""
    bare = parent / labeled_name(prefix, item_id, None)
    if bare.is_dir():
        return bare
    if parent.is_dir():
        # `job_1_*` never matches `job_12_...`: the id is followed by "_".
        for candidate in sorted(parent.glob(f"{bare.name}_*")):
            if candidate.is_dir():
                return candidate
    return None


def resolve_labeled_dir(parent: Path, prefix: str, item_id: int, label: str | None) -> Path:
    """The existing folder for this id if there is one, else the new
    `<prefix>_<id>_<label>` path (not created)."""
    return find_labeled_dir(parent, prefix, item_id) or parent / labeled_name(prefix, item_id, label)


def labeled_video_filename(prefix: str, item_id: int, label: str | None) -> str:
    return f"{labeled_name(prefix, item_id, label)}.mp4"
