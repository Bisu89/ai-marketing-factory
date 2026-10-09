import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_download_engine
from app.core.config import (
    Settings,
    get_settings,
    update_ai_provider,
    update_anthropic_api_key,
    update_elevenlabs_settings,
    update_library_dir,
    update_openai_api_key,
    update_render_cache_retention_days,
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


class ElevenLabsSettingsIn(BaseModel):
    """Every field optional: only the ones sent are changed. api_key, when
    sent, must be non-empty (use it to rotate, not to clear)."""

    api_key: str | None = None
    voice_id: str | None = None
    model_id: str | None = None
    stability: float | None = Field(default=None, ge=0, le=1)
    similarity_boost: float | None = Field(default=None, ge=0, le=1)
    style: float | None = Field(default=None, ge=0, le=1)
    speed: float | None = Field(default=None, ge=0.7, le=1.2)
    usd_per_1k_chars: float | None = Field(default=None, ge=0)


class AIProviderIn(BaseModel):
    provider: str


class RenderCacheRetentionIn(BaseModel):
    days: int


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
        # Render-cache auto-cleanup (0 = off). See
        # app/api/v1/endpoints/assets_cleanup.py.
        "render_cache_retention_days": settings.render_cache_retention_days,
        "elevenlabs": _elevenlabs_view(settings),
    }


def _elevenlabs_view(settings: Settings) -> dict:
    return {
        "has_api_key": bool(settings.elevenlabs_api_key),  # the key itself is never returned
        "voice_id": settings.elevenlabs_voice_id,
        "model_id": settings.elevenlabs_model_id,
        "stability": settings.elevenlabs_stability,
        "similarity_boost": settings.elevenlabs_similarity_boost,
        "style": settings.elevenlabs_style,
        "speed": settings.elevenlabs_speed,
        "usd_per_1k_chars": settings.elevenlabs_usd_per_1k_chars,
        "ready": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id),
    }


@router.put("/settings/elevenlabs")
def set_elevenlabs(payload: ElevenLabsSettingsIn):
    values: dict[str, str] = {}
    for name, value in payload.model_dump(exclude_none=True).items():
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail=f"{name} khong duoc de trong")
        values[name] = str(value)
    if not values:
        raise HTTPException(status_code=400, detail="Khong co truong nao de cap nhat")
    update_elevenlabs_settings(values)
    return _elevenlabs_view(get_settings())


@router.put("/settings/render-cache-retention")
def set_render_cache_retention(payload: RenderCacheRetentionIn):
    if payload.days < 0 or payload.days > 3650:
        raise HTTPException(status_code=400, detail="days must be between 0 and 3650 (0 = off)")
    update_render_cache_retention_days(payload.days)
    return {"render_cache_retention_days": payload.days}


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


def _list_windows_drives() -> list[str]:
    # os.listdrives() (Python 3.12+) isn't available on this app's own
    # pinned Python 3.11 -- a plain existence check per drive letter works
    # identically on any Python version and needs no extra dependency.
    import string

    return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]


@router.get("/settings/browse-folders", response_model=BrowseFoldersOut)
def browse_folders(path: str | None = None):
    if path is None:
        if sys.platform.startswith("win"):
            folders = [FolderEntry(name=drive, path=drive) for drive in _list_windows_drives()]
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
