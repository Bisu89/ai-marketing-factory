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
IMAGE_SIZE = "1024x1536"  # portrait, matches this app's own 9:16 render profile
IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 1536

# Flat per-image USD price (OpenAI's own published table, not derived from
# token usage -- simpler, matches what the user sees on OpenAI's pricing
# page). Update here only if OpenAI repriced gpt-image-1-mini/low/1024x1536.
IMAGE_COST_USD = 0.006


class ImageGenError(Exception):
    """Any failure generating or decoding one beat's image."""


def generate_beat_image(api_key: str, prompt: str, output_path: Path) -> None:
    """Generates one image and writes it atomically to output_path. Never
    partially writes a broken file at the canonical path (same tmp-then-
    replace convention voice_generate.py's own narration_wav.replace()
    uses) -- a crash mid-write must never leave a corrupt PNG that a later
    idempotent-reuse check would wrongly treat as already-generated.
    """
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.images.generate(
            model=IMAGE_MODEL, prompt=prompt, quality=IMAGE_QUALITY, size=IMAGE_SIZE, n=1,
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
