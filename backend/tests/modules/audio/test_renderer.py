import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.modules.audio.renderer import (
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_RATE,
    build_ffmpeg_command,
    probe_audio,
    render_audio_master,
    validate_audio_master,
)
from app.modules.audio.schemas import AudioError, AudioMixPlan

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class BuildFfmpegCommandTests(unittest.TestCase):
    def test_narration_only_plan_has_no_bgm_or_sidechain_filters(self):
        plan = AudioMixPlan(narration_path="narration.wav", target_duration=5.0, bgm_path=None)
        command = build_ffmpeg_command(plan, Path("out.wav"))
        joined = " ".join(command)
        self.assertNotIn("sidechaincompress", joined)
        self.assertNotIn("amix", joined)
        self.assertIn("narration.wav", joined)

    def test_bgm_plan_includes_stream_loop_and_sidechain_ducking(self):
        plan = AudioMixPlan(narration_path="narration.wav", target_duration=5.0, bgm_path="bgm.wav", ducking_enabled=True)
        command = build_ffmpeg_command(plan, Path("out.wav"))
        joined = " ".join(command)
        self.assertIn("-stream_loop", command)
        self.assertIn("sidechaincompress", joined)
        self.assertIn("amix=inputs=2", joined)

    def test_ducking_disabled_skips_sidechain_but_still_mixes(self):
        plan = AudioMixPlan(narration_path="narration.wav", target_duration=5.0, bgm_path="bgm.wav", ducking_enabled=False)
        command = build_ffmpeg_command(plan, Path("out.wav"))
        joined = " ".join(command)
        self.assertNotIn("sidechaincompress", joined)
        self.assertIn("amix=inputs=2", joined)

    def test_fades_are_included_when_nonzero(self):
        plan = AudioMixPlan(narration_path="n.wav", target_duration=5.0, fade_in_sec=0.5, fade_out_sec=1.0)
        joined = " ".join(build_ffmpeg_command(plan, Path("out.wav")))
        self.assertIn("afade=t=in:st=0:d=0.5", joined)
        self.assertIn("afade=t=out:st=4.0:d=1.0", joined)

    def test_zero_fades_are_omitted(self):
        plan = AudioMixPlan(narration_path="n.wav", target_duration=5.0, fade_in_sec=0.0, fade_out_sec=0.0)
        joined = " ".join(build_ffmpeg_command(plan, Path("out.wav")))
        self.assertNotIn("afade", joined)

    def test_output_format_is_lossless_wav_48k_stereo(self):
        plan = AudioMixPlan(narration_path="n.wav", target_duration=5.0)
        command = build_ffmpeg_command(plan, Path("out.wav"))
        self.assertIn("-ar", command)
        self.assertIn(str(OUTPUT_SAMPLE_RATE), command)
        self.assertIn("-ac", command)
        self.assertIn(str(OUTPUT_CHANNELS), command)
        self.assertIn("pcm_s16le", command)

    def test_loudness_normalization_is_always_applied(self):
        plan = AudioMixPlan(narration_path="n.wav", target_duration=5.0)
        joined = " ".join(build_ffmpeg_command(plan, Path("out.wav")))
        self.assertIn("loudnorm=I=-14.0:TP=-1.0", joined)

    def test_deterministic_output_same_inputs_produce_identical_command(self):
        plan = AudioMixPlan(narration_path="n.wav", target_duration=5.0, bgm_path="b.wav")
        first = build_ffmpeg_command(plan, Path("out.wav"))
        second = build_ffmpeg_command(plan, Path("out.wav"))
        self.assertEqual(first, second)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderAudioMasterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_tone(self, name: str, duration: float, freq: int = 300, channels: int = 1) -> Path:
        path = self.tmp_path / name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
             "-ar", "48000", "-ac", str(channels), str(path)],
            check=True, stdin=subprocess.DEVNULL,
        )
        return path

    def _make_silence(self, name: str, duration: float) -> Path:
        path = self.tmp_path / name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={duration}", str(path)],
            check=True, stdin=subprocess.DEVNULL,
        )
        return path

    def test_narration_only_bgm_off_produces_valid_output(self):
        narration = self._make_tone("narration.wav", 4.0)
        plan = AudioMixPlan(narration_path=str(narration), target_duration=4.0, bgm_path=None)
        out = self.tmp_path / "master.wav"
        render_audio_master(plan, out)
        probe = probe_audio(out)
        self.assertAlmostEqual(probe.duration_sec, 4.0, delta=0.15)
        validate_audio_master(probe, expected_duration=4.0)

    def test_short_bgm_loops_to_cover_the_full_narration_duration(self):
        narration = self._make_tone("narration.wav", 12.0, freq=300)
        bgm = self._make_tone("bgm.wav", 3.0, freq=150, channels=2)  # much shorter than narration
        plan = AudioMixPlan(narration_path=str(narration), target_duration=12.0, bgm_path=str(bgm))
        out = self.tmp_path / "master.wav"
        render_audio_master(plan, out)
        probe = probe_audio(out)
        self.assertAlmostEqual(probe.duration_sec, 12.0, delta=0.15)

    def test_long_bgm_trims_to_the_narration_duration(self):
        narration = self._make_tone("narration.wav", 4.0, freq=300)
        bgm = self._make_tone("bgm.wav", 20.0, freq=150, channels=2)  # much longer than narration
        plan = AudioMixPlan(narration_path=str(narration), target_duration=4.0, bgm_path=str(bgm))
        out = self.tmp_path / "master.wav"
        render_audio_master(plan, out)
        probe = probe_audio(out)
        self.assertAlmostEqual(probe.duration_sec, 4.0, delta=0.15)

    def test_ducking_reduces_bgm_level_while_narration_is_active(self):
        # Alternating narration: 2s tone, 2s silence, 2s tone (6s total),
        # continuous BGM at a different, isolatable frequency throughout.
        tone_seg = self._make_tone("seg_tone.wav", 2.0, freq=300)
        silence_seg = self._make_silence("seg_silence.wav", 2.0)
        narration = self.tmp_path / "narration_alt.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(tone_seg), "-i", str(silence_seg), "-i", str(tone_seg),
             "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]", "-map", "[out]", str(narration)],
            check=True, stdin=subprocess.DEVNULL,
        )
        bgm = self._make_tone("bgm.wav", 6.0, freq=150, channels=2)

        plan = AudioMixPlan(
            narration_path=str(narration), target_duration=6.0, bgm_path=str(bgm),
            bgm_volume=0.3, ducking_enabled=True, ducking_ratio=12.0, fade_in_sec=0.0, fade_out_sec=0.0,
        )
        out = self.tmp_path / "ducked.wav"
        render_audio_master(plan, out)

        def _bgm_band_mean_db(start: float) -> float:
            result = subprocess.run(
                ["ffmpeg", "-v", "info", "-ss", str(start), "-t", "1.4", "-i", str(out),
                 "-af", "bandpass=f=150:width_type=h:w=15,volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
            )
            for line in result.stderr.splitlines():
                if "mean_volume:" in line:
                    return float(line.split(":", 1)[1].strip().rstrip("dB").strip())
            self.fail(f"volumedetect produced no mean_volume for window at {start}s")

        active_db = _bgm_band_mean_db(0.3)  # narration speaking
        silent_db = _bgm_band_mean_db(2.3)  # narration not speaking
        self.assertGreater(
            silent_db, active_db + 3.0,
            f"BGM should be audibly louder while narration is silent (silent={silent_db}dB, active={active_db}dB)",
        )

    def test_intentionally_loud_input_does_not_clip_after_normalization(self):
        # A deliberately hot (near-0dBFS, heavily clipped-in-source) input.
        loud_path = self.tmp_path / "loud.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
             "-af", "volume=10dB", "-ar", "48000", "-ac", "1", str(loud_path)],
            check=True, stdin=subprocess.DEVNULL,
        )
        plan = AudioMixPlan(narration_path=str(loud_path), target_duration=3.0, bgm_path=None)
        out = self.tmp_path / "normalized.wav"
        render_audio_master(plan, out)
        probe = probe_audio(out)
        # loudnorm's own TP ceiling should keep real peak comfortably under
        # 0dBFS regardless of how hot the source was.
        self.assertLess(probe.max_volume_db, -0.5)
        validate_audio_master(probe, expected_duration=3.0)  # must not raise AUDIO_CLIPPING

    def test_silent_narration_raises_audio_silent_on_validation(self):
        silence = self._make_silence("silent_narration.wav", 3.0)
        plan = AudioMixPlan(narration_path=str(silence), target_duration=3.0, bgm_path=None)
        out = self.tmp_path / "silent_master.wav"
        render_audio_master(plan, out)  # the mix itself succeeds -- silence is a valid audio signal
        probe = probe_audio(out)
        with self.assertRaises(AudioError) as ctx:
            validate_audio_master(probe, expected_duration=3.0)
        self.assertEqual(ctx.exception.code, "AUDIO_SILENT")

    def test_duration_mismatch_raises_stable_code(self):
        narration = self._make_tone("narration.wav", 4.0)
        plan = AudioMixPlan(narration_path=str(narration), target_duration=4.0, bgm_path=None)
        out = self.tmp_path / "master.wav"
        render_audio_master(plan, out)
        probe = probe_audio(out)
        with self.assertRaises(AudioError) as ctx:
            validate_audio_master(probe, expected_duration=9.0)
        self.assertEqual(ctx.exception.code, "AUDIO_DURATION_MISMATCH")

    def test_missing_narration_file_raises_audio_mix_failed(self):
        plan = AudioMixPlan(narration_path=str(self.tmp_path / "nope.wav"), target_duration=3.0)
        with self.assertRaises(AudioError) as ctx:
            render_audio_master(plan, self.tmp_path / "out.wav")
        self.assertEqual(ctx.exception.code, "AUDIO_MIX_FAILED")

    def test_missing_bgm_file_raises_audio_mix_failed(self):
        narration = self._make_tone("narration.wav", 3.0)
        plan = AudioMixPlan(narration_path=str(narration), target_duration=3.0, bgm_path=str(self.tmp_path / "nope.wav"))
        with self.assertRaises(AudioError) as ctx:
            render_audio_master(plan, self.tmp_path / "out.wav")
        self.assertEqual(ctx.exception.code, "AUDIO_MIX_FAILED")

    def test_probe_unreadable_file_raises_audio_output_invalid(self):
        bogus = self.tmp_path / "not_audio.wav"
        bogus.write_bytes(b"nope")
        with self.assertRaises(AudioError) as ctx:
            probe_audio(bogus)
        self.assertEqual(ctx.exception.code, "AUDIO_OUTPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
