"""OpenAI Audio Transcription API wrapper (Chinese Drama -> Vietnamese
Shorts). Sibling to image_client.py -- same "wrap one SDK resource behind a
small, stable surface, always OpenAI" role, independent of
settings.ai_provider, since no other configured provider has a
transcription API.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import openai

# Change here only -- nowhere else references the transcription model name.
TRANSCRIBE_MODEL = "gpt-4o-transcribe"

# USD per minute of audio. Unconfirmed (no public per-minute pricing page
# for gpt-4o-transcribe this codebase can check today -- OpenAI prices it
# per audio token, not flatly per minute) -- ballparked against whisper-1's
# long-published $0.006/min rate, same "seed with a rough, honestly-labelled
# estimate rather than leave it null" convention app.modules.ai.pricing's
# own module docstring already establishes for claude-sonnet-5/gpt-5.6-luna.
# Update here only once a real rate is confirmed.
TRANSCRIBE_PRICE_PER_MINUTE_USD = 0.006


def estimate_transcription_cost_usd(duration_seconds: float) -> float:
    return round((duration_seconds / 60.0) * TRANSCRIBE_PRICE_PER_MINUTE_USD, 6)


def probe_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise TranscribeError(f"Could not read audio duration for {audio_path}") from exc


class TranscribeError(Exception):
    """Any failure extracting audio from a video or transcribing it."""


@dataclass
class TranscriptionResult:
    text: str
    segments: list[dict]


def extract_audio_track(video_path: Path, output_path: Path) -> None:
    """One ffmpeg subprocess -- strips video, encodes the audio track to a
    small mp3 (keeps the upload to OpenAI's transcription API small).
    Mirrors thumbnail/renderer.py's own `_run_ffmpeg` shape (this module's
    only real subprocess call).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path), "-vn", "-acodec", "libmp3lame", str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise TranscribeError(f"Could not extract audio track from {video_path}: {result.stderr.strip()[-2000:]}")


def transcribe_audio(api_key: str, audio_path: Path, *, language: str) -> TranscriptionResult:
    """Transcribes one audio file. `language` is always passed explicitly
    (never auto-detected) -- a wrong auto-detected language silently
    degrades transcription quality with no visible error, so this mirrors
    generate_beat_image's own "never guess, always pass the real value"
    convention.

    `response_format="json"` -- confirmed via a real API call that
    gpt-4o-transcribe rejects "verbose_json" outright ("response_format
    'verbose_json' is not compatible with model 'gpt-4o-transcribe-...'.
    Use 'json' or 'text' instead"), unlike the older whisper-1 model this
    codebase's own docstrings/specs were written against. That also means
    there is no real per-segment timing available for this model --
    `segments` is always empty; the field is kept on TranscriptionResult
    for shape fidelity, not because this model ever populates it.
    """
    client = openai.OpenAI(api_key=api_key)
    try:
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model=TRANSCRIBE_MODEL, file=f, language=language, response_format="json",
            )
    except openai.APIError as exc:
        raise TranscribeError(str(exc)) from exc

    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise TranscribeError("OpenAI returned an empty transcript.")

    return TranscriptionResult(text=text.strip(), segments=[])
