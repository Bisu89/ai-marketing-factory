"""Beat timing (Task 22 sections 14-23) -- turns one continuous narration
track into a start/end/duration window per Beat. Pure, deterministic,
no I/O: everything here operates on plain text and numbers already
resolved by the composition root (app/api/v1/endpoints/voice_generate.py).

Two timing sources, matching section 16's own priority list:

1. Real per-word timestamps (only ever available from a provider that
   exposes them, e.g. EdgeTTSProvider's WordBoundary events) -- used when
   present and the word count lines up closely enough with our own
   text.split() counts to trust the per-beat slicing (see
   _timing_from_word_timestamps' own reliability guard).
2. A deterministic weighted estimate (section 17/18) -- word count +
   punctuation-pause weight, normalized to the real, measured narration
   duration. This is the one every project can always fall back to
   (SAPI5, this app's own default provider, exposes no word boundaries at
   all), and the one this task's own tests hold to the tightest contract.

Either way, the result is always stitched into a gapless, non-overlapping,
minimum-duration-respecting sequence before being returned (section 18's
own "avoid gaps and overlaps", section 19's own "do not silently delete a
beat" minimum-duration rebalancing).
"""

from app.modules.voice.schemas import VOICE_TIMING_FAILED, BeatTiming, BeatTimingInput, VoiceError, WordTiming

# Section 18's own formula: weighted_duration = word_count + punctuation_pause_weight.
# A sentence-ending mark implies a longer natural pause than a comma.
_SENTENCE_END_WEIGHT = 1.5
_COMMA_WEIGHT = 0.5
_SENTENCE_END_CHARS = (".", "!", "?")

DEFAULT_MIN_BEAT_DURATION = 0.8

# How far a TTS engine's own word count may drift from our text.split()
# count before we stop trusting the per-beat word-timestamp slice
# (abbreviations/numbers can tokenize differently) and fall back to the
# weighted estimate instead of guessing.
_WORD_COUNT_DRIFT_TOLERANCE_RATIO = 0.15
_WORD_COUNT_DRIFT_TOLERANCE_MIN = 3


def compute_beat_timing(
    beats: list[BeatTimingInput],
    total_duration: float,
    min_beat_duration: float = DEFAULT_MIN_BEAT_DURATION,
    word_timestamps: list[WordTiming] | None = None,
) -> list[BeatTiming]:
    if not beats:
        return []
    if total_duration <= 0:
        raise VoiceError(VOICE_TIMING_FAILED, f"Narration duration must be positive, got {total_duration}.")

    raw: list[BeatTiming] | None = None
    if word_timestamps:
        raw = _timing_from_word_timestamps(beats, word_timestamps, total_duration)
    if raw is None:
        raw = _timing_from_weighted_estimate(beats, total_duration)

    durations = _rebalance_minimum_duration(
        [t.duration for t in raw], total_duration, min(min_beat_duration, total_duration / len(beats))
    )
    return _stitch_contiguous(beats, durations, total_duration)


# -- Weighted text-based estimate (priority 3 -- always available) ---------


def _weight_for_text(text: str) -> float:
    text = (text or "").strip()
    if not text:
        return 1.0  # a beat with no narration still gets a real, minimum share -- never zero
    word_count = len(text.split())
    sentence_ends = sum(text.count(c) for c in _SENTENCE_END_CHARS)
    commas = text.count(",")
    weight = word_count + sentence_ends * _SENTENCE_END_WEIGHT + commas * _COMMA_WEIGHT
    return max(weight, 1.0)


def _timing_from_weighted_estimate(beats: list[BeatTimingInput], total_duration: float) -> list[BeatTiming]:
    weights = [_weight_for_text(b.text) for b in beats]
    total_weight = sum(weights)
    shares = [w / total_weight for w in weights]
    # start/end are placeholders here -- _stitch_contiguous (always called
    # by compute_beat_timing afterward) is what actually assigns them;
    # only `duration` from this function is used.
    return [
        BeatTiming(beat_id=b.beat_id, start=0.0, end=0.0, duration=share * total_duration)
        for b, share in zip(beats, shares)
    ]


# -- Real word-timestamp alignment (priority 1 -- when available) ----------


def _timing_from_word_timestamps(
    beats: list[BeatTimingInput], word_timestamps: list[WordTiming], total_duration: float
) -> list[BeatTiming] | None:
    expected_counts = [len((b.text or "").split()) for b in beats]
    total_expected = sum(expected_counts)
    if total_expected == 0 or not word_timestamps or any(c == 0 for c in expected_counts):
        return None  # a beat with no narration text has no words to anchor to

    tolerance = max(_WORD_COUNT_DRIFT_TOLERANCE_MIN, round(total_expected * _WORD_COUNT_DRIFT_TOLERANCE_RATIO))
    if abs(len(word_timestamps) - total_expected) > tolerance:
        return None  # the engine's own tokenization drifted too far to trust per-beat slicing

    timings: list[BeatTiming] = []
    cursor = 0
    for beat, count in zip(beats, expected_counts):
        words = word_timestamps[cursor:cursor + count]
        cursor += count
        if not words:
            return None
        start, end = words[0].start, words[-1].end
        timings.append(BeatTiming(beat_id=beat.beat_id, start=start, end=max(end, start + 0.01), duration=max(end - start, 0.01)))
    return timings


# -- Shared post-processing: minimum duration + gapless stitching ----------


def _rebalance_minimum_duration(raw_durations: list[float], total_duration: float, min_duration: float) -> list[float]:
    """Section 19: a beat below `min_duration` is clamped up to it; the
    difference is taken from beats currently above the minimum,
    proportional to their own size, over a few bounded passes (never an
    unbounded loop). If even splitting `total_duration` evenly across
    every beat can't reach `min_duration` for all of them, falls back to
    that even split -- the closest possible approximation without ever
    deleting a beat (section 19's own explicit instruction).
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


def _stitch_contiguous(beats: list[BeatTimingInput], durations: list[float], total_duration: float) -> list[BeatTiming]:
    """Section 18/22/23: builds the final start/end sequence directly from
    `durations` in order -- first.start == 0, each.start == previous.end
    by construction (not just validated after the fact), and the very
    last beat's `end` is forced to exactly `total_duration` so float
    rounding across many beats can never leave a gap before the real end
    of the narration.
    """
    timings: list[BeatTiming] = []
    cursor = 0.0
    for beat, duration in zip(beats, durations):
        start = cursor
        end = start + duration
        timings.append(BeatTiming(beat_id=beat.beat_id, start=start, end=end, duration=duration))
        cursor = end

    last = timings[-1]
    timings[-1] = BeatTiming(beat_id=last.beat_id, start=last.start, end=total_duration, duration=total_duration - last.start)
    return timings
