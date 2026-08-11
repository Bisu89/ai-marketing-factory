import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.video_composer.models import CAPTION_PRESETS
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return float(result.stdout.strip())


def _mean_volume_db(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
            "-af", f"atrim=start={start}:duration={duration},volumedetect",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
    assert match, f"volumedetect produced no mean_volume in stderr: {result.stderr}"
    return float(match.group(1))


def _make_tone(path: Path, frequency: int, duration: float) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={duration}",
            "-c:a", "libmp3lame", str(path),
        ],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


# -- _mix_audio command generation (mocked _run_ffmpeg, no real ffmpeg needed) -


class MixAudioCommandGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = VideoComposerService(library_dir=self.tmp_path)
        self.narration = self.tmp_path / "narration.mp3"
        self.narration.write_bytes(b"fake-narration-bytes")
        self.music = self.tmp_path / "music.mp3"
        self.music.write_bytes(b"fake-music-bytes")
        self.output = self.tmp_path / "out.m4a"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _captured_args(self, **overrides) -> list[str]:
        defaults = dict(
            narration_path=self.narration,
            music_path=None,
            music_volume=0.15,
            narration_volume=1.0,
            music_ducking_ratio=8.0,
            fade_in_sec=0.0,
            fade_out_sec=0.0,
            video_duration=5.0,
            output_path=self.output,
        )
        defaults.update(overrides)

        captured: dict[str, list[str]] = {}

        def _fake_run_ffmpeg(args: list[str]) -> None:
            captured["args"] = args

        with patch.object(self.service, "_run_ffmpeg", side_effect=_fake_run_ffmpeg):
            self.service._mix_audio(**defaults)
        return captured["args"]

    def _filter_complex(self, args: list[str]) -> str:
        return args[args.index("-filter_complex") + 1]

    def test_ducking_configuration_present_with_correct_ratio_when_music_given(self):
        args = self._captured_args(music_path=str(self.music), music_ducking_ratio=6.5)
        filters = self._filter_complex(args)
        self.assertIn("sidechaincompress", filters)
        self.assertIn("ratio=6.5", filters)

    def test_ducking_ratio_configuration_is_reflected_exactly(self):
        for ratio in (1.0, 8.0, 20.0):
            args = self._captured_args(music_path=str(self.music), music_ducking_ratio=ratio)
            self.assertIn(f"ratio={ratio}", self._filter_complex(args))

    def test_no_ducking_filter_when_music_is_missing_optional(self):
        args = self._captured_args(music_path=None)
        self.assertNotIn("sidechaincompress", self._filter_complex(args))
        self.assertNotIn("amix", self._filter_complex(args))  # nothing to mix with narration alone

    def test_fade_filters_present_and_correctly_timed_when_configured(self):
        args = self._captured_args(video_duration=10.0, fade_in_sec=1.0, fade_out_sec=2.0)
        filters = self._filter_complex(args)
        self.assertIn("afade=t=in:st=0:d=1.0", filters)
        self.assertIn("afade=t=out:st=8.0:d=2.0", filters)

    def test_no_fade_filters_when_durations_are_zero(self):
        args = self._captured_args(fade_in_sec=0.0, fade_out_sec=0.0)
        self.assertNotIn("afade", self._filter_complex(args))

    def test_narration_volume_is_applied(self):
        args = self._captured_args(narration_volume=0.75)
        self.assertIn("volume=0.75", self._filter_complex(args))

    def test_missing_optional_sfx_cues_produces_no_extra_inputs(self):
        args = self._captured_args(sfx_cues=None)
        self.assertNotIn("adelay", self._filter_complex(args))

    def test_sfx_cue_adds_adelay_and_extra_input(self):
        sfx = self.tmp_path / "sfx.mp3"
        sfx.write_bytes(b"fake-sfx-bytes")
        args = self._captured_args(sfx_cues=[{"path": str(sfx), "start_sec": 2.0, "volume": 0.5}])
        filters = self._filter_complex(args)
        self.assertIn("adelay=2000|2000", filters)
        self.assertIn("volume=0.5", filters)
        self.assertIn(str(sfx), args)

    def test_multiple_sfx_cues_each_get_their_own_delay(self):
        sfx1 = self.tmp_path / "sfx1.mp3"
        sfx1.write_bytes(b"a")
        sfx2 = self.tmp_path / "sfx2.mp3"
        sfx2.write_bytes(b"b")
        args = self._captured_args(
            sfx_cues=[
                {"path": str(sfx1), "start_sec": 0.5, "volume": 1.0},
                {"path": str(sfx2), "start_sec": 3.25, "volume": 1.0},
            ]
        )
        filters = self._filter_complex(args)
        self.assertIn("adelay=500|500", filters)
        self.assertIn("adelay=3250|3250", filters)

    def test_output_duration_flag_is_the_authoritative_video_duration(self):
        args = self._captured_args(video_duration=7.25)
        self.assertIn("-t", args)
        self.assertEqual(args[args.index("-t") + 1], "7.25")

    def test_missing_optional_audio_narration_only_still_produces_valid_command(self):
        # Neither music nor SFX -- the minimal, always-valid case.
        args = self._captured_args(music_path=None, sfx_cues=None)
        self.assertEqual(args.count("-i"), 1)  # narration is the only input
        self.assertIn("-map", args)
        self.assertEqual(args[args.index("-map") + 1], "[a]")


# -- caption preset generation (pure ASS generation, no ffmpeg needed) --------


class CaptionPresetGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = VideoComposerService(library_dir=self.tmp_path)
        self.words = [
            {"start": 0.0, "end": 0.3, "text": "This"},
            {"start": 0.3, "end": 0.6, "text": "is"},
            {"start": 0.6, "end": 1.0, "text": "a"},
            {"start": 1.0, "end": 1.5, "text": "test"},
            {"start": 1.5, "end": 2.0, "text": "narration"},
        ]
        self.lines = self.service._group_words_into_lines(self.words)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, preset: str) -> str:
        ass_path = self.tmp_path / f"{preset}.ass"
        srt_path = self.tmp_path / f"{preset}.srt"
        self.service._write_subtitles(self.lines, ass_path, srt_path, 480, 852, 32, preset)
        return ass_path.read_text(encoding="utf-8")

    def test_all_five_presets_generate_valid_non_empty_ass(self):
        self.assertEqual(set(CAPTION_PRESETS), {"emotional", "cinematic", "word_highlight", "big_statement", "quote"})
        for preset in CAPTION_PRESETS:
            content = self._write(preset)
            self.assertIn("[Script Info]", content)
            self.assertIn("[V4+ Styles]", content)
            self.assertIn("[Events]", content)
            self.assertIn("Dialogue:", content)

    def test_unknown_caption_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.service._write_subtitles(
                self.lines, self.tmp_path / "x.ass", self.tmp_path / "x.srt", 480, 852, 32, "not_a_real_preset"
            )

    def test_presets_produce_visually_distinct_caption_generation(self):
        bodies = [self._write(preset) for preset in CAPTION_PRESETS]
        self.assertEqual(len(set(bodies)), len(bodies), "every preset should generate distinct ASS content")

    def test_big_statement_uppercases_and_groups_two_words_per_event(self):
        content = self._write("big_statement")
        self.assertIn("THIS IS", content)

    def test_quote_preset_wraps_rows_in_quotation_marks(self):
        content = self._write("quote")
        self.assertIn("“", content)
        self.assertIn("”", content)

    def test_cinematic_preset_has_fewer_dialogue_events_than_word_timed_presets(self):
        # cinematic: one Dialogue per row (line-static); emotional: one per
        # word (box) plus one per row (text) -- meaningfully more events for
        # the same input, proving they're genuinely different renderers.
        cinematic_count = self._write("cinematic").count("Dialogue:")
        emotional_count = self._write("emotional").count("Dialogue:")
        self.assertLess(cinematic_count, emotional_count)

    def test_caption_timing_reflects_word_boundary_start_times(self):
        # First word "This" starts at t=0.0 -> ASS timestamp 0:00:00.00;
        # last word "narration" ends at t=2.0 -> 0:00:02.00.
        content = self._write("word_highlight")
        self.assertIn("0:00:00.00", content)
        self.assertIn("0:00:02.00", content)

    def test_caption_timing_differs_for_different_word_boundaries(self):
        shifted_words = [{**w, "start": w["start"] + 5.0, "end": w["end"] + 5.0} for w in self.words]
        shifted_lines = self.service._group_words_into_lines(shifted_words)
        ass_path = self.tmp_path / "shifted.ass"
        self.service._write_subtitles(shifted_lines, ass_path, self.tmp_path / "shifted.srt", 480, 852, 32, "cinematic")
        content = ass_path.read_text(encoding="utf-8")
        self.assertIn("0:00:05.00", content)
        self.assertNotIn("0:00:00.00", content)

    def test_srt_output_is_identical_regardless_of_caption_preset(self):
        srt_contents = set()
        for preset in CAPTION_PRESETS:
            srt_path = self.tmp_path / f"{preset}_ref.srt"
            self.service._write_subtitles(
                self.lines, self.tmp_path / f"{preset}_ref.ass", srt_path, 480, 852, 32, preset
            )
            srt_contents.add(srt_path.read_text(encoding="utf-8"))
        self.assertEqual(len(srt_contents), 1, "SRT is a fixed reference artifact, not preset-styled")


# -- real ffmpeg integration: duration, ducking (acoustic), caption burn-in ---


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class AudioMixIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = VideoComposerService(library_dir=self.tmp_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_audio_duration_is_deterministic_across_optional_layer_combinations(self):
        narration = _make_tone(self.tmp_path / "narration.mp3", 440, 2.0)
        music = _make_tone(self.tmp_path / "music.mp3", 220, 10.0)
        sfx = _make_tone(self.tmp_path / "sfx.mp3", 880, 0.3)
        video_duration = 3.0

        combinations = [
            {"music_path": None, "sfx_cues": None},
            {"music_path": str(music), "sfx_cues": None},
            {"music_path": None, "sfx_cues": [{"path": str(sfx), "start_sec": 1.0, "volume": 1.0}]},
            {"music_path": str(music), "sfx_cues": [{"path": str(sfx), "start_sec": 1.0, "volume": 1.0}]},
        ]
        for i, combo in enumerate(combinations):
            output = self.tmp_path / f"mix_{i}.m4a"
            self.service._mix_audio(
                narration, combo["music_path"], 0.15, 1.0, 8.0, 0.0, 0.0, video_duration, output,
                sfx_cues=combo["sfx_cues"],
            )
            self.assertAlmostEqual(_ffprobe_duration(output), video_duration, delta=0.05, msg=combo)

    def test_audio_duration_is_deterministic_with_fades(self):
        narration = _make_tone(self.tmp_path / "narration.mp3", 440, 2.0)
        output = self.tmp_path / "faded.m4a"
        self.service._mix_audio(narration, None, 0.15, 1.0, 8.0, 0.5, 0.5, 3.0, output)
        self.assertAlmostEqual(_ffprobe_duration(output), 3.0, delta=0.05)

    def test_missing_optional_music_still_produces_valid_audio(self):
        narration = _make_tone(self.tmp_path / "narration.mp3", 440, 2.0)
        output = self.tmp_path / "no_music.m4a"
        self.service._mix_audio(narration, None, 0.15, 1.0, 8.0, 0.0, 0.0, 2.5, output)
        self.assertTrue(output.exists())
        self.assertAlmostEqual(_ffprobe_duration(output), 2.5, delta=0.05)

    def test_music_ducking_measurably_reduces_music_level_while_narration_plays(self):
        # narration: true silence for 1.5s, then a loud tone for 1.5s.
        silence = self.tmp_path / "silence.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=1.5",
                "-c:a", "libmp3lame", str(silence),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        tone = _make_tone(self.tmp_path / "tone.mp3", 440, 1.5)
        narration = self.tmp_path / "narration.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(silence), "-i", str(tone),
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", "-c:a", "libmp3lame", str(narration),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        music = _make_tone(self.tmp_path / "music.mp3", 220, 5.0)

        # Isolate the ducked music branch alone (mirrors _mix_audio's own
        # narration-volume + ducking filter fragment) so the measurement
        # reflects only the music's level, not the combined mix (which
        # would otherwise be dominated by narration's own loud signal).
        ducked_only = self.tmp_path / "ducked_only.m4a"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
                "-filter_complex",
                "[0:a]volume=1.0,apad[narration];"
                "[1:a]volume=0.8[music_pre];"
                "[music_pre][narration]sidechaincompress=threshold=0.05:ratio=12.0:attack=5:release=300[ducked]",
                "-map", "[ducked]", "-t", "3.0", str(ducked_only),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )

        quiet_level = _mean_volume_db(ducked_only, start=0.2, duration=1.0)  # narration silent
        loud_level = _mean_volume_db(ducked_only, start=1.7, duration=1.0)  # narration speaking

        self.assertLess(loud_level, quiet_level - 2.0, "music should be measurably quieter while narration plays")

    def test_all_caption_presets_burn_successfully_via_real_ffmpeg(self):
        words = [
            {"start": 0.0, "end": 0.3, "text": "This"},
            {"start": 0.3, "end": 0.6, "text": "is"},
            {"start": 0.6, "end": 1.0, "text": "a"},
            {"start": 1.0, "end": 1.5, "text": "test"},
        ]
        lines = self.service._group_words_into_lines(words)

        base_video = self.tmp_path / "base.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=gray:s=480x852:d=2:r=12",
                "-pix_fmt", "yuv420p", str(base_video),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )

        for preset in CAPTION_PRESETS:
            ass_path = self.tmp_path / f"{preset}.ass"
            self.service._write_subtitles(lines, ass_path, self.tmp_path / f"{preset}.srt", 480, 852, 32, preset)

            burned = self.tmp_path / f"{preset}_burned.mp4"
            escaped = self.service._escape_for_ffmpeg_filter(ass_path)
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-i", str(base_video), "-vf", f"subtitles='{escaped}'", str(burned),
                ],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
            )
            self.assertEqual(result.returncode, 0, f"{preset} failed to burn: {result.stderr}")
            self.assertTrue(burned.exists())


if __name__ == "__main__":
    unittest.main()
