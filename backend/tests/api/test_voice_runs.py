"""voice_generate.voice_runs / voice_fingerprint with per-beat voice overrides."""

import unittest

from app.api.v1.endpoints.voice_generate import voice_fingerprint, voice_runs
from app.modules.beat.schemas import Beat, BeatType, VoiceProjectConfig

VOICE = VoiceProjectConfig(provider="edge_tts", voice_id="vi-VN-NamMinhNeural", language="vi")


def _beat(i, text, voice_id=None):
    return Beat(id=f"b{i}", order=i, type=BeatType.BUILD, narration=text, duration=2.0, voice_id=voice_id)


class VoiceRunsTests(unittest.TestCase):
    def test_consecutive_same_voice_beats_merge_into_runs(self):
        beats = [
            _beat(1, "kể một"), _beat(2, "kể hai"),
            _beat(3, "bình luận", "vi-VN-HoaiMyNeural"),
            _beat(4, "kể ba"),
            _beat(5, "chốt một", "vi-VN-HoaiMyNeural"), _beat(6, "chốt hai", "vi-VN-HoaiMyNeural"),
        ]
        self.assertEqual(voice_runs(beats, VOICE.voice_id), [
            ("kể một kể hai", "vi-VN-NamMinhNeural"),
            ("bình luận", "vi-VN-HoaiMyNeural"),
            ("kể ba", "vi-VN-NamMinhNeural"),
            ("chốt một chốt hai", "vi-VN-HoaiMyNeural"),
        ])

    def test_no_overrides_is_one_run_and_keeps_the_old_fingerprint(self):
        beats = [_beat(1, "một"), _beat(2, "hai")]
        runs = voice_runs(beats, VOICE.voice_id)
        self.assertEqual(len(runs), 1)
        self.assertEqual(voice_fingerprint("một hai", VOICE, runs), voice_fingerprint("một hai", VOICE))

    def test_changing_which_beat_gets_the_second_voice_changes_the_fingerprint(self):
        a = voice_runs([_beat(1, "một"), _beat(2, "hai", "vi-VN-HoaiMyNeural")], VOICE.voice_id)
        b = voice_runs([_beat(1, "một", "vi-VN-HoaiMyNeural"), _beat(2, "hai")], VOICE.voice_id)
        self.assertNotEqual(voice_fingerprint("một hai", VOICE, a), voice_fingerprint("một hai", VOICE, b))


if __name__ == "__main__":
    unittest.main()
