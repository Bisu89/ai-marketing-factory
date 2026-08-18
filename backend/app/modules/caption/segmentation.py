"""Deterministic script -> caption-segment splitting (Task 25 sections
5-13, 16, 29). Pure, no I/O -- mirrors app.modules.voice.timing's own
weighted-estimate + minimum-duration-rebalance + gapless-stitch shape
(section 11: "use Beat timing + text segmentation", the same established
pattern this codebase already trusts for Beat-level timing, applied here
one level down: splitting a *single Beat's* narration text into smaller,
sub-Beat-windowed caption segments).

No ASR, no per-word timestamps -- this operates purely on the Beat's own
absolute [start, end] window (set by Task 22's Voice stage) and the
Beat's own narration text (section 16: "use the final Script text... if
the user manually edited it, that edit is authoritative" -- Beat.narration
already *is* that authoritative text, nothing here re-derives it from an
older AI response).
"""

import re

from app.modules.caption.schemas import (
    CAPTION_TIMING_INVALID,
    CaptionError,
    CaptionSegment,
    CaptionSegmentationConfig,
)

# Matches app.modules.voice.timing's own weighting constants exactly (same
# "a sentence-ending mark implies a longer natural pause than a comma"
# reasoning, section 13) -- duplicated, not imported (module isolation).
_SENTENCE_END_WEIGHT = 1.5
_COMMA_WEIGHT = 0.5
_SENTENCE_END_CHARS = (".", "!", "?")
_PHRASE_BREAK_CHARS = (",", ":", ";")

_WHITESPACE_RE = re.compile(r"\s+")
# Control characters (except the whitespace already normalized above) --
# section 17's own "invalid line breaks / unsupported control characters"
# must never reach the ASS file raw.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_caption_text(text: str) -> str:
    """Section 17: whitespace/control-character cleanup only -- never
    rewrites wording. Collapses any run of whitespace (including literal
    newlines pasted into a manually-edited script) to a single space, and
    strips control characters ASS/ffmpeg can't render safely.
    """
    text = _CONTROL_CHAR_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _weight_for_text(text: str) -> float:
    word_count = len(text.split())
    sentence_ends = sum(text.count(c) for c in _SENTENCE_END_CHARS)
    commas = sum(text.count(c) for c in _PHRASE_BREAK_CHARS)
    weight = word_count + sentence_ends * _SENTENCE_END_WEIGHT + commas * _COMMA_WEIGHT
    return max(weight, 1.0)


def _split_long_chunk_by_words(words: list[str], max_words: int, max_chars: int) -> list[list[str]]:
    """Hard fallback (section 6: "avoid extremely tiny captions" -- this
    is the last resort, only reached when a phrase between two punctuation
    marks is still too long on its own) -- greedy word-count grouping,
    never splitting a single word.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for word in words:
        added_chars = len(word) if not current else len(word) + 1
        if current and (len(current) >= max_words or current_chars + added_chars > max_chars):
            groups.append(current)
            current = []
            current_chars = 0
            added_chars = len(word)
        current.append(word)
        current_chars += added_chars
    if current:
        groups.append(current)
    return groups


def split_text_into_chunks(text: str, max_words: int, max_chars: int) -> list[str]:
    """Section 5/6: prefer sentence/phrase boundaries over blind word
    splitting. Walks the text word by word, closing the current chunk at
    the *first* sentence-end/phrase-break punctuation once the chunk is
    already non-trivial, or once it would exceed max_words/max_chars
    regardless of punctuation. A single phrase that's still too long on
    its own (no punctuation to break at) falls back to a bounded
    word-count split (never mid-word).
    """
    words = text.split()
    if not words:
        return []

    phrases: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for word in words:
        added_chars = len(word) if not current else len(word) + 1
        current.append(word)
        current_chars += added_chars
        ends_sentence = word.rstrip('"\')]').endswith(_SENTENCE_END_CHARS)
        ends_phrase = word.rstrip('"\')]').endswith(_PHRASE_BREAK_CHARS)
        over_limit = len(current) >= max_words or current_chars > max_chars
        if over_limit or ((ends_sentence or ends_phrase) and len(current) >= 2):
            phrases.append(current)
            current = []
            current_chars = 0
    if current:
        phrases.append(current)

    chunks: list[str] = []
    for phrase in phrases:
        if len(phrase) <= max_words and sum(len(w) for w in phrase) + len(phrase) - 1 <= max_chars:
            chunks.append(" ".join(phrase))
        else:
            for group in _split_long_chunk_by_words(phrase, max_words, max_chars):
                chunks.append(" ".join(group))
    return chunks


def _rebalance_minimum_duration(raw_durations: list[float], total_duration: float, min_duration: float) -> list[float]:
    """Verbatim port of app.modules.voice.timing's own algorithm (section
    9: "if a caption would be shorter than the minimum: rebalance adjacent
    segments... do NOT silently delete the caption") -- duplicated, not
    imported (module isolation).
    """
    n = len(raw_durations)
    if n == 0:
        return []
    if min_duration * n >= total_duration:
        return [total_duration / n] * n

    durations = list(raw_durations)
    for _ in range(n):
        below = [i for i, d in enumerate(durations) if d < min_duration]
        if not below:
            break
        deficit = sum(min_duration - durations[i] for i in below)
        above = [i for i in range(n) if i not in below]
        above_total = sum(durations[i] for i in above)
        if above_total <= 0:
            return [total_duration / n] * n
        for i in below:
            durations[i] = min_duration
        for i in above:
            durations[i] -= deficit * (durations[i] / above_total)
    return durations


def split_beat_into_segments(
    beat_id: str, text: str, start: float, end: float, config: CaptionSegmentationConfig,
) -> list[CaptionSegment]:
    """Section 11/12/15: one Beat's narration -> N caption segments, each
    strictly inside [start, end] (section 15's own "caption.start >=
    beat.start, caption.end <= beat.end"), weighted-distributed like
    app.modules.voice.timing.compute_beat_timing (word count + punctuation
    pause weight), then rebalanced for min_duration and capped at
    max_duration (section 10: a segment given more idle time than
    max_duration_sec by the weighted split is capped there, leaving a
    trailing gap rather than an oversized on-screen block -- section 14's
    own "small gaps are acceptable if intentional").

    Raises CaptionError(CAPTION_TIMING_INVALID) for a non-positive Beat
    window. Returns [] for blank/whitespace-only text (section 31: nothing
    to caption, not an error -- the Quality Gate's own MISSING_NARRATION
    already covers a beat with no narration at all).
    """
    normalized = normalize_caption_text(text or "")
    if not normalized:
        return []

    duration = end - start
    if duration <= 0:
        raise CaptionError(CAPTION_TIMING_INVALID, f"Beat {beat_id} has a non-positive timing window ({start}..{end}).")

    chunks = split_text_into_chunks(normalized, config.max_words, config.max_chars)
    if not chunks:
        return []

    weights = [_weight_for_text(c) for c in chunks]
    total_weight = sum(weights)
    raw_durations = [w / total_weight * duration for w in weights]

    min_duration = min(config.min_duration_sec, duration / len(chunks))
    durations = _rebalance_minimum_duration(raw_durations, duration, min_duration)
    # Cap after rebalancing (section 10) -- never below the just-enforced
    # minimum (already guaranteed <= max_duration_sec in any realistic
    # config; MAX_CAPTION checked at the config layer keeps min <= max).
    durations = [min(d, config.max_duration_sec) for d in durations]

    segments: list[CaptionSegment] = []
    cursor = start
    for i, (chunk, chunk_duration) in enumerate(zip(chunks, durations)):
        seg_start = cursor
        seg_end = min(end, seg_start + chunk_duration)
        segments.append(CaptionSegment(id=f"{beat_id}_c{i + 1}", beat_id=beat_id, start=seg_start, end=seg_end, text=chunk))
        cursor = seg_end
    return segments
