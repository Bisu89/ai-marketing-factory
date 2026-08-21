"""Outro Card composition root (real user report: videos cut off abruptly
right when narration ends -- see app.modules.outro.schemas' own docstring
for the full feature). Adapts app.modules.outro's pure renderer to real
project config/BGM/render-profile data, same composition-root shape as
imagegen_generate.py/motion_generate.py.

Reads the BGM track audio_generate.py's own Audio Master mix already
resolved (`audio_master.meta.json`'s `bgm_artifact` field) rather than
re-running BGM selection -- the outro should swell whatever track is
already playing under the main video, never a second, independently
(and possibly differently) auto-selected one.
"""

import json
from pathlib import Path

from app.core.config import Settings
from app.core.render_profile import RenderProfile
from app.modules.beat.schemas import ProjectConfig
from app.modules.outro.renderer import render_outro_clip


def _outro_dir(project_id: int, library_dir: str) -> Path:
    return Path(library_dir) / "_outro" / f"project_{project_id}"


def outro_clip_path(project_id: int, library_dir: str) -> Path:
    return _outro_dir(project_id, library_dir) / "outro.mp4"


def _resolve_bgm_path(project_id: int, config: ProjectConfig, library_dir: str) -> str | None:
    if not config.audio.music_enabled:
        return None
    meta_path = Path(library_dir) / "_audio" / f"project_{project_id}" / "audio_master.meta.json"
    if not meta_path.exists():
        return None
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    bgm_artifact = metadata.get("bgm_artifact")
    if bgm_artifact is None or not Path(bgm_artifact).exists():
        return None
    return bgm_artifact


def resolve_outro_clip(
    project_id: int, config: ProjectConfig, render_profile: RenderProfile, settings: Settings
) -> str | None:
    """Renders a fresh outro clip for this run and returns its path, or
    None when this project has no outro configured (every existing
    project, the common case -- config.outro.enabled defaults False).
    Cheap local ffmpeg, no AI cost -- unlike Audio Master/Visuals, no
    caching/fingerprint scheme is needed; always regenerated fresh.
    """
    if not config.outro.enabled or not config.outro.text.strip():
        return None

    bgm_path = _resolve_bgm_path(project_id, config, settings.library_dir)
    output_path = outro_clip_path(project_id, settings.library_dir)
    render_outro_clip(
        text=config.outro.text,
        duration_sec=config.outro.duration_sec,
        width=render_profile.width,
        height=render_profile.height,
        fps=render_profile.fps,
        output_path=output_path,
        bgm_path=Path(bgm_path) if bgm_path else None,
        bgm_start_volume=config.audio.music_volume,
    )
    return str(output_path)
