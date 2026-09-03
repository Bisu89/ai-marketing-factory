"""Download a news article's own image and prepare it as a ready-to-render
still: cover-crop (fill the frame, crop the overflow) to the exact render
profile size, save as JPEG. Pure except for the one httpx GET + file write
-- no DB, no other module.

Cover-crop, not letterbox: a news photo is almost always landscape
(~1200x630) and a short-form video is vertical, so fitting-with-bars would
waste ~60% of the frame. The motion renderer's own pan/zoom then works on
a full-bleed image.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# A news CDN image is rarely above this; refuse anything absurd rather than
# decompression-bomb ourselves.
_MAX_BYTES = 25 * 1024 * 1024


def prepare_article_image(url: str, dest_path: Path, width: int, height: int, *, timeout: float = 15.0) -> bool:
    """Download `url`, cover-crop to `width`x`height`, write JPEG to
    `dest_path`. Returns True on success, False on any failure (bad URL,
    non-image, tiny image) -- the caller falls back to library/AI image
    assignment, never hard-fails.
    """
    try:
        resp = httpx.get(
            url, timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "AIContentLibrary/1.0 (+news image)"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("News image download failed for %s: %s", url, exc)
        return False

    if len(resp.content) > _MAX_BYTES:
        logger.warning("News image too large (%d bytes): %s", len(resp.content), url)
        return False

    try:
        img = Image.open(io.BytesIO(resp.content))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception as exc:  # noqa: BLE001 -- PIL raises a zoo of types
        logger.warning("News image not decodable (%s): %s", exc, url)
        return False

    # Reject a thumbnail that would look terrible blown up to full frame.
    if img.width < 320 or img.height < 240:
        logger.info("News image too small (%dx%d), skipping: %s", img.width, img.height, url)
        return False

    fitted = ImageOps.fit(img, (width, height), method=Image.LANCZOS, centering=(0.5, 0.4))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(dest_path, format="JPEG", quality=88)
    return True
