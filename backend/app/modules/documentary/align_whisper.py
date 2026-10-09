"""Local word-timestamp provider: faster-whisper on CPU (int8).

Used only when the TTS engine gave no (or poor) word stamps. The model is
loaded lazily and cached per process; it downloads on first use. Whisper's
transcript can be imperfect, which is fine -- it is aligned to the known
script text afterwards (see alignment.py), and weak matches are flagged.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.documentary.tts import WordStamp

logger = logging.getLogger(__name__)

_MODELS: dict[str, object] = {}
_VALID_SIZES = ("tiny", "base", "small", "medium", "large-v3")


def is_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _model(size: str):
    if size not in _VALID_SIZES:
        raise ValidationError(f"Model Whisper không hợp lệ: {size!r} (dùng một trong {', '.join(_VALID_SIZES)}).")
    if size not in _MODELS:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ValidationError("Chưa cài faster-whisper: chạy `pip install faster-whisper`.") from exc
        try:
            logger.info("Loading faster-whisper model %r (first use downloads it)...", size)
            _MODELS[size] = WhisperModel(size, device="cpu", compute_type="int8")
        except Exception as exc:  # noqa: BLE001 -- download/IO errors surface as one clear message
            raise ExternalServiceError(f"Không tải/khởi tạo được model Whisper '{size}': {type(exc).__name__}") from exc
    return _MODELS[size]


def transcribe_words(audio_path: Path, *, language: str = "vi", prompt: str | None = None) -> list[WordStamp]:
    size = get_settings().documentary_whisper_model
    model = _model(size)
    try:
        segments, _info = model.transcribe(
            str(audio_path), language=language, word_timestamps=True, beam_size=1,
            initial_prompt=prompt[:600] if prompt else None, condition_on_previous_text=False,
        )
        stamps = [
            WordStamp(w.word.strip(), float(w.start), float(w.end))
            for seg in segments
            for w in (seg.words or [])
            if w.word.strip()
        ]
    except Exception as exc:  # noqa: BLE001
        raise ExternalServiceError(f"Whisper thất bại khi xử lý {audio_path.name}: {type(exc).__name__}") from exc
    return stamps
