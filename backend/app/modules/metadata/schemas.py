"""Pure domain contracts for the Metadata Engine (Task 27 -- see
docs/features/53-thumbnail-metadata-package.md): existing Content/Script/
Hook -> deterministic title/description/hashtags -> metadata.json. No AI
call of any kind -- everything here is template/normalization logic over
data the Factory already produced in earlier stages.

Per app/modules/README.md, this module must never import
app.modules.beat/asset/factory/video_composer (or vice versa) -- the
composition root (app/api/v1/endpoints/package_generate.py) is the one
place allowed to translate a real Project/ContentBrief/Beat into this
module's own ContentInputs.
"""

from dataclasses import dataclass

METADATA_GENERATION_FAILED = "METADATA_GENERATION_FAILED"
TITLE_INVALID = "TITLE_INVALID"
DESCRIPTION_INVALID = "DESCRIPTION_INVALID"
HASHTAG_INVALID = "HASHTAG_INVALID"


class MetadataError(Exception):
    """Base for every error this module raises -- always carries one of
    the stable codes above so a composition root never has to string-match
    a message to classify a failure.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ContentInputs:
    """The subset of a project's own already-generated content this
    module needs to derive title/description/hashtags from (section 21/24/
    26) -- plain strings, no ContentBrief/Beat import (module isolation).
    `hook_text` is the project's own HOOK-type Beat narration, if any
    (section 14: the thumbnail headline/title fallback must come from a
    real Hook or Title already in this project, never an invented
    message).
    """

    core_message: str | None = None
    cta: str | None = None
    topic: str | None = None
    angle: str | None = None
    emotion: str | None = None
    tone: str | None = None
    hook_text: str | None = None
    project_name: str | None = None


@dataclass
class MetadataConfig:
    language: str = "en"
    platform_profile: str = "general"
    max_hashtags: int = 8
    max_title_chars: int = 70
    max_description_chars: int = 500
    cta_enabled: bool = True


@dataclass
class ManualOverrides:
    """Section 21/48's own "manual input always wins" -- None means "no
    override, derive it"; an empty string/list is a deliberate, explicit
    "I want this blank," never conflated with "not set."
    """

    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None


@dataclass
class PackageMetadata:
    """The exact metadata.json shape (section 20)."""

    title: str
    description: str
    hashtags: list[str]
    language: str
    category: str
    platform_profile: str
    duration: float
    width: int
    height: int
    aspect_ratio: str
    thumbnail: str
    video: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "hashtags": list(self.hashtags),
            "language": self.language,
            "category": self.category,
            "platform_profile": self.platform_profile,
            "duration": self.duration,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "thumbnail": self.thumbnail,
            "video": self.video,
        }
