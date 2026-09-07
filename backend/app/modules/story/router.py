"""Story planning CRUD (feature 131). Pure module router -- no cross-module
work here (Phase 2's story pipeline lives in a composition root,
app/api/v1/endpoints/story_pipeline.py, the same split
app.modules.series.router / series_project.py already use).

NotFoundError / ValidationError raised by the service layer are turned
into 404 / 400 JSON by the global handlers in app/main.py.
"""

from fastapi import APIRouter

from app.modules.story import service
from app.modules.story.schemas import (
    ChannelIn,
    ChannelOut,
    EpisodeIn,
    EpisodeOut,
    StoryChapterIn,
    StoryChapterOut,
    StoryCharacterIn,
    StoryCharacterOut,
    StoryCheckpointOut,
    StoryIn,
    StoryLocationIn,
    StoryLocationOut,
    StoryOut,
    StoryPatch,
    StoryRunOut,
    StorySceneIn,
    StorySceneOut,
)

router = APIRouter()


def _out(model, row):
    return model.model_validate(row, from_attributes=True)


# -- Channels ----------------------------------------------------------


@router.post("/story-channels", response_model=ChannelOut, status_code=201)
def create_channel(payload: ChannelIn) -> ChannelOut:
    return _out(ChannelOut, service.create_channel(**payload.model_dump()))


@router.get("/story-channels", response_model=list[ChannelOut])
def list_channels() -> list[ChannelOut]:
    return [_out(ChannelOut, c) for c in service.list_channels()]


@router.get("/story-channels/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: int) -> ChannelOut:
    return _out(ChannelOut, service.get_channel(channel_id))


@router.put("/story-channels/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, payload: ChannelIn) -> ChannelOut:
    return _out(ChannelOut, service.update_channel(channel_id, **payload.model_dump()))


@router.delete("/story-channels/{channel_id}", status_code=204)
def delete_channel(channel_id: int) -> None:
    service.delete_channel(channel_id)


# -- Episodes -------------------------------------------------------


@router.post("/episodes", response_model=EpisodeOut, status_code=201)
def create_episode(payload: EpisodeIn) -> EpisodeOut:
    return _out(EpisodeOut, service.create_episode(**payload.model_dump()))


@router.get("/series/{series_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(series_id: int) -> list[EpisodeOut]:
    return [_out(EpisodeOut, e) for e in service.list_episodes_for_series(series_id)]


@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode(episode_id: int) -> EpisodeOut:
    return _out(EpisodeOut, service.get_episode(episode_id))


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(episode_id: int, payload: EpisodeIn) -> EpisodeOut:
    return _out(EpisodeOut, service.update_episode(episode_id, **payload.model_dump()))


@router.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: int) -> None:
    service.delete_episode(episode_id)


# -- Stories -------------------------------------------------------


@router.post("/stories", response_model=StoryOut, status_code=201)
def create_story(payload: StoryIn) -> StoryOut:
    return _out(StoryOut, service.create_story(**payload.model_dump()))


@router.get("/stories", response_model=list[StoryOut])
def list_stories(mode: str | None = None, status: str | None = None) -> list[StoryOut]:
    return [_out(StoryOut, s) for s in service.list_stories(mode=mode, status=status)]


@router.get("/stories/{story_id}", response_model=StoryOut)
def get_story(story_id: int) -> StoryOut:
    return _out(StoryOut, service.get_story(story_id))


@router.patch("/stories/{story_id}", response_model=StoryOut)
def patch_story(story_id: int, payload: StoryPatch) -> StoryOut:
    return _out(StoryOut, service.patch_story(story_id, payload.model_dump(exclude_unset=True)))


@router.delete("/stories/{story_id}", status_code=204)
def delete_story(story_id: int) -> None:
    service.delete_story(story_id)


# -- Characters --------------------------------------------------


@router.post("/stories/{story_id}/characters", response_model=StoryCharacterOut, status_code=201)
def add_character(story_id: int, payload: StoryCharacterIn) -> StoryCharacterOut:
    return _out(StoryCharacterOut, service.add_character(story_id, **payload.model_dump()))


@router.get("/stories/{story_id}/characters", response_model=list[StoryCharacterOut])
def list_characters(story_id: int) -> list[StoryCharacterOut]:
    return [_out(StoryCharacterOut, c) for c in service.list_characters(story_id)]


@router.put("/story-characters/{character_id}", response_model=StoryCharacterOut)
def update_character(character_id: int, payload: StoryCharacterIn) -> StoryCharacterOut:
    return _out(StoryCharacterOut, service.update_character(character_id, **payload.model_dump()))


@router.delete("/story-characters/{character_id}", status_code=204)
def delete_character(character_id: int) -> None:
    service.delete_character(character_id)


# -- Locations --------------------------------------------------


@router.post("/stories/{story_id}/locations", response_model=StoryLocationOut, status_code=201)
def add_location(story_id: int, payload: StoryLocationIn) -> StoryLocationOut:
    return _out(StoryLocationOut, service.add_location(story_id, **payload.model_dump()))


@router.get("/stories/{story_id}/locations", response_model=list[StoryLocationOut])
def list_locations(story_id: int) -> list[StoryLocationOut]:
    return [_out(StoryLocationOut, loc) for loc in service.list_locations(story_id)]


@router.put("/story-locations/{location_id}", response_model=StoryLocationOut)
def update_location(location_id: int, payload: StoryLocationIn) -> StoryLocationOut:
    return _out(StoryLocationOut, service.update_location(location_id, **payload.model_dump()))


@router.delete("/story-locations/{location_id}", status_code=204)
def delete_location(location_id: int) -> None:
    service.delete_location(location_id)


# -- Chapters --------------------------------------------------


@router.post("/stories/{story_id}/chapters", response_model=StoryChapterOut, status_code=201)
def add_chapter(story_id: int, payload: StoryChapterIn) -> StoryChapterOut:
    return _out(StoryChapterOut, service.add_chapter(story_id, **payload.model_dump()))


@router.get("/stories/{story_id}/chapters", response_model=list[StoryChapterOut])
def list_chapters(story_id: int) -> list[StoryChapterOut]:
    return [_out(StoryChapterOut, c) for c in service.list_chapters(story_id)]


@router.put("/story-chapters/{chapter_id}", response_model=StoryChapterOut)
def update_chapter(chapter_id: int, payload: StoryChapterIn) -> StoryChapterOut:
    return _out(StoryChapterOut, service.update_chapter(chapter_id, **payload.model_dump()))


@router.delete("/story-chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: int) -> None:
    service.delete_chapter(chapter_id)


# -- Scenes --------------------------------------------------


@router.post("/story-chapters/{chapter_id}/scenes", response_model=StorySceneOut, status_code=201)
def add_scene(chapter_id: int, payload: StorySceneIn) -> StorySceneOut:
    return _out(StorySceneOut, service.add_scene(chapter_id, **payload.model_dump()))


@router.get("/story-chapters/{chapter_id}/scenes", response_model=list[StorySceneOut])
def list_scenes(chapter_id: int) -> list[StorySceneOut]:
    return [_out(StorySceneOut, s) for s in service.list_scenes(chapter_id)]


@router.put("/story-scenes/{scene_id}", response_model=StorySceneOut)
def update_scene(scene_id: int, payload: StorySceneIn) -> StorySceneOut:
    return _out(StorySceneOut, service.update_scene(scene_id, **payload.model_dump()))


@router.delete("/story-scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: int) -> None:
    service.delete_scene(scene_id)


# -- StoryRun / StoryCheckpoint (read-only in Phase 1) -----------


@router.get("/stories/{story_id}/runs", response_model=list[StoryRunOut])
def list_runs(story_id: int) -> list[StoryRunOut]:
    return [_out(StoryRunOut, r) for r in service.list_runs_for_story(story_id)]


@router.get("/story-runs/{run_id}", response_model=StoryRunOut)
def get_run(run_id: int) -> StoryRunOut:
    from app.core.exceptions import NotFoundError

    run = service.get_run(run_id)
    if run is None:
        raise NotFoundError("StoryRun", run_id)
    return _out(StoryRunOut, run)


@router.get("/story-runs/{run_id}/checkpoints", response_model=list[StoryCheckpointOut])
def get_run_checkpoints(run_id: int) -> list[StoryCheckpointOut]:
    return [_out(StoryCheckpointOut, c) for c in service.get_checkpoints(run_id)]
