"""TTS backends for documentary narration (feature 166).

Composition root: the only place joining app.modules.documentary (backend
interface) with app.modules.voice (edge-tts) and the ElevenLabs HTTP API.
Importing this module registers the "edge" and "elevenlabs" backends.

ElevenLabs credentials are read from server-side settings at call time and
are never logged or echoed in an error. The `/with-timestamps` response shape
is parsed defensively; it has NOT been verified against the live API in this
repo (no paid call was made), so a missing alignment simply yields no word
stamps and the local aligner takes over.
"""

import base64
import logging
import time
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.documentary.tts import SynthResult, TTSBackend, WordStamp, register_backend
from app.modules.voice.providers import get_provider as get_voice_provider
from app.modules.voice.schemas import VoiceError

logger = logging.getLogger(__name__)

EDGE_VOICE = "vi-VN-NamMinhNeural"
EDGE_SPEED = 1.0
ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
ELEVEN_OUTPUT_FORMAT = "mp3_44100_128"
ELEVEN_TIMEOUT_SEC = 120.0
ELEVEN_MAX_TRIES = 3
_RETRY_STATUS = {429, 500, 502, 503, 504}


class EdgeBackend(TTSBackend):
    """Free Microsoft Edge voices; returns real per-word timestamps."""

    name = "edge"
    extension = ".wav"

    def fingerprint(self) -> str:
        return f"edge:{EDGE_VOICE}:{EDGE_SPEED:.2f}"

    def estimate_cost(self, chars: int) -> float | None:
        return 0.0

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        try:
            audio = get_voice_provider("edge_tts").synthesize(text, EDGE_VOICE, "vi", EDGE_SPEED, out_path)
        except VoiceError as exc:
            raise ExternalServiceError(f"edge-tts thất bại: {exc}") from exc
        stamps = [WordStamp(w.text, w.start, w.end) for w in audio.word_timestamps] or None
        return SynthResult(path=out_path, chars=len(text), model="edge-tts", voice=EDGE_VOICE, cost_usd=0.0, word_stamps=stamps)


def words_from_char_alignment(chars: list[str], starts: list[float], ends: list[float]) -> list[WordStamp]:
    """Character-level alignment -> word stamps (words split at whitespace)."""
    words: list[WordStamp] = []
    buf, w_start, w_end = [], 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(WordStamp("".join(buf), w_start, w_end))
                buf = []
            continue
        if not buf:
            w_start = s
        buf.append(ch)
        w_end = e
    if buf:
        words.append(WordStamp("".join(buf), w_start, w_end))
    return words


class ElevenLabsBackend(TTSBackend):
    name = "elevenlabs"
    extension = ".mp3"
    paid = True

    @staticmethod
    def _cfg():
        s = get_settings()
        if not s.elevenlabs_api_key or not s.elevenlabs_voice_id:
            raise ValidationError(
                "ElevenLabs chưa được cấu hình: cần API key và voice_id (PUT /settings/elevenlabs)."
            )
        return s

    def fingerprint(self) -> str:
        s = get_settings()
        return (
            f"elevenlabs:{s.elevenlabs_voice_id}:{s.elevenlabs_model_id}:{s.elevenlabs_stability:.2f}:"
            f"{s.elevenlabs_similarity_boost:.2f}:{s.elevenlabs_style:.2f}:{s.elevenlabs_speed:.2f}"
        )

    def estimate_cost(self, chars: int) -> float | None:
        price = get_settings().elevenlabs_usd_per_1k_chars
        return None if price is None else round(chars / 1000.0 * price, 6)

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        s = self._cfg()
        body = {
            "text": text,
            "model_id": s.elevenlabs_model_id,
            "voice_settings": {
                "stability": s.elevenlabs_stability,
                "similarity_boost": s.elevenlabs_similarity_boost,
                "style": s.elevenlabs_style,
                "speed": s.elevenlabs_speed,
            },
        }
        url = ELEVEN_URL.format(voice_id=s.elevenlabs_voice_id)
        last = "không rõ"
        for attempt in range(ELEVEN_MAX_TRIES):
            try:
                r = httpx.post(
                    url, params={"output_format": ELEVEN_OUTPUT_FORMAT}, json=body,
                    headers={"xi-api-key": s.elevenlabs_api_key}, timeout=ELEVEN_TIMEOUT_SEC,
                )
            except httpx.HTTPError as exc:
                last = type(exc).__name__  # class name only: never echo request details
            else:
                if r.status_code == 200:
                    return self._parse(r.json(), text, out_path, s.elevenlabs_model_id, s.elevenlabs_voice_id)
                last = f"HTTP {r.status_code}"
                if r.status_code not in _RETRY_STATUS:
                    break
            if attempt < ELEVEN_MAX_TRIES - 1:
                time.sleep(2.0 * (attempt + 1))
        raise ExternalServiceError(f"ElevenLabs thất bại ({last}).")

    def _parse(self, data: dict, text: str, out_path: Path, model: str, voice: str) -> SynthResult:
        try:
            audio = base64.b64decode(data["audio_base64"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError("ElevenLabs trả về dữ liệu audio không hợp lệ.") from exc
        if not audio:
            raise ExternalServiceError("ElevenLabs trả về audio rỗng.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio)
        stamps = None
        al = data.get("alignment") or data.get("normalized_alignment")
        if isinstance(al, dict):
            try:
                stamps = words_from_char_alignment(
                    al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
                ) or None
            except (KeyError, TypeError):
                stamps = None
        return SynthResult(
            path=out_path, chars=len(text), model=model, voice=voice, cost_usd=self.estimate_cost(len(text)),
            word_stamps=stamps,
        )


register_backend(EdgeBackend())
register_backend(ElevenLabsBackend())
