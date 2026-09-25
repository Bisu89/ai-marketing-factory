"""Multi-voice narration (Beat.voice_id overrides): synthesize_voice_runs splices
one synthesize() per run and shifts word timings onto the joint timeline."""

import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.voice.providers import TTSProvider, synthesize_voice_runs
from app.modules.voice.schemas import AudioResult, WordTiming

RATE = 24000


class _FakeProvider(TTSProvider):
    """Writes 1.0s of silence per run; one word per input word, 0.2s apart."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text, voice_id, language, speed, output_path, sentence_pause_sec=0.35):
        self.calls.append((text, voice_id))
        with wave.open(str(output_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"\x00\x00" * RATE)
        words = [WordTiming(text=t, start=i * 0.2, end=i * 0.2 + 0.15) for i, t in enumerate(text.split())]
        return AudioResult(path=str(output_path), duration_sec=1.0, sample_rate=RATE, channels=1, word_timestamps=words)

    def list_voices(self):
        return []


class SynthesizeVoiceRunsTests(unittest.TestCase):
    def test_each_run_uses_its_voice_and_word_times_continue_across_runs(self):
        provider = _FakeProvider()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "narration.wav"
            result = synthesize_voice_runs(
                provider, [("một hai", "male"), ("ba", "female")], "vi", 1.0, out, sentence_pause_sec=0.1,
            )
            self.assertTrue(out.exists())
        self.assertEqual(provider.calls, [("một hai", "male"), ("ba", "female")])
        self.assertEqual([w.text for w in result.word_timestamps], ["một", "hai", "ba"])
        # run 1 is trimmed to its last word (0.35s) + 0.08s buffer, then a 0.1s pause
        self.assertAlmostEqual(result.word_timestamps[2].start, 0.35 + 0.08 + 0.1, places=3)
        self.assertAlmostEqual(result.duration_sec, 0.43 + 0.1 + 0.23, places=2)


if __name__ == "__main__":
    unittest.main()
