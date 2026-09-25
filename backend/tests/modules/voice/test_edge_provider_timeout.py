"""EdgeTTSProvider must not hang forever on a stalled edge_tts stream (real
incident: factory run 130 sat in GENERATING_VOICE for 10+ minutes after a
retry's WebSocket never produced a chunk). edge_tts itself is faked."""

import asyncio
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.modules.voice import providers


class _FakeCommunicate:
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).calls += 1
        self.stall = type(self).calls == 1  # first attempt stalls, the retry works

    async def stream(self):
        if self.stall:
            await asyncio.Event().wait()  # never set: a stream that never yields nor closes
        yield {"type": "audio", "data": b"fake-mp3"}
        yield {"type": "WordBoundary", "text": "xin", "offset": 0, "duration": 2_000_000}


def _fake_convert_to_wav(_src: Path, dst: Path) -> None:
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)


class EdgeTTSStallTests(unittest.TestCase):
    def test_a_stalled_attempt_times_out_and_the_retry_succeeds(self):
        _FakeCommunicate.calls = 0
        with TemporaryDirectory() as tmp, \
                patch("edge_tts.Communicate", _FakeCommunicate), \
                patch.object(providers, "_SEGMENT_ATTEMPT_TIMEOUT_SEC", 0.2), \
                patch.object(providers, "_convert_to_wav", _fake_convert_to_wav):
            result = providers.EdgeTTSProvider().synthesize(
                "xin", "vi-VN-NamMinhNeural", "vi", 1.0, Path(tmp) / "out.wav",
            )
        self.assertEqual(_FakeCommunicate.calls, 2)
        self.assertEqual([w.text for w in result.word_timestamps], ["xin"])


if __name__ == "__main__":
    unittest.main()
