from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.scene_cutter.models import SceneCutJob, SceneCutResult


class PickFolderOut(BaseModel):
    path: str | None


class SceneCutJobCreateIn(BaseModel):
    video_id: int | None = None
    source_path: str | None = None
    threshold: float = 46.0
    # Real user report: a single continuous scene came back cut into 3 at
    # the old default of 0.6s -- see SceneCutterService._merge_short_scenes
    # for the deterministic safety net added alongside this; raising the
    # detector's own floor here is the first line of defense, reducing how
    # often a spurious sub-second boundary (whip-pan, flash, motion blur)
    # gets registered as a scene break in the first place.
    min_scene_len_sec: float = 1.2
    trim_sec: float = 0.0
    output_dir: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "SceneCutJobCreateIn":
        if (self.video_id is None) == (self.source_path is None):
            raise ValueError("Provide exactly one of video_id or source_path")
        return self


def _to_media_url(file_path: str, library_dir: Path) -> str | None:
    # Only paths inside library_dir are servable via the /media static mount
    # (see app/main.py) -- arbitrary-file jobs are stored under
    # library_dir/_local_files/ specifically so their scenes are previewable
    # in the browser too, not just downloadable from disk.
    try:
        rel = Path(file_path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scene_number: int
    start_timecode: str
    end_timecode: str
    file_path: str
    media_url: str | None = None


def scene_to_out(scene: SceneCutResult, library_dir: Path) -> SceneOut:
    base = SceneOut.model_validate(scene)
    return base.model_copy(update={"media_url": _to_media_url(scene.file_path, library_dir)})


class SceneCutJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int | None
    source_path: str | None
    threshold: float
    min_scene_len_sec: float
    trim_sec: float
    requested_output_dir: str | None
    status: str
    scene_count: int | None
    output_dir: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    scenes: list[SceneOut] = []


def job_to_out(job: SceneCutJob, library_dir: Path) -> SceneCutJobOut:
    base = SceneCutJobOut.model_validate(job)
    return base.model_copy(update={"scenes": [scene_to_out(s, library_dir) for s in job.scenes]})
