"""Chinese Drama -> Vietnamese Shorts: the composition-root adapter between
app.modules.ai (transcribe_client + llm_client) and app.modules.video_composer.
Per app/modules/README.md, no module may import another module -- video_composer
must not import app.modules.ai (or vice versa); this file is the one place
allowed to import both, the same "composition root" role
composition_render.py already plays for BeatRenderer (see that module's own
docstring for the precedent).

The real implementation of video_composer.service.DubGenerator -- given one
uploaded Chinese-language video clip, produces a Vietnamese translation +
title + hook via ASR (OpenAI, always -- no other configured provider has a
transcription API) then a structured LLM call (provider-agnostic: whichever
of Claude/OpenAI the user already has configured for text generation).
"""

import json
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AICredentials, AIProviderError, call_structured, resolve_ai_credentials
from app.modules.ai.transcribe_client import TranscribeError, extract_audio_track, transcribe_audio

logger = logging.getLogger(__name__)

# Change here only -- nowhere else references this value directly. The
# default TTS voice/rate for this mode live in video_composer/router.py
# instead (this file has nothing to do with TTS -- that runs later, on the
# worker, well after generate_dub returns).
DUB_ASR_LANGUAGE = "zh"

TITLE_MIN_CHARS = 35
TITLE_MAX_CHARS = 55
HOOK_MAX_WORDS = 12

MAX_TOKENS = 2048
MAX_RETRIES = 1  # one bounded repair attempt -- matches beat_generate.py's own convention


@dataclass
class DubResult:
    translation: str
    title: str
    hook: str


OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "translation": {"type": "string"},
            "title": {"type": "string"},
            "hook": {"type": "string"},
        },
        "required": ["translation", "title", "hook"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "Bạn là biên tập viên video Shorts/TikTok, chuyển thoại phim Trung Quốc sang tiếng Việt.\n\n"
    "translation:\n"
    "- Tiếng Việt tự nhiên.\n"
    "- Văn nói.\n"
    "- Dễ nghe khi đọc bằng TTS.\n"
    "- Ngắn gọn.\n"
    "- Giữ đúng ý gốc.\n"
    "- Không dịch máy móc.\n\n"
    f"title:\n"
    f"- {TITLE_MIN_CHARS}–{TITLE_MAX_CHARS} ký tự.\n"
    "- Không nhắc tên phim.\n"
    "- Không dùng \"cảnh phim\".\n"
    "- Không dùng \"trích đoạn\".\n"
    "- Không dùng \"full\".\n"
    "- Tạo tò mò.\n"
    "- Không spoil quá mức.\n"
    "- Tự nhiên như tiêu đề Shorts.\n\n"
    f"hook:\n"
    f"- Tối đa {HOOK_MAX_WORDS} từ.\n"
    "- Gây tò mò.\n"
    "- Ngắn.\n"
    "- Phù hợp Shorts/TikTok.\n"
    "- Phải dựa trên nội dung thực tế.\n"
    "- Không bịa tình tiết.\n\n"
    "Chỉ trả JSON.\n"
    "Không markdown.\n"
    "Không giải thích."
)


def _validate_dub_result(parsed: dict) -> DubResult:
    translation = str(parsed["translation"]).strip()
    title = str(parsed["title"]).strip()
    hook = str(parsed["hook"]).strip()

    if not translation:
        raise ValueError("translation must not be empty")
    if not (TITLE_MIN_CHARS <= len(title) <= TITLE_MAX_CHARS):
        raise ValueError(f"title is {len(title)} characters, must be {TITLE_MIN_CHARS}-{TITLE_MAX_CHARS}")
    hook_word_count = len(hook.split())
    if hook_word_count == 0 or hook_word_count > HOOK_MAX_WORDS:
        raise ValueError(f"hook has {hook_word_count} words, must be 1-{HOOK_MAX_WORDS}")

    return DubResult(translation=translation, title=title, hook=hook)


def _call_and_validate(credentials: AICredentials, transcript: str, repair_note: str | None) -> DubResult:
    system_prompt = SYSTEM_PROMPT
    if repair_note:
        system_prompt += (
            f"\n\nYour previous response was invalid: {repair_note}\n"
            "Fix it and return valid JSON only, respecting all of the constraints above."
        )

    try:
        result = call_structured(
            credentials, system=system_prompt, user_message=transcript,
            output_schema=OUTPUT_SCHEMA, max_tokens=MAX_TOKENS, schema_name="chinese_drama_dub",
        )
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc

    if result.refused:
        raise ExternalServiceError("Request was refused by the model's safety filter.")
    if not result.text:
        raise ExternalServiceError("Model did not return any text content.")

    try:
        parsed = json.loads(result.text)
        return _validate_dub_result(parsed)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"generated JSON did not match the expected contract: {exc}") from exc


def _translate_title_and_hook(settings: Settings, transcript: str) -> DubResult:
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )

    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _call_and_validate(credentials, transcript, repair_note)
        except ValueError as exc:
            logger.warning(
                "Chinese Drama dub-text attempt %d/%d failed validation: %s", attempt + 1, MAX_RETRIES + 1, exc
            )
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not generate a valid translation/title/hook after {MAX_RETRIES + 1} attempts: {last_error}")


def generate_dub(video_path: Path, on_transcribed: Callable[[], None], settings: Settings) -> DubResult:
    """The real video_composer.service.DubGenerator implementation --
    injected into VideoComposerService at construction (see app/main.py,
    which captures `settings` via a closure so this matches DubGenerator's
    own 2-arg call signature). Never called on the HTTP request thread;
    this runs on the job's own worker thread
    (VideoComposerService._run_dub_generation_phase), so a slow ASR/LLM
    call never blocks the upload response.

    `settings` is an explicit param (not read via a global get_settings()
    call internally) so tests can pass a fabricated Settings directly --
    same reasoning beat_generate.py's own generate_beat_plan(credentials, ...)
    takes credentials as a param rather than resolving them itself.
    """
    if not settings.openai_api_key:
        raise ValidationError("No OpenAI API key configured -- add one in Settings to use Chinese Drama mode (ASR requires OpenAI).")

    with tempfile.TemporaryDirectory(prefix="chinese_drama_asr_") as tmp:
        audio_path = Path(tmp) / "audio.mp3"
        try:
            extract_audio_track(video_path, audio_path)
            transcription = transcribe_audio(settings.openai_api_key, audio_path, language=DUB_ASR_LANGUAGE)
        except TranscribeError as exc:
            raise ExternalServiceError(str(exc)) from exc

    on_transcribed()
    return _translate_title_and_hook(settings, transcription.text)
