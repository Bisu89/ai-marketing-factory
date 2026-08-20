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

    # Render job hardening (Task 11 -- see
    # docs/features/38-render-job-hardening.md). A conservative fixed
    # floor, not a real per-video size estimate (deliberately out of
    # scope -- see that doc's "disk-space preflight" section): below this,
    # a render is rejected before it starts rather than failing partway
    # through with a cryptic ffmpeg I/O error.
    min_free_disk_mb: int = 500

    # Batch video creation (Task 13 -- see
    # docs/features/40-batch-video-creation.md). Caps how many "Generate
    # Beats for Batch" Claude calls run at once -- a conservative default,
    # not a real Anthropic-reported rate limit (this app has no such
    # config to reuse), configurable per this task's own instruction.
    max_concurrent_ai_generation: int = 2

    # Factory Batch Engine (Task 20 -- see
    # docs/features/46-factory-batch-engine.md). How many FactoryRuns may
    # be actively progressing through their *local* stages (Beat/Visual/
    # Quality) at once -- deliberately conservative for a desktop machine,
    # and deliberately NOT the same knob as max_concurrent_ai_generation
    # (a project can be "active" while waiting on other local work, not
    # just an AI call) or max_parallel_renders (rendering is a completely
    # separate, already-serial concern -- see that field's own docstring).
    max_parallel_projects: int = 2

    # Informational/reporting only -- app.modules.video_composer.VideoComposerService
    # has exactly one worker thread (a single queue.Queue + one
    # threading.Thread, see that module), so render concurrency is already
    # 1 by construction and this setting does not currently control
    # anything. Kept here (rather than omitted) so factory batch reporting
    # has a real number to show alongside max_parallel_projects, and so a
    # future multi-worker render queue has an obvious place to plug in.
    max_parallel_renders: int = 1

    # Content Engine (Task 21 -- see docs/features/47-content-brief-script-engine.md).
    # Configurable speech rate for the Script word-count validator (section
    # 13's own "do not hardcode one universal speech rate") -- a natural
    # narration pace, not a precise TTS timing model (that's Task 22's job).
    content_words_per_second: float = 2.2

    # Voice Factory (Task 22 -- see docs/features/48-voice-factory-local-tts.md
    # section 19). A configurable floor, not hardcoded -- prevents an
    # unusably short beat window from real narration timing without ever
    # silently deleting a beat (app.modules.voice.timing rebalances
    # neighboring beats instead).
    voice_min_beat_duration: float = 0.8

    anthropic_api_key: str | None = None

    # Dual AI Provider (see docs/features/55-dual-ai-provider.md) -- which
    # provider app.modules.ai.llm_client.resolve_ai_credentials picks by
    # default. Plain, unvalidated string (same as anthropic_api_key above);
    # the PUT /settings/ai-provider endpoint is what actually validates
    # against llm_client.AI_PROVIDERS before persisting.
    ai_provider: str = "anthropic"
    openai_api_key: str | None = None

    # Competitor Content Analyzer (Task 11 -- see
    # docs/features/76-competitor-content-analyzer.md). TikTok Developer
    # app credentials (one app, registered by the user on
    # developers.tiktok.com) -- same "plain str field + dedicated
    # update_x()" shape as anthropic_api_key/openai_api_key above.
    # tiktok_redirect_uri must be an HTTPS URL registered with that TikTok
    # app (TikTok's own requirement, not this app's choice); see the
    # module's own setup doc for why a desktop-local app needs one.
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_redirect_uri: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def update_library_dir(new_path: str) -> None:
    set_key(ENV_FILE_PATH, "APP_LIBRARY_DIR", new_path)
    get_settings.cache_clear()


def update_anthropic_api_key(key: str) -> None:
    set_key(ENV_FILE_PATH, "APP_ANTHROPIC_API_KEY", key)
    get_settings.cache_clear()


def update_openai_api_key(key: str) -> None:
    set_key(ENV_FILE_PATH, "APP_OPENAI_API_KEY", key)
    get_settings.cache_clear()


def update_ai_provider(provider: str) -> None:
    set_key(ENV_FILE_PATH, "APP_AI_PROVIDER", provider)
    get_settings.cache_clear()


def update_tiktok_client_key(key: str) -> None:
    set_key(ENV_FILE_PATH, "APP_TIKTOK_CLIENT_KEY", key)
    get_settings.cache_clear()


def update_tiktok_client_secret(secret: str) -> None:
    set_key(ENV_FILE_PATH, "APP_TIKTOK_CLIENT_SECRET", secret)
    get_settings.cache_clear()


def update_tiktok_redirect_uri(uri: str) -> None:
    set_key(ENV_FILE_PATH, "APP_TIKTOK_REDIRECT_URI", uri)
    get_settings.cache_clear()
