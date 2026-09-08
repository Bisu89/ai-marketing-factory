"""Narration audio for the Video Composer render path:

- `run_narration`      -- fresh edge_tts synthesis (Chinese Drama mode),
                          returns word-boundary timings.
- `build_narration_timeline` -- stitch per-beat pre-recorded clips into one
                          gapless track honouring each Beat's duration
                          (local-narration mode).

Extracted verbatim from `VideoComposerService` (P2 refactor). Behaviour
unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import edge_tts

from app.modules.video_composer.ffmpeg_ops import run_ffmpeg

logger = logging.getLogger(__name__)

# edge-tts is an unofficial API -- real testing (both Chinese Drama
# verification and app.modules.voice.providers' EdgeTTSProvider, which
# documents the identical failure) shows an intermittent "No audio was
# received" error every few consecutive calls, unrelated to the text.
# Duplicated (not imported) retry shape from that module -- module isolation.
_NARRATION_MAX_ATTEMPTS = 4
_NARRATION_RETRY_BACKOFF_SEC = 1.5


def run_narration(script_text: str, voice: str, output_path: Path, rate: str = "+0%") -> list[dict]:
    async def _generate_once() -> list[dict]:
        communicate = edge_tts.Communicate(script_text, voice, rate=rate, boundary="WordBoundary")
        words: list[dict] = []
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append(
                        {
                            "start": chunk["offset"] / 1e7,
                            "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                            "text": chunk["text"],
                        }
                    )
        return words

    async def _generate_with_retry() -> list[dict]:
        last_exc: Exception | None = None
        for attempt in range(_NARRATION_MAX_ATTEMPTS):
            try:
                words = await _generate_once()
                if output_path.exists() and output_path.stat().st_size > 0:
                    return words
                last_exc = RuntimeError("edge_tts produced no audio bytes.")
            except Exception as exc:  # noqa: BLE001 -- retried regardless of edge_tts exception type
                last_exc = exc
            if attempt < _NARRATION_MAX_ATTEMPTS - 1:
                logger.warning(
                    "edge_tts narration attempt %d/%d failed (%s) -- retrying.",
                    attempt + 1, _NARRATION_MAX_ATTEMPTS, last_exc,
                )
                await asyncio.sleep(_NARRATION_RETRY_BACKOFF_SEC * (attempt + 1))
        raise RuntimeError(f"edge_tts narration failed after {_NARRATION_MAX_ATTEMPTS} attempts: {last_exc}")

    return asyncio.run(_generate_with_retry())


def build_narration_timeline(specs: list[dict], segments_dir: Path, output_path: Path) -> None:
    """Builds one continuous local narration track from per-beat pre-recorded
    audio, preserving Beat boundaries exactly: each entry in `specs`
    (`{"duration": float, "path": str | None}`, one per Beat, in order)
    occupies exactly `duration` seconds -- its own audio (silence-padded if
    shorter) or pure silence if `path` is None. A drop-in replacement for
    `run_narration`'s output: the same "one narration file" contract
    `audio_mix.mix_audio` expects.
    """
    segments_dir.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []
    for index, spec in enumerate(specs):
        duration = float(spec["duration"])
        source_path = spec.get("path")
        segment_path = segments_dir / f"segment_{index:03d}.m4a"
        if source_path:
            run_ffmpeg(
                [
                    "-i", str(source_path),
                    "-af", f"apad=whole_dur={duration}",
                    "-t", str(duration),
                    "-c:a", "aac",
                    str(segment_path),
                ]
            )
        else:
            run_ffmpeg(
                [
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", str(duration),
                    "-c:a", "aac",
                    str(segment_path),
                ]
            )
        segment_paths.append(segment_path)

    if not segment_paths:
        # No beats at all -- shouldn't happen (an empty CompositionPlan is
        # rejected before rendering), but produce a trivially short silent
        # file rather than leaving no narration input at all.
        run_ffmpeg(
            ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1", "-c:a", "aac", str(output_path)]
        )
        return

    concat_list = segments_dir / "concat.txt"
    concat_list.write_text(
        # ffmpeg's concat demuxer resolves relative "file" entries against
        # the list file's own directory, not the process cwd -- resolve to
        # an absolute path so the relative job_dir path isn't doubled up.
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths), encoding="utf-8"
    )
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)]
    )
