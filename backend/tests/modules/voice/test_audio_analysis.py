"""Tests for app.modules.voice.audio_analysis's validate_audio (Task 22
sections 10/14/36). Pure -- AudioProbe is a plain dataclass, no ffmpeg
subprocess involved for this part.
"""

import unittest

from app.modules.voice.audio_analysis import validate_audio
from app.modules.voice.schemas import AudioProbe, VoiceError


def _probe(**overrides) -> AudioProbe:
    defaults = dict(duration_sec=5.0, sample_rate=48000, channels=1, codec="pcm_s16le", mean_volume_db=-20.0, max_volume_db=-5.0)
    defaults.update(overrides)
    return AudioProbe(**defaults)


class ValidateAudioTests(unittest.TestCase):
    def test_valid_audio_raises_nothing(self):
        validate_audio(_probe())  # no exception

    def test_zero_duration_raises_tts_invalid_output(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(duration_sec=0.0))
        self.assertEqual(ctx.exception.code, "TTS_INVALID_OUTPUT")

    def test_negative_duration_raises_tts_invalid_output(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(duration_sec=-1.0))
        self.assertEqual(ctx.exception.code, "TTS_INVALID_OUTPUT")

    def test_zero_sample_rate_raises_voice_format_invalid(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(sample_rate=0))
        self.assertEqual(ctx.exception.code, "VOICE_FORMAT_INVALID")

    def test_zero_channels_raises_voice_format_invalid(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(channels=0))
        self.assertEqual(ctx.exception.code, "VOICE_FORMAT_INVALID")

    def test_near_silent_audio_raises_voice_silent(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(mean_volume_db=-60.0))
        self.assertEqual(ctx.exception.code, "VOICE_SILENT")

    def test_audio_right_at_the_silence_threshold_is_rejected(self):
        with self.assertRaises(VoiceError) as ctx:
            validate_audio(_probe(mean_volume_db=-50.0))
        self.assertEqual(ctx.exception.code, "VOICE_SILENT")

    def test_audio_just_above_the_silence_threshold_passes(self):
        validate_audio(_probe(mean_volume_db=-49.9))  # no exception

    def test_unknown_loudness_never_blocks_validation(self):
        # ffmpeg's volumedetect can fail to report a value for a very short
        # clip -- section 36's own guard against a False silence rejection
        # when loudness simply couldn't be measured.
        validate_audio(_probe(mean_volume_db=None, max_volume_db=None))


if __name__ == "__main__":
    unittest.main()
