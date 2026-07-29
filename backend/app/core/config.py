from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "AI Content Library"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = "sqlite:///./data/library.db"

    log_level: str = "INFO"

    download_dir: str = "./data/downloads"
    max_concurrent_downloads: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
