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
    update_google_oauth_client_id,
    update_google_oauth_client_secret,
    update_library_dir,
    update_news_poll_interval_minutes,
    update_openai_api_key,
    update_render_cache_retention_days,
    update_tiktok_client_key,
    update_tiktok_client_secret,
    update_tiktok_redirect_uri,
    update_youtube_redirect_uri,
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


class TikTokClientKeyIn(BaseModel):
    client_key: str


class TikTokClientSecretIn(BaseModel):
    client_secret: str


class TikTokRedirectUriIn(BaseModel):
    redirect_uri: str


class GoogleOAuthClientIn(BaseModel):
    client_id: str
    client_secret: str


class YouTubeRedirectUriIn(BaseModel):
    redirect_uri: str


class RenderCacheRetentionIn(BaseModel):
    days: int


class NewsPollIntervalIn(BaseModel):
    minutes: int


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
        # Competitor Content Analyzer (Task 11) -- same "never echo the
        # secret, only whether it's set" convention as the AI keys above.
        "has_tiktok_client_key": bool(settings.tiktok_client_key),
        "has_tiktok_client_secret": bool(settings.tiktok_client_secret),
        "tiktok_redirect_uri": settings.tiktok_redirect_uri,
        # YouTube Publishing (see docs/features/127-youtube-publishing.md) --
        # same "never echo the secret, only whether it's set" convention.
        "has_google_oauth_client": bool(settings.google_oauth_client_id and settings.google_oauth_client_secret),
        "youtube_redirect_uri": settings.youtube_redirect_uri,
        # Render-cache auto-cleanup (0 = off). See
        # app/api/v1/endpoints/assets_cleanup.py.
        "render_cache_retention_days": settings.render_cache_retention_days,
        # News channel feed poll interval in minutes (0 = off). See
        # app/modules/news/ and docs/features/123-news-channel.md.
        "news_poll_interval_minutes": settings.news_poll_interval_minutes,
    }


@router.put("/settings/render-cache-retention")
def set_render_cache_retention(payload: RenderCacheRetentionIn):
    if payload.days < 0 or payload.days > 3650:
        raise HTTPException(status_code=400, detail="days must be between 0 and 3650 (0 = off)")
    update_render_cache_retention_days(payload.days)
    return {"render_cache_retention_days": payload.days}


@router.put("/settings/news-poll-interval")
def set_news_poll_interval(payload: NewsPollIntervalIn):
    if payload.minutes < 0 or payload.minutes > 1440:
        raise HTTPException(status_code=400, detail="minutes must be between 0 and 1440 (0 = off)")
    update_news_poll_interval_minutes(payload.minutes)
    return {"news_poll_interval_minutes": payload.minutes}


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


@router.put("/settings/tiktok-client-key")
def set_tiktok_client_key(payload: TikTokClientKeyIn):
    key = payload.client_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Client key khong duoc de trong")
    update_tiktok_client_key(key)
    return {"has_tiktok_client_key": True}


@router.put("/settings/tiktok-client-secret")
def set_tiktok_client_secret(payload: TikTokClientSecretIn):
    secret = payload.client_secret.strip()
    if not secret:
        raise HTTPException(status_code=400, detail="Client secret khong duoc de trong")
    update_tiktok_client_secret(secret)
    return {"has_tiktok_client_secret": True}


@router.put("/settings/tiktok-redirect-uri")
def set_tiktok_redirect_uri(payload: TikTokRedirectUriIn):
    uri = payload.redirect_uri.strip()
    if not uri.startswith("https://"):
        raise HTTPException(status_code=400, detail="Redirect URI phai la HTTPS -- TikTok khong chap nhan http://")
    update_tiktok_redirect_uri(uri)
    return {"tiktok_redirect_uri": uri}


@router.put("/settings/google-oauth-client")
def set_google_oauth_client(payload: GoogleOAuthClientIn):
    cid = payload.client_id.strip()
    secret = payload.client_secret.strip()
    if not cid or not secret:
        raise HTTPException(status_code=400, detail="Client ID va Client Secret khong duoc de trong")
    update_google_oauth_client_id(cid)
    update_google_oauth_client_secret(secret)
    return {"has_google_oauth_client": True}


@router.put("/settings/youtube-redirect-uri")
def set_youtube_redirect_uri(payload: YouTubeRedirectUriIn):
    uri = payload.redirect_uri.strip()
    if not (uri.startswith("http://127.0.0.1") or uri.startswith("http://localhost") or uri.startswith("https://")):
        raise HTTPException(status_code=400, detail="Redirect URI phai la http://127.0.0.1..., http://localhost... hoac https://...")
    update_youtube_redirect_uri(uri)
    return {"youtube_redirect_uri": uri}


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
