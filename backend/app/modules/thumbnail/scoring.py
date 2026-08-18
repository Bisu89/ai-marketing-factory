"""Deterministic frame rejection + scoring + selection (Task 27 sections
7-9). Pure, no I/O -- operates entirely on already-computed FrameStats
(see renderer.py for the actual Pillow measurement pass). Never AI vision
(section 7), never random (section 9 -- "the same video should produce the
same thumbnail on retry").
"""

from app.modules.thumbnail.schemas import FrameStats

# Section 7's own "reject near-black/near-white/flat/blurred" -- a 0-255
# grayscale scale. A frame this dark or this bright is almost always a
# fade-to-black/white transition or a blown-out flash, never a usable
# thumbnail candidate.
MIN_BRIGHTNESS = 15.0
MAX_BRIGHTNESS = 240.0
# Below this, a frame is visually flat/empty (a solid-color or near-solid
# card, a heavy fade) regardless of brightness.
MIN_CONTRAST = 8.0
# Below this, a frame has almost no edge detail at all -- heavily
# blurred/out-of-focus or a near-empty frame the contrast check alone
# might miss (e.g. a soft gradient with real contrast but no detail).
MIN_EDGE_DENSITY = 2.0

# Section 8's own weighting -- "should prioritize sharpness + contrast +
# reasonable brightness," in that order. Each raw signal is normalized to
# roughly 0..1 before weighting; the exact saturation points are generous
# (found via real photos during manual verification), not intended to be
# a precise perceptual model -- this is a deterministic MVP heuristic, not
# a claimed accurate one.
_EDGE_WEIGHT = 0.45
_CONTRAST_WEIGHT = 0.35
_BRIGHTNESS_WEIGHT = 0.20
_EDGE_SATURATION = 40.0
_CONTRAST_SATURATION = 80.0
_IDEAL_BRIGHTNESS = 128.0


def is_rejectable(stats: FrameStats) -> bool:
    """Section 7: near-black/near-white/flat/heavily-blurred candidates
    are excluded before scoring ever runs -- never merely scored low
    alongside good candidates, since a whole batch of candidates could
    legitimately all be borderline dark (e.g. a night-themed video) and
    "just pick the least-bad one" would still ship an unusable thumbnail.
    """
    if stats.brightness < MIN_BRIGHTNESS or stats.brightness > MAX_BRIGHTNESS:
        return True
    if stats.contrast < MIN_CONTRAST:
        return True
    if stats.edge_density < MIN_EDGE_DENSITY:
        return True
    return False


def score_frame(stats: FrameStats) -> float:
    """Section 8: higher is better. Deterministic pure arithmetic over
    already-computed stats -- calling this twice on the same FrameStats
    always returns the exact same float.
    """
    brightness_score = max(0.0, 1.0 - abs(stats.brightness - _IDEAL_BRIGHTNESS) / _IDEAL_BRIGHTNESS)
    contrast_score = min(stats.contrast / _CONTRAST_SATURATION, 1.0)
    edge_score = min(stats.edge_density / _EDGE_SATURATION, 1.0)
    return _EDGE_WEIGHT * edge_score + _CONTRAST_WEIGHT * contrast_score + _BRIGHTNESS_WEIGHT * brightness_score


def select_best_frame(candidates: list[FrameStats]) -> FrameStats | None:
    """Section 9: deterministic -- ties (identical score) broken by the
    earliest offset_fraction, never by insertion order or randomness, so
    re-running against the exact same candidate set always picks the same
    frame. Returns None (section 7's own "no valid frame" outcome, see
    THUMBNAIL_NO_VALID_FRAME) when every candidate was rejected -- the
    strict version, with no fallback (see select_best_frame_with_fallback
    below for what the real renderer actually uses).
    """
    survivors = [c for c in candidates if not is_rejectable(c)]
    if not survivors:
        return None
    return min(survivors, key=lambda c: (-score_frame(c), c.offset_fraction))


def select_best_frame_with_fallback(candidates: list[FrameStats]) -> FrameStats | None:
    """What app.modules.thumbnail.renderer actually calls. A real, non-
    corrupt video that happens to be uniformly flat/low-detail throughout
    (a legitimate, if visually plain, video -- e.g. simple text-on-solid-
    background content) would otherwise hard-fail the whole Package stage
    over every single candidate tripping the same rejection heuristic --
    the exact "never block the near-$0 factory over a soft failure" this
    codebase already applies everywhere else (BGM-missing, Motion-cache-
    miss, etc.). Falls back to the highest-scoring candidate among *all*
    of them, rejected or not, once a real attempt at a good frame has
    already failed. Only returns None when there is nothing at all to
    choose from (an empty candidate list -- section 7's own genuinely
    unrecoverable case, still THUMBNAIL_NO_VALID_FRAME).
    """
    best = select_best_frame(candidates)
    if best is not None:
        return best
    if not candidates:
        return None
    return min(candidates, key=lambda c: (-score_frame(c), c.offset_fraction))
