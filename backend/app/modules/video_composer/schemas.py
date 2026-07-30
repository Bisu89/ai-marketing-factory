from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.modules.video_composer.models import VideoComposeJob


def _to_media_url(file_path: str, library_dir: Path) -> str | None:
    try:
        rel = Path(file_path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


class VideoComposeJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    music_volume: float
    transition_duration: float
    requested_output_dir: str | None
    status: str
    clip_count: int
    output_path: str | None
    output_media_url: str | None = None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


def job_to_out(job: VideoComposeJob, library_dir: Path) -> VideoComposeJobOut:
    base = VideoComposeJobOut.model_validate(job)
    output_media_url = _to_media_url(job.output_path, library_dir) if job.output_path else None
    return base.model_copy(update={"output_media_url": output_media_url})


class PickFolderOut(BaseModel):
    path: str | None
