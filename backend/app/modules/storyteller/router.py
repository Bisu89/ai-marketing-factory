"""Storyteller API: paste/upload a script -> narrated long-form video.
No AI endpoint here at all -- the script comes from outside this app."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.modules.storyteller import service
from app.modules.storyteller.schemas import AssetOut, EpisodeCreateIn, EpisodeOut
from app.modules.storyteller.service import StorytellerService

router = APIRouter()

_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1258", "utf-16")


def get_storyteller_service(request: Request) -> StorytellerService:
    return request.app.state.storyteller_service


def _decode_text(raw: bytes) -> str:
    for enc in _TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValidationError("Không đọc được file -- hãy lưu dưới dạng .txt UTF-8")


def _episode_out(row) -> EpisodeOut:
    return EpisodeOut.model_validate(row, from_attributes=True)


def _asset_out(row) -> AssetOut:
    return AssetOut.model_validate(row, from_attributes=True)


@router.post("/storyteller/episodes", response_model=EpisodeOut, status_code=201)
def create_episode(payload: EpisodeCreateIn, svc: StorytellerService = Depends(get_storyteller_service)):
    episode = service.create_episode(**payload.model_dump())
    svc.enqueue(episode.id)
    return _episode_out(episode)


@router.post("/storyteller/episodes/upload", response_model=EpisodeOut, status_code=201)
def create_episode_from_file(
    title: str = Form(...),
    voice: str = Form("vi-VN-HoaiMyNeural"),
    narration_rate: str = Form("+0%"),
    burn_captions: bool = Form(True),
    layout: str = Form("single"),
    background_asset_id: int | None = Form(None),
    avatar_asset_id: int | None = Form(None),
    left_asset_id: int | None = Form(None),
    middle_asset_id: int | None = Form(None),
    right_asset_id: int | None = Form(None),
    slide_asset_ids: str | None = Form(None),
    music_asset_id: int | None = Form(None),
    disclaimer_text: str | None = Form(None),
    story_title: str | None = Form(None),
    story_author: str | None = Form(None),
    story_character: str | None = Form(None),
    file: UploadFile = File(...),
    svc: StorytellerService = Depends(get_storyteller_service),
):
    raw = file.file.read()
    if not raw:
        raise ValidationError("File rỗng")
    script_text = _decode_text(raw)
    slide_ids = [int(x) for x in slide_asset_ids.split(",") if x.strip()] if slide_asset_ids else None
    if layout == "slideshow" and len(slide_ids or []) < 2:
        raise ValidationError("Bố cục slideshow cần ít nhất 2 ảnh")
    episode = service.create_episode(
        title=title, script_text=script_text, voice=voice, narration_rate=narration_rate,
        burn_captions=burn_captions, layout=layout,
        background_asset_id=background_asset_id, avatar_asset_id=avatar_asset_id,
        left_asset_id=left_asset_id, middle_asset_id=middle_asset_id, right_asset_id=right_asset_id,
        slide_asset_ids=slide_ids, music_asset_id=music_asset_id,
        disclaimer_text=disclaimer_text or None, story_title=story_title or None,
        story_author=story_author or None, story_character=story_character or None,
    )
    svc.enqueue(episode.id)
    return _episode_out(episode)


@router.get("/storyteller/episodes", response_model=list[EpisodeOut])
def list_episodes():
    return [_episode_out(e) for e in service.list_episodes()]


@router.get("/storyteller/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode(episode_id: int):
    return _episode_out(service.get_episode(episode_id))


@router.get("/storyteller/episodes/{episode_id}/file")
def get_episode_file(episode_id: int):
    episode = service.get_episode(episode_id)
    if not episode.output_path or not Path(episode.output_path).is_file():
        raise ValidationError("Video chưa render xong")
    return FileResponse(episode.output_path, media_type="video/mp4")


@router.post("/storyteller/episodes/{episode_id}/retry", response_model=EpisodeOut)
def retry_episode(episode_id: int, svc: StorytellerService = Depends(get_storyteller_service)):
    episode = service.retry_episode(episode_id)
    svc.enqueue(episode.id)
    return _episode_out(episode)


@router.delete("/storyteller/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: int, settings: Settings = Depends(get_settings)):
    service.delete_episode(episode_id, Path(settings.library_dir))


@router.post("/storyteller/assets", response_model=AssetOut, status_code=201)
def upload_asset(
    kind: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    asset = service.save_asset(kind=kind, name=name, tmp_upload_path=tmp_path, library_dir=Path(settings.library_dir))
    return _asset_out(asset)


@router.get("/storyteller/assets", response_model=list[AssetOut])
def list_assets(kind: str | None = None):
    return [_asset_out(a) for a in service.list_assets(kind)]


@router.delete("/storyteller/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: int, settings: Settings = Depends(get_settings)):
    service.delete_asset(asset_id, Path(settings.library_dir))
