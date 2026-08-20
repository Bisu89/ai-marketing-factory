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
    CaptionWordTiming,
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


def _real_word_boundaries(
    chunks: list[str], words: list[CaptionWordTiming], start: float, end: float, max_duration_sec: float,
) -> list[tuple[float, float]] | None:
    """Task 62 (see docs/features/62-caption-real-word-timing.md): when
    real, measured per-word timing is available (edge_tts's own
    WordBoundary events, threaded through from the Voice stage -- see
    caption_generate.py), position each chunk against where its own words
    were ACTUALLY spoken instead of a generic weighted-text-length
    estimate. The weighted estimate assumes a uniform words-per-second
    pace across a whole Beat, which real speech never actually keeps
    (natural pauses at commas/sentence-ends are longer than the model
    assumes) -- for a beat with several short, punctuation-heavy clauses
    this compounds into seconds of drift by the end of the beat (a real,
    user-reported bug: a caption could disappear before its own words had
    even started being spoken).

    Returns None (falls back to the weighted estimate below) when the
    supplied words don't correspond 1:1 with the chunks' own word count --
    same "don't trust a mismatched engine tokenization" caution
    app.modules.voice.timing._timing_from_word_timestamps already applies
    at the whole-Beat level, applied here one level down.

    A real edge case found verifying this against a live project: the
    Beat's own official [start, end] (settled by Voice, and possibly
    shifted a few ms by its own min-duration rebalancing/gapless-stitching
    -- see voice.timing._rebalance_minimum_duration/_stitch_contiguous)
    does not always land *exactly* on where this Beat's own real first/
    last word actually starts/ends. Clamping the real timeline hard to
    [start, end] can then invert or collapse the last chunk's own segment
    to a sliver. Instead, the real (gapless-stitched) timeline is
    rescaled -- an affine map from [first real word's start, last real
    word's end] onto [start, end] -- which preserves every real relative
    pause/pace (the actual bug this function exists to fix) while
    guaranteeing every result stays inside the Beat's own authoritative
    window by construction (never escapes it, never inverts).
    """
    expected_counts = [len(c.split()) for c in chunks]
    if not words or len(words) != sum(expected_counts):
        return None

    cursor = 0
    raw: list[tuple[float, float]] = []
    for count in expected_counts:
        chunk_words = words[cursor:cursor + count]
        cursor += count
        raw.append((chunk_words[0].start, chunk_words[-1].end))

    real_start, real_end = raw[0][0], raw[-1][1]
    real_span = max(real_end - real_start, 1e-6)
    scale = (end - start) / real_span

    # Gapless stitch, in the words' own real timeline first (each segment
    # runs from where the previous one ended -- or this Beat's own first
    # real word, for the first -- through to where the NEXT segment's own
    # first real word begins -- or this Beat's own last real word's end,
    # for the last): a natural pause between two clauses is folded into
    # the segment *before* it rather than left as a gap with nothing on
    # screen, and a caption switches at the exact instant the next word
    # starts being spoken.
    stitched: list[tuple[float, float]] = []
    for i in range(len(raw)):
        seg_start = real_start if i == 0 else max(raw[i][0], stitched[i - 1][1])
        seg_end = real_end if i == len(raw) - 1 else raw[i + 1][0]
        stitched.append((seg_start, max(seg_end, seg_start + 1e-6)))

    boundaries: list[tuple[float, float]] = []
    for seg_start, seg_end in stitched:
        mapped_start = start + (seg_start - real_start) * scale
        mapped_end = start + (seg_end - real_start) * scale
        mapped_end = min(mapped_end, mapped_start + max_duration_sec)
        mapped_end = max(mapped_end, mapped_start + 0.01)
        boundaries.append((mapped_start, mapped_end))
    return boundaries


def split_beat_into_segments(
    beat_id: str, text: str, start: float, end: float, config: CaptionSegmentationConfig,
    words: list[CaptionWordTiming] | None = None,
) -> list[CaptionSegment]:
    """Section 11/12/15: one Beat's narration -> N caption segments, each
    strictly inside [start, end] (section 15's own "caption.start >=
    beat.start, caption.end <= beat.end").

    Task 62: when `words` (this Beat's own slice of real, measured
    per-word timing) is supplied and its word count matches the text's
    own, segments are positioned against that real timing (see
    _real_word_boundaries above) -- far more accurate than an estimate.
    Falls back to the original weighted-distribution model (word count +
    punctuation pause weight, like app.modules.voice.timing.
    compute_beat_timing) -- rebalanced for min_duration and capped at
    max_duration (section 10: a segment given more idle time than
    max_duration_sec by the weighted split is capped there, leaving a
    trailing gap rather than an oversized on-screen block -- section 14's
    own "small gaps are acceptable if intentional") -- whenever real
    timing isn't available at all (the "local" SAPI5 provider has no
    word-boundary data) or doesn't line up with this Beat's own text.

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

    real_boundaries = _real_word_boundaries(chunks, words, start, end, config.max_duration_sec) if words else None

    if real_boundaries is not None:
        boundaries = real_boundaries
    else:
        weights = [_weight_for_text(c) for c in chunks]
        total_weight = sum(weights)
        raw_durations = [w / total_weight * duration for w in weights]

        min_duration = min(config.min_duration_sec, duration / len(chunks))
        durations = _rebalance_minimum_duration(raw_durations, duration, min_duration)
        # Cap after rebalancing (section 10) -- never below the just-enforced
        # minimum (already guaranteed <= max_duration_sec in any realistic
        # config; MAX_CAPTION checked at the config layer keeps min <= max).
        durations = [min(d, config.max_duration_sec) for d in durations]

        boundaries = []
        cursor = start
        for chunk_duration in durations:
            seg_start = cursor
            seg_end = min(end, seg_start + chunk_duration)
            boundaries.append((seg_start, seg_end))
            cursor = seg_end

    segments: list[CaptionSegment] = []
    for i, (chunk, (seg_start, seg_end)) in enumerate(zip(chunks, boundaries)):
        segments.append(CaptionSegment(id=f"{beat_id}_c{i + 1}", beat_id=beat_id, start=seg_start, end=seg_end, text=chunk))
    return segments
