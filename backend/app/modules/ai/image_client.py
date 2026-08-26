"""OpenAI Images API wrapper (Task 59 -- "Generate Full by AI" opt-in per-
beat image generation). Sibling to llm_client.py -- same "wrap one SDK
resource behind a small, stable surface" role -- but a different API
surface (Images, not Chat Completions) and always OpenAI, independent of
llm_client.AI_PROVIDERS' own text-provider toggle (Claude has no image
generation API, so this feature never branches on settings.ai_provider).

Real, installed openai==3.3.0 SDK shape (verified directly against
.venv/Lib/site-packages/openai/resources/images.py): GPT image models
(gpt-image-1*) only ever return base64 (`Image.b64_json`), never a `url`
-- no response_format needs to be requested for that, it's simply how
this model family always responds.
"""

import base64
from pathlib import Path

import openai

# Change here only -- nowhere else references image model/quality/size.
IMAGE_MODEL = "gpt-image-1-mini"
IMAGE_QUALITY = "low"

# GPT image models only support these three exact sizes (verified against
# the installed openai SDK's own Literal type, e.g.
# openai.types.images_response.ImagesResponse.data[].size). Real user
# request: a landscape (16:9) render profile alongside this app's original
# portrait one -- see app.core.render_profile.SOCIAL_LANDSCAPE. Keyed by
# the same "portrait"/"landscape"/"square" orientation
# _orientation_for_profile below derives from a project's actual render
# profile, so a caller never has to know the raw API size string.
IMAGE_SIZE_PORTRAIT = "1024x1536"
IMAGE_SIZE_LANDSCAPE = "1536x1024"
IMAGE_SIZE_SQUARE = "1024x1024"

IMAGE_SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    IMAGE_SIZE_PORTRAIT: (1024, 1536),
    IMAGE_SIZE_LANDSCAPE: (1536, 1024),
    IMAGE_SIZE_SQUARE: (1024, 1024),
}

# Kept as the default for every existing caller that doesn't (yet) pass an
# explicit `size` -- this app's original portrait 9:16 profile.
IMAGE_SIZE = IMAGE_SIZE_PORTRAIT
IMAGE_WIDTH, IMAGE_HEIGHT = IMAGE_SIZE_DIMENSIONS[IMAGE_SIZE]

# Flat per-image USD price (OpenAI's own published table, not derived from
# token usage -- simpler, matches what the user sees on OpenAI's pricing
# page). Portrait and landscape have the identical total pixel count (just
# rotated), so this one price covers both; square was never priced/verified
# separately since no square render profile exists in this app. Update
# here only if OpenAI repriced gpt-image-1-mini/low.
IMAGE_COST_USD = 0.006


class ImageGenError(Exception):
    """Any failure generating or decoding one beat's image."""


def generate_beat_image(api_key: str, prompt: str, output_path: Path, size: str = IMAGE_SIZE) -> None:
    """Generates one image and writes it atomically to output_path. Never
    partially writes a broken file at the canonical path (same tmp-then-
    replace convention voice_generate.py's own narration_wav.replace()
    uses) -- a crash mid-write must never leave a corrupt PNG that a later
    idempotent-reuse check would wrongly treat as already-generated.

    `size` defaults to this app's original portrait size for every existing
    caller that doesn't pass one; must be one of IMAGE_SIZE_DIMENSIONS'
    keys. Callers that care about a project's actual render profile (see
    imagegen_generate.py) pass one of IMAGE_SIZE_PORTRAIT/_LANDSCAPE/_SQUARE
    explicitly instead of relying on this default.
    """
    if size not in IMAGE_SIZE_DIMENSIONS:
        raise ImageGenError(f"Unsupported image size {size!r}, must be one of {sorted(IMAGE_SIZE_DIMENSIONS)}")

    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.images.generate(
            model=IMAGE_MODEL, prompt=prompt, quality=IMAGE_QUALITY, size=size, n=1,
        )
    except openai.APIError as exc:
        raise ImageGenError(str(exc)) from exc

    image = response.data[0] if response.data else None
    if image is None or not image.b64_json:
        raise ImageGenError("OpenAI returned no image data.")

    try:
        raw = base64.b64decode(image.b64_json)
    except (ValueError, TypeError) as exc:
        raise ImageGenError(f"Could not decode OpenAI's image response: {exc}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_bytes(raw)
    tmp_path.replace(output_path)
