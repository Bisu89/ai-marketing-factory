"""ElevenLabs narration config (feature 163): key never leaks, partial
updates only touch what was sent, bad values are rejected."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.endpoints import settings as ep
from app.core.config import Settings


class ElevenLabsSettingsTests(unittest.TestCase):
    def test_view_never_contains_the_key(self):
        s = Settings(elevenlabs_api_key="sk-secret", elevenlabs_voice_id="v1", _env_file=None)
        view = ep._elevenlabs_view(s)
        self.assertNotIn("sk-secret", str(view))
        self.assertTrue(view["has_api_key"])
        self.assertTrue(view["ready"])

    def test_not_ready_without_voice(self):
        s = Settings(elevenlabs_api_key="k", _env_file=None)
        self.assertFalse(ep._elevenlabs_view(s)["ready"])

    def test_partial_update_sends_only_given_fields(self):
        with patch.object(ep, "update_elevenlabs_settings") as upd:
            ep.set_elevenlabs(ep.ElevenLabsSettingsIn(voice_id=" abc ", stability=0.3))
        upd.assert_called_once_with({"voice_id": "abc", "stability": "0.3"})

    def test_empty_payload_and_blank_string_rejected(self):
        with patch.object(ep, "update_elevenlabs_settings"):
            with self.assertRaises(HTTPException):
                ep.set_elevenlabs(ep.ElevenLabsSettingsIn())
            with self.assertRaises(HTTPException):
                ep.set_elevenlabs(ep.ElevenLabsSettingsIn(api_key="  "))

    def test_out_of_range_rejected(self):
        with self.assertRaises(PydanticValidationError):
            ep.ElevenLabsSettingsIn(stability=1.5)
        with self.assertRaises(PydanticValidationError):
            ep.ElevenLabsSettingsIn(speed=2.0)


if __name__ == "__main__":
    unittest.main()
