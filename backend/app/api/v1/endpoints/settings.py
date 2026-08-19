import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_download_engine
from app.core.config import (
    Settings,
    get_settings,
    update_ai_provider,
    update_anthropic_api_key,
    update_library_dir,
    update_openai_api_key,
)
from app.modules.ai.llm_client import AI_PROVIDERS, resolve_ai_credentials
from app.services.download.engine import DownloadEngine

router = APIRouter()


class LibraryDirIn(BaseModel):
    path: str


class AnthropicApiKeyIn(BaseModel):
    api_key: str


class OpenAIApiKeyIn(BaseModel):
    api_key: str


class AIProviderIn(BaseModel):
    provider: str


class FolderEntry(BaseModel):
    name: str
    path: str


class BrowseFoldersOut(BaseModel):
    current_path: str | None
    parent_path: str | None
    folders: list[FolderEntry]


@router.get("/settings")
def read_settings(settings: Settings = Depends(get_settings)):
    return {
        "library_dir": settings.library_dir,
        "download_dir": settings.download_dir,
        "max_concurrent_downloads": settings.max_concurrent_downloads,
        # Never echo either key itself back to the client -- only whether
        # one is set. ai_provider names which one is currently active;
        # has_ai_key is the computed "is the *active* provider actually
        # usable right now" the frontend should check instead of assuming
        # Anthropic specifically.
        "ai_provider": settings.ai_provider,
        "has_anthropic_key": bool(settings.anthropic_api_key),
        "has_openai_key": bool(settings.openai_api_key),
        "has_ai_key": resolve_ai_credentials(settings) is not None,
    }


@router.put("/settings/anthropic-key")
def set_anthropic_api_key(payload: AnthropicApiKeyIn):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key khong duoc de trong")
    update_anthropic_api_key(key)
    return {"has_anthropic_key": True}


@router.put("/settings/openai-key")
def set_openai_api_key(payload: OpenAIApiKeyIn):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key khong duoc de trong")
    update_openai_api_key(key)
    return {"has_openai_key": True}


@router.put("/settings/ai-provider")
def set_ai_provider(payload: AIProviderIn):
    if payload.provider not in AI_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider {payload.provider!r}, must be one of {AI_PROVIDERS}")
    update_ai_provider(payload.provider)
    return {"ai_provider": payload.provider}


@router.put("/settings/library-dir")
def set_library_dir(
    payload: LibraryDirIn,
    engine: DownloadEngine = Depends(get_download_engine),
):
    path = Path(payload.path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Không tạo được thư mục: {exc}") from exc

    update_library_dir(str(path))
    engine.set_library_dir(path)
    return {"library_dir": str(path)}


@router.get("/settings/browse-folders", response_model=BrowseFoldersOut)
def browse_folders(path: str | None = None):
    if path is None:
        if sys.platform.startswith("win"):
            folders = [FolderEntry(name=drive, path=drive) for drive in os.listdrives()]
        else:
            folders = [FolderEntry(name="/", path="/")]
        return BrowseFoldersOut(current_path=None, parent_path=None, folders=folders)

    target = Path(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Thư mục không tồn tại")

    entries: list[FolderEntry] = []
    try:
        for child in sorted(target.iterdir()):
            if child.is_dir():
                entries.append(FolderEntry(name=child.name, path=str(child)))
    except PermissionError:
        pass

    parent = target.parent
    parent_path = str(parent) if parent != target else None
    return BrowseFoldersOut(current_path=str(target), parent_path=parent_path, folders=entries)
