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
import re
import shutil
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

# Real user report: narration synthesized as one unbroken pass (the
# original behavior of both providers below) reads as flat/monotone
# regardless of voice choice, because there is no breath between
# sentences at all -- neither SAPI5 nor edge_tts inserts one on its own
# when handed one long string. Both providers now split narration into
# sentences and synthesize each separately, then splice them back
# together with a real, silent gap of this length -- a natural
# inter-sentence pause length in human speech, short enough to still
# read as one continuous narration. Hand-tunable, not user-configurable
# (a pure audio-quality constant, not a product decision) -- see
# _split_sentences/_concat_wav_with_pauses below.
_INTER_SENTENCE_PAUSE_SEC = 0.35

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")

# Real production report: a full multi-beat script (15-30+ sentences is
# normal) synthesized one edge_tts network call per sentence took 5-10+
# minutes end to end once the free service's own real, confirmed
# flakiness kicked in (near-every segment needing a retry during one
# live run) -- each retry adds real backoff seconds, and that multiplies
# across every sentence with no cap. A real video's *beats* (a handful
# per video, not "one per sentence") are the natural pacing unit anyway,
# so segments are capped here and adjacent sentences merged evenly when
# a script has more sentences than this -- bounds worst-case wall-clock
# time regardless of script length, at the cost of skipping a pause
# between two sentences inside the same merged segment on longer scripts.
_MAX_TTS_SEGMENTS = 8


def _split_sentences(text: str) -> list[str]:
    """Deliberately simple punctuation-based splitting, not real NLP
    sentence segmentation -- good enough for narration scripts (short,
    plain sentences), and a mis-split only ever moves a pause to a
    slightly different spot, never breaks correctness. Always returns at
    least one segment (the original text) so callers never need a
    separate empty-list case. Capped at _MAX_TTS_SEGMENTS -- see that
    constant's own comment.
    """
    stripped = text.strip()
    if not stripped:
        return [stripped]
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()]
    if not sentences:
        return [stripped]
    return _cap_segment_count(sentences, _MAX_TTS_SEGMENTS)


def _cap_segment_count(sentences: list[str], max_segments: int) -> list[str]:
    if len(sentences) <= max_segments:
        return sentences
    # Evenly distribute sentences across exactly max_segments groups (the
    # last groups absorb one extra sentence each when it doesn't divide
    # evenly), then join each group back into one segment.
    n = len(sentences)
    base, extra = divmod(n, max_segments)
    groups: list[list[str]] = []
    i = 0
    for g in range(max_segments):
        size = base + (1 if g >= max_segments - extra else 0)
        groups.append(sentences[i:i + size])
        i += size
    return [" ".join(g) for g in groups if g]


# A tiny buffer kept after a segment's real last spoken word (when we know
# where that is -- see EdgeTTSProvider) so trimming trailing silence never
# clips the word's own natural decay.
_TRAILING_WORD_BUFFER_SEC = 0.08


def _concat_wav_with_pauses(segments: list[tuple[Path, float | None]], pause_sec: float, output_path: Path) -> None:
    """Stitches already-synthesized WAV segments into one file with a real
    silent gap between each pair -- pure stdlib `wave`, no ffmpeg needed
    (this codebase already reads WAV headers this way, see _probe_wav).

    Each entry is (wav_path, trim_to_duration_sec | None). Confirmed while
    building this feature: edge_tts's own per-request output carries a
    real, inconsistent amount of trailing silence after the last spoken
    word -- up to ~0.85s on some segments, ~0.1s on others, from real
    measurement -- which would otherwise stack unpredictably on top of
    `pause_sec` and make the gap between sentences wildly inconsistent
    (observed 0.2s-1.3s in testing before this trim was added). Passing a
    trim duration (EdgeTTSProvider does, from its own real WordBoundary
    data; LocalTTSProvider passes None, SAPI5 exposes no such data) makes
    the actual gap length `pause_sec`, precisely, every time.

    All segments must share the same format (they do here: same provider,
    same voice/settings, produced back-to-back in one synthesize() call);
    a mismatch is a real bug upstream, so this raises rather than
    silently producing garbled audio.
    """
    paths = [p for p, _ in segments]
    with wave.open(str(paths[0]), "rb") as first:
        params = first.getparams()

    for seg_path in paths[1:]:
        with wave.open(str(seg_path), "rb") as seg:
            seg_params = seg.getparams()
        if (seg_params.framerate, seg_params.sampwidth, seg_params.nchannels) != (
            params.framerate, params.sampwidth, params.nchannels,
        ):
            raise VoiceError(
                TTS_GENERATION_FAILED,
                f"TTS segments have inconsistent audio formats ({seg_path.name} vs {paths[0].name}) -- cannot splice.",
            )

    silence_frames = max(0, round(pause_sec * params.framerate))
    silence_bytes = b"\x00" * (silence_frames * params.sampwidth * params.nchannels)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as out:
        out.setparams(params)
        for i, (seg_path, trim_to) in enumerate(segments):
            with wave.open(str(seg_path), "rb") as seg:
                total_frames = seg.getnframes()
                frames_to_write = total_frames
                if trim_to is not None:
                    frames_to_write = min(total_frames, max(0, round(trim_to * params.framerate)))
                out.writeframes(seg.readframes(frames_to_write))
            if i < len(segments) - 1:
                out.writeframes(silence_bytes)


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

    def _speak_one(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> None:
        import pyttsx3

        engine = pyttsx3.init()
        try:
            resolved_voice = LocalTTSProvider._resolve_voice(engine, voice_id, language)
            engine.setProperty("voice", resolved_voice)
            rate = max(_MIN_RATE_WPM, min(_MAX_RATE_WPM, round(_BASE_RATE_WPM * speed)))
            engine.setProperty("rate", rate)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
        finally:
            engine.stop()

    def _synthesize_now(self, text: str, voice_id: str, language: str, speed: float, output_path: Path) -> AudioResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sentences = _split_sentences(text)

        if len(sentences) <= 1:
            # Single sentence (or empty/degenerate text) -- unchanged
            # one-shot path, no segments/pauses to insert.
            self._speak_one(text, voice_id, language, speed, output_path)
        else:
            import pythoncom

            tmp_dir = output_path.parent / f".{output_path.stem}_segments"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            try:
                segment_paths = []
                for i, sentence in enumerate(sentences):
                    seg_path = tmp_dir / f"seg_{i:03d}.wav"
                    # A full CoUninitialize/CoInitialize cycle -- not just a
                    # fresh pyttsx3.init() -- between every segment.
                    # Confirmed by real, guarded testing while building this
                    # feature: SAPI5's "save to file" driver mode gets stuck
                    # after one runAndWait() completes and a SECOND call
                    # hangs indefinitely, even with a brand-new engine
                    # instance in the same COM apartment; only tearing the
                    # apartment down and rebuilding it between calls (safe
                    # here even nested inside _run()'s own thread-lifetime
                    # CoInitialize -- COM reference-counts these per thread)
                    # actually resets it. This is a different bug from the
                    # multi-THREAD deadlock _TTSWorker's own docstring
                    # already documents; that fix (one dedicated thread)
                    # does not, by itself, cover this one.
                    pythoncom.CoUninitialize()
                    pythoncom.CoInitialize()
                    self._speak_one(sentence, voice_id, language, speed, seg_path)
                    segment_paths.append(seg_path)
                # SAPI5 exposes no word-boundary data, so there's no real
                # last-word position to trim to -- None means "use the
                # segment's own full length" (see _concat_wav_with_pauses's
                # own docstring).
                _concat_wav_with_pauses([(p, None) for p in segment_paths], _INTER_SENTENCE_PAUSE_SEC, output_path)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

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
        sentences = _split_sentences(text)

        async def _generate_segment_once(segment_text: str, tmp_mp3: Path) -> list[WordTiming]:
            communicate = edge_tts.Communicate(segment_text, resolved_voice, rate=rate_str, boundary="WordBoundary")
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

        # edge_tts's underlying WebSocket connection to Microsoft's (free,
        # unofficial) service is genuinely flaky under back-to-back requests
        # -- confirmed during this change's own verification: splitting one
        # script into N per-sentence calls (necessary for real inter-sentence
        # pauses, see _INTER_SENTENCE_PAUSE_SEC above) turns one network call
        # into N, and real testing showed an intermittent NoAudioReceived
        # failure roughly every few consecutive calls, unrelated to the text
        # content itself. A single script-wide call (the pre-existing
        # behavior, still used below when there's only one sentence) rarely
        # hit this simply by making far fewer calls. Retrying the SAME
        # segment a few times with backoff is the standard, necessary
        # mitigation for an unofficial API like this -- without it, this
        # change would make narration generation measurably less reliable
        # overall, not just less monotone.
        _SEGMENT_MAX_ATTEMPTS = 4
        _SEGMENT_RETRY_BACKOFF_SEC = 1.5

        async def _generate_segment(segment_text: str, tmp_mp3: Path) -> list[WordTiming]:
            last_exc: Exception | None = None
            for attempt in range(_SEGMENT_MAX_ATTEMPTS):
                try:
                    words = await _generate_segment_once(segment_text, tmp_mp3)
                    if tmp_mp3.exists() and tmp_mp3.stat().st_size > 0:
                        return words
                    last_exc = RuntimeError("edge_tts produced no audio bytes for this segment.")
                except Exception as exc:  # noqa: BLE001 -- retried below regardless of exact edge_tts exception type
                    last_exc = exc
                if attempt < _SEGMENT_MAX_ATTEMPTS - 1:
                    logger.warning(
                        "edge_tts segment synthesis attempt %d/%d failed (%s) -- retrying.",
                        attempt + 1, _SEGMENT_MAX_ATTEMPTS, last_exc,
                    )
                    await asyncio.sleep(_SEGMENT_RETRY_BACKOFF_SEC * (attempt + 1))
            raise VoiceError(
                TTS_GENERATION_FAILED,
                f"edge_tts synthesis failed after {_SEGMENT_MAX_ATTEMPTS} attempts: {last_exc}",
            )

        if len(sentences) <= 1:
            # Single sentence (or empty/degenerate text) -- unchanged
            # one-shot path, no segments/pauses to insert.
            tmp_mp3 = output_path.with_suffix(".mp3")
            words = asyncio.run(_generate_segment(text, tmp_mp3))
            # Convert to this pipeline's own canonical WAV container
            # immediately (never leave an MP3 as the provider's own
            # "output_path" artifact -- audio_analysis.normalize_audio does
            # the *format* normalization afterward regardless of provider,
            # this is just "give the caller a real, readable file at the
            # path it asked for").
            _convert_to_wav(tmp_mp3, output_path)
            tmp_mp3.unlink(missing_ok=True)
        else:
            tmp_dir = output_path.parent / f".{output_path.stem}_segments"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            try:
                segments: list[tuple[Path, float | None]] = []
                all_words: list[WordTiming] = []
                offset_sec = 0.0
                for i, sentence in enumerate(sentences):
                    tmp_mp3 = tmp_dir / f"seg_{i:03d}.mp3"
                    tmp_wav = tmp_dir / f"seg_{i:03d}.wav"
                    segment_words = asyncio.run(_generate_segment(sentence, tmp_mp3))
                    _convert_to_wav(tmp_mp3, tmp_wav)
                    seg_duration, _, _ = _probe_wav(tmp_wav)

                    # Trim this segment's own trailing silence (see
                    # _concat_wav_with_pauses's own docstring for why --
                    # confirmed by real measurement, edge_tts pads this
                    # inconsistently, up to ~0.85s on some segments) so the
                    # actual gap heard between sentences is always
                    # _INTER_SENTENCE_PAUSE_SEC, not that plus a random
                    # extra padding amount.
                    trim_to = seg_duration
                    if segment_words:
                        trim_to = min(seg_duration, segment_words[-1].end + _TRAILING_WORD_BUFFER_SEC)

                    all_words.extend(
                        WordTiming(text=w.text, start=w.start + offset_sec, end=w.end + offset_sec)
                        for w in segment_words
                    )
                    segments.append((tmp_wav, trim_to))
                    is_last = i == len(sentences) - 1
                    offset_sec += trim_to + (0.0 if is_last else _INTER_SENTENCE_PAUSE_SEC)

                _concat_wav_with_pauses(segments, _INTER_SENTENCE_PAUSE_SEC, output_path)
                words = all_words
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

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
