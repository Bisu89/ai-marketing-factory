import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import set_key
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# PyInstaller sets sys.frozen=True on a packaged build. Only then do paths
# move off "relative to CWD" (fine for `uvicorn` run from the repo root in
# dev) onto a real per-user writable location -- an installed .exe's CWD is
# unpredictable, and its own install folder may not be writable for a
# no-admin install. Dev behavior is completely unchanged either way.
IS_FROZEN = getattr(sys, "frozen", False)


def _app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "AIContentLibrary"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_file_path() -> str:
    if not IS_FROZEN:
        return ".env"
    return str(_app_data_dir() / ".env")


def _default_database_url() -> str:
    if not IS_FROZEN:
        return "sqlite:///./data/library.db"
    data_dir = _app_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'library.db').as_posix()}"


def _default_download_dir() -> str:
    if not IS_FROZEN:
        return "./data/downloads"
    return str(_app_data_dir() / "data" / "downloads")


def _default_library_dir() -> str:
    if not IS_FROZEN:
        return "./data/library"
    return str(_app_data_dir() / "data" / "library")


# Resolved once at import time (IS_FROZEN never changes within a process),
# shared between Settings' own env_file config and the update_*() helpers
# below so both agree on where the .env actually lives.
ENV_FILE_PATH = _env_file_path()


def resource_path(relative: str) -> Path:
    """Resolve a bundled read-only resource (bundled ffmpeg, the built
    frontend) both in dev and when frozen. PyInstaller extracts/places
    `datas` under sys._MEIPASS (the app's own folder in onedir mode); in dev
    there's no such thing, so relative falls back to the repo layout.
    """
    if IS_FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / relative
    return Path(__file__).resolve().parents[3] / relative


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_prefix="APP_", extra="ignore")

    app_name: str = "AI Content Library"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = Field(default_factory=_default_database_url)

    log_level: str = "INFO"

    download_dir: str = Field(default_factory=_default_download_dir)
    library_dir: str = Field(default_factory=_default_library_dir)
    max_concurrent_downloads: int = 3

    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def update_library_dir(new_path: str) -> None:
    set_key(ENV_FILE_PATH, "APP_LIBRARY_DIR", new_path)
    get_settings.cache_clear()


def update_anthropic_api_key(key: str) -> None:
    set_key(ENV_FILE_PATH, "APP_ANTHROPIC_API_KEY", key)
    get_settings.cache_clear()
