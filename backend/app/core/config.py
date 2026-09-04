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

    # Default narration settings used to pre-fill the voice fields when a
    # user creates a NEW Video Factory template from "Blank" (see
    # CreateTemplateModal). Purely a starting point -- once a template is
    # created it carries its own snapshot, and changing these never touches
    # an existing template or project. Mirrors VoiceProjectConfig's own
    # field names/defaults (app.modules.beat.schemas): provider in
    # ("local", "edge_tts"), speed 0.5-2.0, pause 0.0-2.0s.
    default_voice_provider: str = "local"
    default_voice_id: str = "default"
    default_voice_speed: float = 1.0
    default_sentence_pause_sec: float = 0.35

    # Render-cache auto-cleanup (see docs/features/121-...). How many days
    # after a project's render finishes before its regenerable per-beat
    # voice/motion/audio cache (_voice/_motion/_audio/project_<id>/) is
    # swept automatically, at startup + every 24h. 0 = off (the shipped
    # default -- never auto-deletes anything unless the user opts in).
    # AI-generated images are never included in the automatic sweep.
    render_cache_retention_days: int = 0

    # News channel (see docs/features/123-news-channel.md). How often the
    # background poll loop re-fetches every enabled NewsSource, in minutes.
    # 0 = off (the shipped default -- feeds are only pulled when the user
    # clicks "Fetch"). A sensible manual value is 30-60.
    news_poll_interval_minutes: int = 0

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

    # YouTube Publishing (see docs/features/127-youtube-publishing.md).
    # Google Cloud OAuth 2.0 "Desktop app" client credentials the user
    # creates themselves (one Cloud project, YouTube Data API v3 enabled) --
    # same "plain str field + dedicated update_x()" shape as the keys above.
    # youtube_redirect_uri must be one of the redirect URIs registered on
    # that OAuth client; the loopback default works for a desktop app.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    youtube_redirect_uri: str = "http://127.0.0.1:8000/api/v1/publishing/youtube/oauth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def update_library_dir(new_path: str) -> None:
    set_key(ENV_FILE_PATH, "APP_LIBRARY_DIR", new_path)
    get_settings.cache_clear()


def update_render_cache_retention_days(days: int) -> None:
    set_key(ENV_FILE_PATH, "APP_RENDER_CACHE_RETENTION_DAYS", str(days))
    get_settings.cache_clear()


def update_news_poll_interval_minutes(minutes: int) -> None:
    set_key(ENV_FILE_PATH, "APP_NEWS_POLL_INTERVAL_MINUTES", str(minutes))
    get_settings.cache_clear()


def update_default_voice(provider: str, voice_id: str, speed: float, sentence_pause_sec: float) -> None:
    set_key(ENV_FILE_PATH, "APP_DEFAULT_VOICE_PROVIDER", provider)
    set_key(ENV_FILE_PATH, "APP_DEFAULT_VOICE_ID", voice_id)
    set_key(ENV_FILE_PATH, "APP_DEFAULT_VOICE_SPEED", str(speed))
    set_key(ENV_FILE_PATH, "APP_DEFAULT_SENTENCE_PAUSE_SEC", str(sentence_pause_sec))
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


def update_google_oauth_client_id(value: str) -> None:
    set_key(ENV_FILE_PATH, "APP_GOOGLE_OAUTH_CLIENT_ID", value)
    get_settings.cache_clear()


def update_google_oauth_client_secret(value: str) -> None:
    set_key(ENV_FILE_PATH, "APP_GOOGLE_OAUTH_CLIENT_SECRET", value)
    get_settings.cache_clear()


def update_youtube_redirect_uri(uri: str) -> None:
    set_key(ENV_FILE_PATH, "APP_YOUTUBE_REDIRECT_URI", uri)
    get_settings.cache_clear()
