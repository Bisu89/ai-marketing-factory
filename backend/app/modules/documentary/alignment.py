"""Align the KNOWN narration text to word timestamps.

We already know what was said (the approved script), so this is alignment,
not transcription: a speech recogniser / TTS engine supplies (word, start,
end) stamps that may be misspelled, merged or missing words, and we match
them to the script's own words with a sequence alignment. Script words that
find no counterpart are interpolated between their matched neighbours and
flagged, so a weak match is visible instead of silently trusted.

ffprobe is NOT involved here: it only measures a file's duration.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.modules.documentary.tts import WordStamp

_PUNCT = re.compile(r"[^\w]+", re.UNICODE)


@dataclass
class AlignedWord:
    text: str
    start: float
    end: float
    matched: bool  # False = interpolated, no real timestamp backed this word


def tokens(text: str) -> list[str]:
    return text.split()


def fold(word: str) -> str:
    """Case-, punctuation- and diacritic-insensitive key, so 'Constantinople,'
    matches 'constantinople' and a recogniser's dropped Vietnamese tone mark
    does not break the match."""
    w = unicodedata.normalize("NFD", word.lower().replace("đ", "d"))
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return _PUNCT.sub("", w)


def align_words(script_words: list[str], stamps: list[WordStamp], total_sec: float) -> list[AlignedWord]:
    """-> one AlignedWord per script word, in script order, monotonic in time
    and clipped to [0, total_sec]."""
    n = len(script_words)
    if n == 0:
        return []
    a = [fold(w) for w in script_words]
    b = [fold(s.text) for s in stamps]
    start: list[float | None] = [None] * n
    end: list[float | None] = [None] * n
    matched = [False] * n
    if stamps:
        for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
            for k in range(block.size):
                start[block.a + k] = stamps[block.b + k].start
                end[block.a + k] = stamps[block.b + k].end
                matched[block.a + k] = True

    # Interpolate each run of unmatched words between its matched neighbours.
    i = 0
    while i < n:
        if start[i] is not None:
            i += 1
            continue
        j = i
        while j < n and start[j] is None:
            j += 1
        lo = end[i - 1] if i > 0 and end[i - 1] is not None else 0.0
        hi = start[j] if j < n and start[j] is not None else total_sec
        hi = max(hi, lo)
        span = (hi - lo) / (j - i)
        for k in range(i, j):
            start[k] = lo + span * (k - i)
            end[k] = lo + span * (k - i + 1)
        i = j

    out, prev_end = [], 0.0
    for k in range(n):
        s = min(max(float(start[k]), prev_end), total_sec)
        e = min(max(float(end[k]), s), total_sec)
        out.append(AlignedWord(script_words[k], round(s, 3), round(e, 3), matched[k]))
        prev_end = s  # monotonic starts; overlap of ends is tidied by the caller
    return out


def coverage(words: list[AlignedWord]) -> float:
    return sum(1 for w in words if w.matched) / len(words) if words else 0.0


def estimated_words(script_words: list[str], total_sec: float) -> list[AlignedWord]:
    """Last-resort timing: spread words over the audio by length. Every word
    is flagged unmatched -- this is a guess and is reported as one."""
    n = len(script_words)
    if n == 0:
        return []
    weights = [len(fold(w)) + 1 + (3 if w.endswith((".", "!", "?", "…")) else 1 if w.endswith(",") else 0) for w in script_words]
    total = float(sum(weights))
    out, t = [], 0.0
    for w, wt in zip(script_words, weights):
        d = total_sec * wt / total
        out.append(AlignedWord(w, round(t, 3), round(t + d, 3), False))
        t += d
    return out


_SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")


def split_subtitle_chunks(words: list[AlignedWord], max_chars: int = 84) -> list[list[AlignedWord]]:
    """Group words into subtitle lines: break at sentence ends, and split any
    chunk longer than max_chars at a comma (or the word nearest its middle)."""
    chunks: list[list[AlignedWord]] = []
    cur: list[AlignedWord] = []
    for w in words:
        cur.append(w)
        if _SENTENCE_END.search(w.text):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out: list[list[AlignedWord]] = []
    for ch in chunks:
        out.extend(_split_long(ch, max_chars))
    return out


def _split_long(chunk: list[AlignedWord], max_chars: int) -> list[list[AlignedWord]]:
    text_len = sum(len(w.text) + 1 for w in chunk) - 1
    if text_len <= max_chars or len(chunk) < 4:
        return [chunk]
    mid = len(chunk) // 2
    cut = min(
        (k for k in range(2, len(chunk) - 1) if chunk[k - 1].text.endswith(",")),
        key=lambda k: abs(k - mid),
        default=mid,
    )
    return _split_long(chunk[:cut], max_chars) + _split_long(chunk[cut:], max_chars)
