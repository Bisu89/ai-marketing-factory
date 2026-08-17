"""TTS provider abstraction (Task 22 section 4) -- FactoryPipeline/
voice_generate.py call `TTSProvider.synthesize()` and never know which
engine actually ran. `LocalTTSProvider` (pyttsx3/SAPI5) is the default:
genuinely offline, no API key, no network call during normal operation
(section 1/5). `EdgeTTSProvider` wraps this repo's existing, already-
working `edge_tts` integration (previously only reachable from inside
app.modules.video_composer -- see that module's own `_run_narration`) as
an explicit, non-default alternative (section 41: "if the repository
already has an external TTS client, keep it behind TTSProvider, but do
not require it"). A small, self-contained duplicate of that ~15-line
edge_tts call is intentional here, not an oversight -- app.modules.voice
must never import app.modules.video_composer (module isolation), so this
is the same "duplicate a few lines across a module boundary" convention
app.modules.beat.schemas already uses for BeatMotionPreset.
"""

import asyncio
import logging
import queue
import subprocess
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path

from app.modules.voice.schemas import (
    TTS_GENERATION_FAILED,
    TTS_PROVIDER_UNAVAILABLE,
    AudioResult,
    VoiceError,
    WordTiming,
)

logger = logging.getLogger(__name__)

# SAPI5's own natural rate (words/minute) at speed=1.0 -- pyttsx3's default
# is already ~200; 180 reads as a natural, slightly unhurried narration
# pace for short-form video, matching this app's own "warm/reflective"
# template tones (see beat/schemas.py's ContentProjectConfig defaults).
_BASE_RATE_WPM = 180
_MIN_RATE_WPM = 80
_MAX_RATE_WPM = 400


class _TTSWorker:
    """SAPI5's own COM voice engine hangs indefinitely (not just races --
    a genuine, reproducible deadlock, confirmed during this task's own
    development) when two+ threads call pyttsx3.init()/runAndWait() at
    close to the same moment, even with a fresh CoInitialize'd apartment
    and a plain threading.Lock serializing the actual calls -- the lock
    alone was not enough; the underlying COM/SAPI state itself is not
    safe to touch from more than one OS thread's lifetime, not just one
    critical section at a time. The fix is the same one this codebase
    already uses for its other fragile, must-be-serialized local resource
    (FFmpeg rendering) -- app.modules.video_composer.VideoComposerService's
    own single `queue.Queue` + one dedicated `threading.Thread` -- applied
    here to SAPI5 instead. Every call to LocalTTSProvider.synthesize(),
    from any caller thread (including the Factory Batch Engine's own
    ThreadPoolExecutor workers, Task 20), is handed to this one always-the-
    same worker thread and blocks on a plain `queue.Queue` reply until it
    finishes -- so pyttsx3/SAPI5 is only ever touched by that one thread
    for the lifetime of the process, closing off the deadlock entirely
    rather than trying to out-lock it.
    """

    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True, name="sapi5-tts-worker")
                self._thread.start()

    def _run(self) -> None:
        import pythoncom

        # CoInitialize once for this thread's entire lifetime (not once per
        # job) -- this is now the one and only thread that will ever touch
        # SAPI5 for the rest of the process, so there is no cross-thread
        # apartment churn left to cause the deadlock this class exists to
        # avoid.
        pythoncom.CoInitialize()
        try:
            while True:
                kind, args, reply = self._jobs.get()
                try:
                    if kind == "synthesize":
                        reply.put(("ok", self._synthesize_now(*args)))
                    else:
                        reply.put(("ok", self._list_voices_now()))
                except Exception as exc:  # noqa: BLE001 -- always hand the error back to the caller thread
                    reply.put(("error", exc))
        finally:
            pythoncom.CoUninitialize()  # pragma: no cover -- this loop never returns in practice

    def _synthesize_now(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            resolved_voice = LocalTTSProvider._resolve_voice(engine, voice_id, language)
            engine.setProperty("voice", resolved_voice)
            rate = max(_MIN_RATE_WPM, min(_MAX_RATE_WPM, round(_BASE_RATE_WPM * speed)))
            engine.setProperty("rate", rate)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
        finally:
            engine.stop()

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise VoiceError(TTS_GENERATION_FAILED, "Local TTS produced no audio output.")

        duration_sec, sample_rate, channels = _probe_wav(output_path)
        return AudioResult(
            path=str(output_path), duration_sec=duration_sec, sample_rate=sample_rate, channels=channels,
            word_timestamps=[],  # SAPI5 exposes no reliable, cross-voice word-boundary API -- section 16's fallback tier
        )

    def _list_voices_now(self) -> list[dict]:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            voices = engine.getProperty("voices")
            return [{"id": v.id, "name": v.name, "languages": _decode_languages(v.languages)} for v in voices]
        finally:
            engine.stop()

    def _submit(self, kind: str, args: tuple):
        self._ensure_started()
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._jobs.put((kind, args, reply))
        outcome, value = reply.get()
        if outcome == "error":
            raise value
        return value

    def synthesize(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        return self._submit("synthesize", (text, voice_id, language, speed, output_path))

    def list_voices(self) -> list[dict]:
        return self._submit("list_voices", ())


# One worker for the whole process (see _TTSWorker's own docstring) --
# every LocalTTSProvider instance shares it, matching VideoComposerService's
# own single-worker-thread-per-process shape.
_tts_worker = _TTSWorker()


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        """Writes real, playable audio to `output_path` (any format -- the
        composition root normalizes to the canonical WAV format afterward,
        see audio_analysis.normalize_audio) and returns its own facts about
        what it produced. Must raise VoiceError (never returns a partial/
        placeholder result) on failure.
        """
        raise NotImplementedError


class LocalTTSProvider(TTSProvider):
    """The default provider (section 2/5) -- pyttsx3, which drives the OS's
    own SAPI5 (Windows; this app is Windows-only, see AIContentLibrary.spec's
    winforms/edgechromium bundling) speech engine directly, entirely
    in-process, zero network calls. `voice_id="default"` picks whichever
    voice SAPI5 already has installed for the requested language; a
    specific SAPI5 voice token (as returned by list_voices()) may also be
    passed directly.
    """

    def list_voices(self) -> list[dict]:
        """Real, installed SAPI5 voices -- never a hardcoded list (section
        6's own "do not hardcode voice=... inside the pipeline"). What's
        actually available depends on the end user's own Windows
        installation (see docs/features/48-voice-factory-local-tts.md's
        own honest note on this). Routed through the same single worker
        thread as synthesize() -- see _TTSWorker's own docstring for why a
        second, independent pyttsx3.init() call from this (caller) thread
        while the worker thread might be mid-synthesis is exactly the
        condition that deadlocks SAPI5.
        """
        return _tts_worker.list_voices()

    @staticmethod
    def _resolve_voice(engine, voice_id: str, language: str) -> str:
        voices = engine.getProperty("voices")
        if voice_id and voice_id != "default":
            for v in voices:
                if v.id == voice_id:
                    return v.id
            raise VoiceError(
                TTS_PROVIDER_UNAVAILABLE, f"Local TTS voice {voice_id!r} is not installed on this machine."
            )

        language_prefix = language.split("-")[0].lower()
        for v in voices:
            langs = [lang.lower() for lang in _decode_languages(v.languages)]
            if any(lang.startswith(language_prefix) for lang in langs) or language_prefix in v.id.lower():
                return v.id

        if language_prefix == "en" and voices:
            return voices[0].id

        raise VoiceError(
            TTS_PROVIDER_UNAVAILABLE,
            f"No local SAPI5 voice for language {language!r} is installed on this machine. "
            "Install a matching Windows Speech voice, or choose the edge_tts provider instead.",
        )

    def synthesize(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        try:
            import pythoncom  # noqa: F401 -- import-checked here so a missing pywin32 fails with this module's own stable code
        except ImportError as exc:  # pragma: no cover -- Windows-only dependency
            raise VoiceError(TTS_PROVIDER_UNAVAILABLE, f"pywin32 is not available: {exc}") from exc

        # Delegates to the one dedicated SAPI5 worker thread (see
        # _TTSWorker's own docstring for why this call is never made
        # directly from the caller's own thread) -- from this method's own
        # point of view, still just a plain synchronous call in, AudioResult
        # out.
        try:
            return _tts_worker.synthesize(text, voice_id, language, speed, output_path)
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError(TTS_GENERATION_FAILED, f"Local TTS synthesis failed: {exc}") from exc


class EdgeTTSProvider(TTSProvider):
    """The optional, non-default provider (section 41) -- free but NOT
    offline (a real network call to Microsoft's Edge Read-Aloud service,
    the same one app.modules.video_composer's own `_run_narration` already
    uses at render time for the classic whole-composition TTS path). Kept
    entirely separate from that render-time usage: this class exists so
    the *Voice Factory stage* can optionally use the same free engine
    ahead of rendering, with real word-level timing (section 16 priority 1)
    -- it does not change or replace video_composer's own existing
    behavior in any way.
    """

    def synthesize(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        import edge_tts

        resolved_voice = voice_id if voice_id and voice_id != "default" else _default_edge_voice(language)
        # edge-tts's own rate= syntax: signed percentage relative to 1.0x.
        rate_percent = round((speed - 1.0) * 100)
        rate_str = f"{'+' if rate_percent >= 0 else ''}{rate_percent}%"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_mp3 = output_path.with_suffix(".mp3")

        async def _generate() -> list[WordTiming]:
            communicate = edge_tts.Communicate(text, resolved_voice, rate=rate_str, boundary="WordBoundary")
            words: list[WordTiming] = []
            with open(tmp_mp3, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        words.append(WordTiming(
                            text=chunk["text"], start=chunk["offset"] / 1e7,
                            end=(chunk["offset"] + chunk["duration"]) / 1e7,
                        ))
            return words

        try:
            words = asyncio.run(_generate())
        except Exception as exc:
            raise VoiceError(TTS_GENERATION_FAILED, f"edge_tts synthesis failed: {exc}") from exc

        if not tmp_mp3.exists() or tmp_mp3.stat().st_size == 0:
            raise VoiceError(TTS_GENERATION_FAILED, "edge_tts produced no audio output.")

        # Convert to this pipeline's own canonical WAV container immediately
        # (never leave an MP3 as the provider's own "output_path" artifact --
        # audio_analysis.normalize_audio does the *format* normalization
        # afterward regardless of provider, this is just "give the caller a
        # real, readable file at the path it asked for").
        _convert_to_wav(tmp_mp3, output_path)
        tmp_mp3.unlink(missing_ok=True)

        duration_sec, sample_rate, channels = _probe_wav(output_path)
        return AudioResult(
            path=str(output_path), duration_sec=duration_sec, sample_rate=sample_rate,
            channels=channels, word_timestamps=words,
        )


def get_provider(name: str) -> TTSProvider:
    if name == "local":
        return LocalTTSProvider()
    if name == "edge_tts":
        return EdgeTTSProvider()
    raise VoiceError(TTS_PROVIDER_UNAVAILABLE, f"Unknown TTS provider {name!r} -- expected 'local' or 'edge_tts'.")


def _decode_languages(raw_languages) -> list[str]:
    decoded = []
    for lang in raw_languages or []:
        if isinstance(lang, bytes):
            try:
                decoded.append(lang.decode("utf-8", errors="ignore").strip("\x00"))
            except Exception:
                continue
        else:
            decoded.append(str(lang))
    return decoded


def _default_edge_voice(language: str) -> str:
    # Matches the same small, fixed voice set this app's own frontend
    # already hardcodes (VideoFactoryPage.tsx/VideoComposerPage.tsx) --
    # not duplicated logic, just the one default per language this
    # provider needs when the caller didn't pick a specific voice id.
    defaults = {"en": "en-US-GuyNeural", "es": "es-ES-AlvaroNeural", "vi": "vi-VN-NamMinhNeural", "pt": "pt-BR-AntonioNeural"}
    return defaults.get(language.split("-")[0].lower(), "en-US-GuyNeural")


def _probe_wav(path: Path) -> tuple[float, int, int]:
    """No shared ffmpeg/ffprobe wrapper exists in this codebase by design
    (see composition_render.py's own _probe_audio_duration docstring) --
    for a WAV specifically, Python's stdlib `wave` module reads the header
    directly, no subprocess needed at all.
    """
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        duration = frames / float(rate) if rate else 0.0
    return duration, rate, channels


def _convert_to_wav(source: Path, destination: Path) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(source), str(destination)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not destination.exists():
        raise VoiceError(TTS_GENERATION_FAILED, f"Could not convert synthesized audio to WAV: {result.stderr.strip()}")
