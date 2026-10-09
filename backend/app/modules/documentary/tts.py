"""Text-to-speech backend interface for narration segments.

The module ships only the offline `mock` backend (silence sized from the
text -- for development and tests, never a real voice). Real engines (edge-tts
and ElevenLabs) are registered by a composition root,
app/api/v1/endpoints/documentary_tts.py, because this module may not import
other modules or call providers directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import ValidationError
from app.modules.documentary import media

SYLLABLES_PER_SECOND = 3.3  # only for the mock's fake length; real length is always measured


@dataclass(frozen=True)
class WordStamp:
    text: str
    start: float
    end: float


@dataclass
class SynthResult:
    path: Path
    chars: int
    model: str
    voice: str
    cost_usd: float | None  # None = price unknown; 0.0 only when the engine is genuinely free
    word_stamps: list[WordStamp] | None = None


class TTSBackend(ABC):
    name: str
    extension: str = ".mp3"
    paid: bool = False  # paid backends need an explicit confirmation before a batch runs

    @abstractmethod
    def fingerprint(self) -> str:
        """Everything that changes the sound (engine, voice, model, settings).
        Part of the cache key: change it and every segment is regenerated."""

    def estimate_cost(self, chars: int) -> float | None:
        return None

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> SynthResult: ...


class MockTTSBackend(TTSBackend):
    name = "mock"
    extension = ".wav"

    def fingerprint(self) -> str:
        return "mock:v1"

    def estimate_cost(self, chars: int) -> float | None:
        return 0.0

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        seconds = max(0.5, len(text.split()) / SYLLABLES_PER_SECOND)
        media.make_silence(out_path, seconds)
        return SynthResult(path=out_path, chars=len(text), model="mock", voice="silence", cost_usd=0.0)


_REGISTRY: dict[str, TTSBackend] = {"mock": MockTTSBackend()}


def register_backend(backend: TTSBackend) -> None:
    _REGISTRY[backend.name] = backend


def get_backend(name: str) -> TTSBackend:
    b = _REGISTRY.get(name)
    if b is None:
        raise ValidationError(
            f"Backend giọng đọc '{name}' chưa được cấu hình. Có sẵn: {', '.join(sorted(_REGISTRY))}."
        )
    return b


def available_backends() -> list[str]:
    return sorted(_REGISTRY)
