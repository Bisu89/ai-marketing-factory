from functools import lru_cache

from dotenv import set_key
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "AI Content Library"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = "sqlite:///./data/library.db"

    log_level: str = "INFO"

    download_dir: str = "./data/downloads"
    library_dir: str = "./data/library"
    max_concurrent_downloads: int = 3

    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def update_library_dir(new_path: str) -> None:
    set_key(".env", "APP_LIBRARY_DIR", new_path)
    get_settings.cache_clear()


def update_anthropic_api_key(key: str) -> None:
    set_key(".env", "APP_ANTHROPIC_API_KEY", key)
    get_settings.cache_clear()
