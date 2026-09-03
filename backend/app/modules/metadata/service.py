"""Deterministic title/description/hashtag derivation (Task 27 sections
21-29). Pure, no I/O, no AI call -- every function here is a plain string
transform over already-generated content (ContentInputs) or an explicit
manual override (ManualOverrides). Calling any of these twice with the
same inputs always returns the exact same result.
"""

import re

from app.modules.metadata.schemas import (
    DESCRIPTION_INVALID,
    HASHTAG_INVALID,
    TITLE_INVALID,
    ContentInputs,
    MetadataError,
)

_WHITESPACE_RE = re.compile(r"\s+")
_ILLEGAL_FS_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")
# A hashtag is a tag, not a caption -- reject phrase/sentence-length input
# instead of CamelCasing it into one unusable run-on tag (feature 126).
_HASHTAG_MAX_WORDS = 5
_HASHTAG_MAX_CHARS = 40


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    words = text.split()
    kept: list[str] = []
    length = 0
    for word in words:
        added = len(word) if not kept else len(word) + 1
        if length + added > max_chars:
            break
        kept.append(word)
        length += added
    return " ".join(kept) if kept else text[:max_chars]


# -- Title (section 21-23) ---------------------------------------------


def validate_title(text: str, max_chars: int) -> None:
    if not text or not text.strip():
        raise MetadataError(TITLE_INVALID, "Title must not be empty.")
    if len(text) > max_chars:
        raise MetadataError(TITLE_INVALID, f"Title is {len(text)} characters, longer than the {max_chars} limit.")
    if _ILLEGAL_FS_CHARS_RE.search(text):
        raise MetadataError(TITLE_INVALID, f"Title contains illegal filesystem characters: {text!r}")
    if _CONTROL_CHAR_RE.search(text):
        raise MetadataError(TITLE_INVALID, "Title contains control characters.")


def derive_title(inputs: ContentInputs, manual_title: str | None, max_chars: int) -> str:
    """Section 21's own priority: manual title > a deterministically
    derived title > hook fallback. "Generated title" (the brief's own
    middle tier) means core_message here -- there is no second AI call in
    this task (section 22), so "generation" is this template/shortening
    logic, not a fresh model response.
    """
    if manual_title is not None and manual_title.strip():
        text = _normalize_whitespace(_ILLEGAL_FS_CHARS_RE.sub("", manual_title))
        validate_title(text, max_chars)
        return text

    candidate = inputs.core_message or inputs.hook_text or inputs.project_name
    if not candidate:
        raise MetadataError(TITLE_INVALID, "No core message, hook, or project name available to derive a title from.")
    text = _normalize_whitespace(_ILLEGAL_FS_CHARS_RE.sub("", candidate))
    text = _truncate_at_word_boundary(text, max_chars)
    validate_title(text, max_chars)
    return text


# -- Description (section 24-25) -----------------------------------------


def validate_description(text: str, max_chars: int) -> None:
    if not text or not text.strip():
        raise MetadataError(DESCRIPTION_INVALID, "Description must not be empty.")
    if len(text) > max_chars:
        raise MetadataError(DESCRIPTION_INVALID, f"Description is {len(text)} characters, longer than the {max_chars} limit.")
    if _CONTROL_CHAR_RE.search(text):
        raise MetadataError(DESCRIPTION_INVALID, "Description contains control characters.")


def derive_description(
    inputs: ContentInputs, manual_description: str | None, hashtags: list[str],
    *, cta_enabled: bool, max_chars: int,
) -> str:
    """Section 24's own template: [summary] blank-line [CTA] blank-line
    [hashtags]. A manual description is used verbatim (section 25's own
    "reuse it," section 48's "manual edits override generated values") --
    hashtags are never appended to a human-written description.
    """
    if manual_description is not None and manual_description.strip():
        text = manual_description.strip()
        validate_description(text, max_chars)
        return text

    summary = inputs.core_message or inputs.hook_text or inputs.project_name
    if not summary:
        raise MetadataError(DESCRIPTION_INVALID, "No content available to derive a description from.")

    parts = [summary.strip()]
    if cta_enabled and inputs.cta:
        parts.append(inputs.cta.strip())
    body = "\n\n".join(parts)
    if hashtags:
        body = f"{body}\n\n{' '.join(hashtags)}"

    if len(body) > max_chars:
        # Trim the summary/CTA body first (word boundary), keep the
        # hashtag line intact -- a truncated hashtag is a broken hashtag,
        # never worth saving a few characters of summary text over.
        hashtag_line = f"\n\n{' '.join(hashtags)}" if hashtags else ""
        budget = max(0, max_chars - len(hashtag_line))
        body = _truncate_at_word_boundary("\n\n".join(parts), budget) + hashtag_line
    validate_description(body, max_chars)
    return body


# -- Hashtags (section 26-28) ---------------------------------------------


def normalize_hashtag(raw: str) -> str | None:
    """Section 27: "#LoveStory" / "#love story" / "love-story" all
    normalize to the same "#LoveStory" CamelCase form. Returns None for
    anything with no real alphanumeric content (an empty/punctuation-only
    input) -- the caller drops those rather than emitting a bare "#".
    """
    text = raw.strip()
    if text.startswith("#"):
        text = text[1:]
    words = [w for w in _NON_ALNUM_RE.split(text) if w]
    if not words:
        return None
    # A real hashtag is a couple of words, not a phrase or a whole
    # sentence. Reject anything longer rather than CamelCasing it into an
    # unusable monster tag -- ContentBrief's topic/angle/emotion/tone are
    # full sentences (see derive_hashtags), and feeding those here used to
    # produce "#TheBattleOfAgincourtOn25October1415Where..." (feature 126).
    if len(words) > _HASHTAG_MAX_WORDS:
        return None
    normalized = "".join(word[:1].upper() + word[1:] for word in words)
    if not normalized or len(normalized) > _HASHTAG_MAX_CHARS:
        return None
    return f"#{normalized}"


def normalize_hashtags(raw_candidates: list[str], max_count: int) -> list[str]:
    """Section 27/28: normalizes, drops empty/invalid/duplicate (case-
    insensitive) tags, then caps at `max_count` in input order --
    "quality over quantity," never padded up to a target count.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in raw_candidates:
        tag = normalize_hashtag(raw)
        if tag is None:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
        if len(result) >= max_count:
            break
    return result


def validate_hashtags(hashtags: list[str], max_count: int) -> None:
    if len(hashtags) > max_count:
        raise MetadataError(HASHTAG_INVALID, f"{len(hashtags)} hashtags exceeds the configured limit of {max_count}.")
    for tag in hashtags:
        if not tag.startswith("#") or len(tag) < 2:
            raise MetadataError(HASHTAG_INVALID, f"Invalid hashtag: {tag!r}")
        if _CONTROL_CHAR_RE.search(tag):
            raise MetadataError(HASHTAG_INVALID, f"Hashtag contains control characters: {tag!r}")


def derive_hashtags(inputs: ContentInputs, manual_hashtags: list[str] | None, max_count: int) -> list[str]:
    """Section 26/28: manual hashtags always win (validated, never
    silently topped up with generated ones); otherwise derived from
    ContentBrief's own topic/angle/emotion/tone -- there is no Project-
    level Tag/Category association in this codebase to reuse instead (the
    existing Tag system is Video-library-level, structurally unrelated to
    a Factory Project -- see this task's own docs/features entry).
    """
    if manual_hashtags is not None:
        normalized = normalize_hashtags(manual_hashtags, max_count)
        validate_hashtags(normalized, max_count)
        return normalized

    raw_candidates = [s for s in (inputs.topic, inputs.angle, inputs.emotion, inputs.tone) if s]
    hashtags = normalize_hashtags(raw_candidates, max_count)
    validate_hashtags(hashtags, max_count)
    return hashtags


# -- Category (section 30) -------------------------------------------------


def derive_category(inputs: ContentInputs) -> str:
    """Section 30's own instruction not to build a second category
    taxonomy: this codebase's real `Category` table is Video-library-level
    and structurally unrelated to a Factory Project (no FK, no shared
    identity) -- reusing it here would require a genuinely new schema
    relationship, out of this task's "reuse existing" scope. `topic` (a
    free string already produced by Task 21's ContentBrief, matching the
    same already-accepted precedent as ContentBrief.emotion being a free
    string rather than a DB Emotion row) is the closest honest label.
    """
    return inputs.topic or "general"
