"""Tests for Task 22 -- see docs/features/48-voice-factory-local-tts.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness.
Uses the real LocalTTSProvider (genuinely offline SAPI5, no network, no
mocking) -- Task 22's own core promise is that this path works with zero
external dependencies, so these tests exercise the real engine rather than
faking it, the same way EndToEndTests already exercises a real FFmpeg
render.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.v1.endpoints.factory_pipeline import _stage_generate_voice, reconcile_factory_runs_on_startup
from app.api.v1.endpoints.voice_generate import (
    build_narration_text,
    generate_project_narration,
    narration_is_valid,
    narration_wav_path,
    voice_fingerprint,
)
from app.modules.asset.models import Asset
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import (
    AudioProjectConfig,
    Beat,
    BeatPlan,
    BeatType,
    ProjectConfig,
    VoiceProjectConfig,
)
from app.modules.factory.schemas import VOICE_SILENT
from tests.api.test_factory_pipeline import _FactoryTestCase


class _VoiceStageTestCase(_FactoryTestCase):
    def _project_with_beats(self, name: str, texts: list[str], **config_overrides) -> int:
        from app.modules.beat.project_service import create_project

        config = ProjectConfig(**config_overrides)
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project(name, "placeholder script", config)
        beats = [
            Beat(id=f"b{i}", order=i, type=BeatType.BODY, narration=text, duration=1.0)
            for i, text in enumerate(texts, start=1)
        ]
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        return project_id


class NarrationGenerationTests(_VoiceStageTestCase):
    def test_generates_real_narration_wav_and_assigns_every_beat(self):
        project_id = self._project_with_beats(
            "Voice Basic", ["This is the first beat's narration.", "And this is the second beat."]
        )
        generated = generate_project_narration(project_id, self.settings)
        self.assertTrue(generated)

        wav = narration_wav_path(project_id, self.settings)
        self.assertTrue(wav.exists())
        self.assertGreater(wav.stat().st_size, 0)

        draft = get_project_draft(project_id)
        for beat in draft.beats:
            self.assertIsNotNone(beat.narration_asset_id)
            self.assertIsNotNone(beat.start)
            self.assertIsNotNone(beat.end)
            self.assertGreater(beat.end, beat.start)

        db = self._db()
        try:
            for beat in draft.beats:
                asset = db.get(Asset, beat.narration_asset_id)
                self.assertIsNotNone(asset)
                self.assertEqual(asset.type, "audio")
                self.assertTrue(Path(asset.path).exists())
        finally:
            db.close()

    def test_timing_is_gapless_and_covers_the_full_narration(self):
        project_id = self._project_with_beats(
            "Voice Timing", ["Short.", "A somewhat longer beat with more words in it.", "End."]
        )
        generate_project_narration(project_id, self.settings)
        draft = get_project_draft(project_id)
        ordered = sorted(draft.beats, key=lambda b: b.order)
        self.assertEqual(ordered[0].start, 0.0)
        for prev, cur in zip(ordered, ordered[1:]):
            self.assertAlmostEqual(prev.end, cur.start, places=3)

    def test_narration_disabled_skips_the_stage_entirely(self):
        project_id = self._project_with_beats(
            "Voice Disabled", ["Some narration."], audio=AudioProjectConfig(narration_enabled=False)
        )
        generated = generate_project_narration(project_id, self.settings)
        self.assertFalse(generated)
        self.assertFalse(narration_wav_path(project_id, self.settings).exists())
        draft = get_project_draft(project_id)
        self.assertIsNone(draft.beats[0].narration_asset_id)


class IdempotencyTests(_VoiceStageTestCase):
    def test_second_call_with_unchanged_script_and_voice_does_not_regenerate(self):
        project_id = self._project_with_beats("Voice Reuse", ["Some narration text here."])
        first = generate_project_narration(project_id, self.settings)
        self.assertTrue(first)

        wav = narration_wav_path(project_id, self.settings)
        first_mtime = wav.stat().st_mtime_ns

        second = generate_project_narration(project_id, self.settings)
        self.assertFalse(second)  # nothing regenerated -- same script, same voice config
        self.assertEqual(wav.stat().st_mtime_ns, first_mtime)


class InvalidationTests(_VoiceStageTestCase):
    def test_script_change_invalidates_the_cached_fingerprint(self):
        project_id = self._project_with_beats("Voice Script Change", ["Original narration text."])
        generate_project_narration(project_id, self.settings)
        original_fingerprint = voice_fingerprint(
            build_narration_text(get_project_draft(project_id).beats), VoiceProjectConfig()
        )

        draft = get_project_draft(project_id)
        edited_beats = [b.model_copy(update={"narration": "Completely different narration text now."}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=edited_beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        new_fingerprint = voice_fingerprint(build_narration_text(edited_beats), VoiceProjectConfig())
        self.assertNotEqual(original_fingerprint, new_fingerprint)

        regenerated = generate_project_narration(project_id, self.settings)
        self.assertTrue(regenerated)

    def test_voice_settings_change_invalidates_without_touching_visual_assignment(self):
        project_id = self._project_with_beats("Voice Settings Change", ["Some narration text."])
        generate_project_narration(project_id, self.settings)
        draft = get_project_draft(project_id)
        visual_asset_id_before = draft.beats[0].asset_id  # None -- never set by this stage

        new_config = draft.config.model_copy(update={"voice": VoiceProjectConfig(speed=1.5)})
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=new_config)
        update_project_beat_plan(project_id, plan)

        regenerated = generate_project_narration(project_id, self.settings)
        self.assertTrue(regenerated)
        draft_after = get_project_draft(project_id)
        self.assertEqual(draft_after.beats[0].asset_id, visual_asset_id_before)  # visuals untouched


class StageErrorTranslationTests(_VoiceStageTestCase):
    def test_silent_audio_is_translated_into_a_factory_stage_error_with_the_stable_code(self):
        from app.api.v1.endpoints.factory_pipeline import FactoryStageError
        from app.modules.voice.schemas import VoiceError

        project_id = self._project_with_beats("Voice Silent", ["Some narration."])
        with patch(
            "app.api.v1.endpoints.voice_generate.validate_audio",
            side_effect=VoiceError(VOICE_SILENT, "Synthesized audio is essentially silent."),
        ):
            with self.assertRaises(FactoryStageError) as ctx:
                _stage_generate_voice(project_id, self.settings)
        self.assertEqual(ctx.exception.code, VOICE_SILENT)
        self.assertEqual(ctx.exception.stage, "GENERATING_VOICE")


class CrashRecoveryTests(_VoiceStageTestCase):
    def test_run_stuck_in_generating_voice_is_marked_interrupted_on_reconcile(self):
        from app.modules.factory import service as factory_service

        project_id = self._project_with_beats("Voice Crash", ["Some narration."])
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="GENERATING_VOICE")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "GENERATING_VOICE")

    def test_narration_is_valid_false_when_the_wav_file_is_missing(self):
        project_id = self._project_with_beats("Voice Missing Wav", ["Some narration."])
        self.assertFalse(narration_is_valid(project_id, self.settings))

    def test_narration_is_valid_true_after_real_generation(self):
        project_id = self._project_with_beats("Voice Valid Check", ["Some narration."])
        generate_project_narration(project_id, self.settings)
        self.assertTrue(narration_is_valid(project_id, self.settings))


class PipelineIntegrationTests(_VoiceStageTestCase):
    def test_full_run_persists_voice_before_quality_check(self):
        project_id = self._project_with_beats("Voice In Pipeline", ["Some narration text for this beat."])
        db = self._db()
        try:
            from app.modules.asset.schemas import AssetRegisterIn
            from app.modules.asset.service import AssetService
            from tests.api.test_batch_render import _make_solid_image

            image = _make_solid_image(self.tmp_path / "voice_pipeline.jpg", (10, 200, 10))
            asset = AssetService(db).register(AssetRegisterIn(filename=image.name, path=str(image), type="image", source="test"))
            asset_id = asset.id
        finally:
            db.close()

        draft = get_project_draft(project_id)
        beats = [b.model_copy(update={"asset_id": asset_id}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertIn(run.status, ("QUEUED", "NEEDS_REVIEW", "COMPLETED"))

        final_draft = get_project_draft(project_id)
        self.assertIsNotNone(final_draft.beats[0].narration_asset_id)
        self.assertTrue(narration_wav_path(project_id, self.settings).exists())


if __name__ == "__main__":
    unittest.main()
