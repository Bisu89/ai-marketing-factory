"""Synthesized sound effects for optional scene-cut cues ($0, no samples -- generated from scratch,
so no licensing risk and no new paid service). Ported technique from a sibling Remotion skill's
`gen_audio.py` (read manually, not imported -- see docs/documentary/PORTING_NOTES.md part A).

Off by default (`RenderParams.sfx_enabled`). When on, each scene whose (pre-existing, previously
unused) `sfx_cues` hint text is non-empty gets exactly one short effect, picked by matching that
text against a small fixed catalog -- never a sound the user didn't ask for, and never silently
dropped just because the hint names no recognised style (it falls back to a neutral "whoosh").

Dependency note: the reference script uses numpy + scipy (Butterworth filters via
`scipy.signal.butter`). This repo's venv already has numpy (pulled in transitively by
faster-whisper/ctranslate2) but not scipy, so this module uses numpy only, with a plain one-pole
IIR low/high-pass standing in for Butterworth -- plenty for a < 2s noise-based transition cue.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000  # matches media.SAMPLE_RATE / the project's own final mux rate
STYLES: tuple[str, ...] = ("whoosh", "impact", "stinger", "wind")
# Bump when the synthesis changes, so a stale cached WAV from the old algorithm is never reused.
SFX_VERSION = 1

# English + Vietnamese keywords a free-text hint is matched against (case-insensitive substring).
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "whoosh": ("whoosh", "swoosh", "swish", "lướt", "vút"),
    "impact": ("impact", "thud", "hit", "boom", "va đập", "đập", "bùm", "rơi"),
    "stinger": ("sting", "stinger", "chord", "dramatic", "nhấn", "kịch tính", "bất ngờ"),
    "wind": ("wind", "drone", "ambient", "gió", "rền", "u ám", "căng thẳng"),
}


def match_style(hint: str) -> str:
    """The catalog style a free-text hint (e.g. "gió lướt, kịch tính") most plausibly means. Falls
    back to "whoosh" -- a neutral transition cue -- for any non-empty hint that names no known
    style, so a hint the user already typed always produces *some* cue."""
    low = hint.lower()
    for style, words in _KEYWORDS.items():
        if any(w in low for w in words):
            return style
    return "whoosh"


# ---- synthesis (numpy only -- see module docstring) --------------------------------------------
def _noise(seconds: float, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, int(seconds * SR))


def _lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    """One-pole IIR lowpass. Intentionally simple (no scipy/Butterworth): good enough for a short
    noise-based SFX, not a mixing-console filter."""
    a = float(np.exp(-2 * np.pi * cutoff_hz / SR))
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def _highpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    return x - _lowpass(x, cutoff_hz)


def _bandpass(x: np.ndarray, lo_hz: float, hi_hz: float) -> np.ndarray:
    return _lowpass(_highpass(x, lo_hz), hi_hz)


def _env(n: int, attack: float, decay_curve: float) -> np.ndarray:
    t = np.arange(n) / SR
    na = max(1, int(attack * SR))
    e = np.exp(-decay_curve * t / max(n / SR, 1e-6))
    e[:na] *= np.linspace(0.0, 1.0, na)
    return e


def _chirp(f0: float, f1: float, seconds: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    k = np.log(f1 / f0) / seconds
    phase = 2 * np.pi * f0 * (np.exp(k * t) - 1) / k
    return np.sin(phase)


def _normalize(x: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return x / m * peak if m else x


def _render(style: str, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if style == "whoosh":
        d = 0.45
        n = _noise(d, rng)
        half = len(n) // 2
        sweep = np.concatenate([_lowpass(n[:half], 3200.0), _lowpass(n[half:], 900.0)])
        bell = np.concatenate([np.linspace(0, 1, half), np.linspace(1, 0, len(sweep) - half)])
        x = sweep * bell
    elif style == "impact":
        d = 0.7
        boom = _chirp(130.0, 35.0, d) * _env(int(d * SR), 0.002, 4.0)
        crack = _bandpass(_noise(0.22, rng), 300.0, 3200.0) * _env(int(0.22 * SR), 0.001, 7.0)
        x = np.zeros(int(d * SR))
        x[: len(boom)] += boom
        x[: len(crack)] += crack * 0.8
    elif style == "stinger":
        d = 1.1
        t = np.arange(int(d * SR)) / SR
        chord = sum(np.sin(2 * np.pi * f * t) for f in (110.0, 164.8, 220.0, 261.6)) / 4
        chord = chord * _env(len(t), 0.004, 3.0)
        crack = _bandpass(_noise(0.4, rng), 2000.0, SR / 2 - 100) * _env(int(0.4 * SR), 0.002, 5.0)
        x = chord * 0.7
        x[: len(crack)] += crack * 0.35
    elif style == "wind":
        d = 1.6
        x = _bandpass(_noise(d, rng), 120.0, 900.0)
        t = np.arange(len(x)) / SR
        x = x * (0.6 + 0.4 * np.sin(2 * np.pi * 0.6 * t))
        fade = int(0.3 * SR)
        x[:fade] *= np.linspace(0, 1, fade)
        x[-fade:] *= np.linspace(1, 0, fade)
    else:
        raise ValueError(f"unknown SFX style: {style!r} (expected one of {STYLES})")
    return _normalize(x)


def _write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def ensure_catalog(cache_dir: Path) -> dict[str, Path]:
    """One deterministic WAV per style, generated once and reused by every project (same seed =>
    same file every time, so repeated renders stay cache-stable). Shared across projects on purpose
    -- it's a fixed catalog, not project-specific content."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for style in STYLES:
        path = cache_dir / f"{style}_v{SFX_VERSION}.wav"
        if not path.is_file():
            _write_wav(path, _render(style))
        out[style] = path
    return out
