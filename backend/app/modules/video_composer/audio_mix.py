"""Narration + optional ducked music + optional SFX -> one mixed audio
track. Extracted verbatim from `VideoComposerService._mix_audio` (P2
refactor). Behaviour unchanged.
"""

from __future__ import annotations

from pathlib import Path

from app.modules.video_composer.ffmpeg_ops import run_ffmpeg


def mix_audio(
    narration_path: Path,
    music_path: str | None,
    music_volume: float,
    narration_volume: float,
    music_ducking_ratio: float,
    fade_in_sec: float,
    fade_out_sec: float,
    video_duration: float,
    output_path: Path,
    sfx_cues: list[dict] | None = None,
) -> None:
    """Mixes narration (always present) with optional background music
    (ducked under narration via ffmpeg's sidechaincompress -- real, dynamic
    ducking keyed off the narration's own level) and optional SFX cues
    (each played once, delayed to its own start offset), then applies
    optional fade in/out. `-t {video_duration}` on the output is the hard,
    deterministic-duration safety net.
    """
    sfx_cues = sfx_cues or []

    inputs: list[str] = ["-i", str(narration_path)]
    # whole_dur makes the pad target explicit and deterministic regardless
    # of what else is in the filter chain (apad's default pads only a small
    # ffmpeg-internal amount once amix/sidechaincompress are also present --
    # confirmed by a real truncation bug while building this pipeline).
    filters: list[str] = [f"[0:a]volume={narration_volume},apad=whole_dur={video_duration}[narration]"]
    mix_labels = ["narration"]
    next_index = 1

    if music_path:
        inputs += ["-stream_loop", "-1", "-i", music_path]
        filters.append(f"[{next_index}:a]volume={music_volume}[music_pre]")
        # sidechaincompress: music is compressed using narration as the
        # trigger -- music level drops whenever narration is speaking and
        # returns during silence. threshold/attack/release are fixed
        # speech-over-music defaults; `ratio` is the exposed knob.
        filters.append(
            f"[music_pre][narration]sidechaincompress=threshold=0.05:"
            f"ratio={music_ducking_ratio}:attack=5:release=300[ducked]"
        )
        mix_labels.append("ducked")
        next_index += 1

    for i, cue in enumerate(sfx_cues):
        inputs += ["-i", str(cue["path"])]
        delay_ms = max(0, int(round(cue.get("start_sec", 0.0) * 1000)))
        cue_volume = cue.get("volume", 1.0)
        label = f"sfx{i}"
        filters.append(f"[{next_index}:a]volume={cue_volume},adelay={delay_ms}|{delay_ms}[{label}]")
        mix_labels.append(label)
        next_index += 1

    if len(mix_labels) > 1:
        mix_inputs = "".join(f"[{label}]" for label in mix_labels)
        filters.append(f"{mix_inputs}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[mixed]")
        last_label = "mixed"
    else:
        last_label = "narration"

    # Final apad=whole_dur, always applied: sidechaincompress truncates its
    # output back to narration's raw pre-padding length even when fed an
    # already-padded sidechain (a real test failure while building this).
    # whole_dur only ever adds silence, never trims. The outer -t is the
    # final trim.
    final_ops = [f"apad=whole_dur={video_duration}"]
    if fade_in_sec > 0:
        final_ops.append(f"afade=t=in:st=0:d={fade_in_sec}")
    if fade_out_sec > 0:
        fade_out_start = max(0.0, video_duration - fade_out_sec)
        final_ops.append(f"afade=t=out:st={fade_out_start}:d={fade_out_sec}")
    filters.append(f"[{last_label}]{','.join(final_ops)}[a]")

    run_ffmpeg(
        inputs
        + [
            "-filter_complex", ";".join(filters),
            "-map", "[a]",
            "-t", str(video_duration),
            str(output_path),
        ]
    )
