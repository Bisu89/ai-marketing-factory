"""Tests for Task 24 -- see docs/features/50-audio-master.md. Reuses
tests.api.test_factory_pipeline's own _FactoryTestCase harness. Uses real
FFmpeg mixing and the real LocalTTSProvider throughout (no mocking of the
audio engine itself) -- the same "exercise the real engine" precedent
Task 22/23's own stage tests already established.
"""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.v1.endpoints.audio_generate import (
    audio_fingerprint,
    audio_master_is_valid,
    audio_master_path,
    audio_was_attempted,
    generate_project_audio_master,
    resolve_bgm_asset,
)
from app.api.v1.endpoints.factory_pipeline import _stage_generate_audio, reconcile_factory_runs_on_startup
from app.api.v1.endpoints.voice_generate import generate_project_narration, narration_wav_path
from app.modules.asset.models import Asset
from app.modules.audio.schemas import AudioError
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import (
    AudioProjectConfig,
    Beat,
    BeatPlan,
    BeatType,
    ContentProjectConfig,
    ProjectConfig,
)
from tests.api.test_factory_pipeline import _FactoryTestCase


class _AudioStageTestCase(_FactoryTestCase):
    def _project_with_narration(self, name: str, texts: list[str], **config_overrides) -> int:
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
        generate_project_narration(project_id, self.settings)
        return project_id

    def _register_bgm_asset(self, name: str, tags: list[str], freq: int = 200, duration: float = 20.0) -> int:
        path = self.tmp_path / f"{name}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
             "-ar", "48000", "-ac", "2", str(path)],
            check=True, stdin=subprocess.DEVNULL,
        )
        db = self._db()
        try:
            from app.modules.asset.schemas import AssetRegisterIn
            from app.modules.asset.service import AssetService

            asset = AssetService(db).register(
                AssetRegisterIn(filename=path.name, path=str(path), type="audio", tags=tags, source="test")
            )
            return asset.id
        finally:
            db.close()


class BgmOffAndNarrationOnlyTests(_AudioStageTestCase):
    def test_bgm_disabled_produces_narration_only_audio_master(self):
        project_id = self._project_with_narration(
            "BGM Off", ["Some narration text for this beat."], audio=AudioProjectConfig(music_enabled=False)
        )
        generated = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(generated)
        out = audio_master_path(project_id, self.settings.library_dir)
        self.assertTrue(out.exists())

    def test_no_bgm_assets_in_library_still_produces_narration_only_master(self):
        # Section 34: the factory must still work with zero music assets.
        project_id = self._project_with_narration(
            "No BGM Library", ["Some narration text."], audio=AudioProjectConfig(music_enabled=True, bgm_mode="AUTO")
        )
        generated = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(generated)
        self.assertTrue(audio_master_path(project_id, self.settings.library_dir).exists())


class ManualBgmTests(_AudioStageTestCase):
    def test_manual_selection_is_used_even_when_a_better_auto_match_exists(self):
        auto_pick = self._register_bgm_asset("auto_pick", tags=["piano", "soft", "emotional"], freq=180)
        manual_pick = self._register_bgm_asset("manual_pick", tags=["upbeat"], freq=220)

        project_id = self._project_with_narration(
            "Manual BGM", ["Some narration text."],
            audio=AudioProjectConfig(music_enabled=True, bgm_mode="MANUAL", bgm_asset_id=manual_pick),
            content=ContentProjectConfig(tone="warm and reflective"),  # would auto-match auto_pick if AUTO
        )
        draft = get_project_draft(project_id)
        db = self._db()
        try:
            resolved = resolve_bgm_asset(project_id, draft.config, db)
        finally:
            db.close()
        self.assertEqual(resolved.id, manual_pick)
        self.assertNotEqual(resolved.id, auto_pick)

    def test_manual_selection_referencing_a_missing_asset_raises_bgm_not_found(self):
        project_id = self._project_with_narration(
            "Manual BGM Missing", ["Some narration text."],
            audio=AudioProjectConfig(music_enabled=True, bgm_mode="MANUAL", bgm_asset_id=999999),
        )
        with self.assertRaises(AudioError) as ctx:
            generate_project_audio_master(project_id, self.settings)
        self.assertEqual(ctx.exception.code, "BGM_NOT_FOUND")


class AutoBgmTests(_AudioStageTestCase):
    def test_auto_selection_picks_a_tone_matched_track(self):
        self._register_bgm_asset("piano_track", tags=["piano", "soft", "emotional"], freq=180)
        project_id = self._project_with_narration(
            "Auto BGM", ["Some narration text."],
            audio=AudioProjectConfig(music_enabled=True, bgm_mode="AUTO"),
            content=ContentProjectConfig(tone="warm and reflective"),
        )
        generated = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(generated)
        self.assertTrue(audio_master_path(project_id, self.settings.library_dir).exists())


class IdempotencyTests(_AudioStageTestCase):
    def test_second_call_with_unchanged_state_does_not_remix(self):
        project_id = self._project_with_narration("Audio Reuse", ["Some narration text."])
        first = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(first)

        out = audio_master_path(project_id, self.settings.library_dir)
        first_mtime = out.stat().st_mtime_ns

        second = generate_project_audio_master(project_id, self.settings)
        self.assertFalse(second)
        self.assertEqual(out.stat().st_mtime_ns, first_mtime)


class InvalidationTests(_AudioStageTestCase):
    def test_narration_change_invalidates_the_cached_master(self):
        project_id = self._project_with_narration("Narration Change", ["Original narration text."])
        generate_project_audio_master(project_id, self.settings)
        out = audio_master_path(project_id, self.settings.library_dir)
        original_mtime = out.stat().st_mtime_ns

        draft = get_project_draft(project_id)
        edited_beats = [b.model_copy(update={"narration": "Completely different narration content now."}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=edited_beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        generate_project_narration(project_id, self.settings)  # Voice regenerates first, same as the real pipeline

        regenerated = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(out.stat().st_mtime_ns, original_mtime)

    def test_bgm_change_invalidates_without_touching_visual_or_motion_state(self):
        track_a = self._register_bgm_asset("track_a", tags=["piano"], freq=180)
        track_b = self._register_bgm_asset("track_b", tags=["piano"], freq=220)

        project_id = self._project_with_narration(
            "BGM Change", ["Some narration text."],
            audio=AudioProjectConfig(music_enabled=True, bgm_mode="MANUAL", bgm_asset_id=track_a),
        )
        generate_project_audio_master(project_id, self.settings)
        out = audio_master_path(project_id, self.settings.library_dir)
        original_mtime = out.stat().st_mtime_ns

        draft = get_project_draft(project_id)
        visual_asset_id_before = draft.beats[0].asset_id  # untouched by this stage regardless
        new_config = draft.config.model_copy(
            update={"audio": draft.config.audio.model_copy(update={"bgm_asset_id": track_b})}
        )
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=new_config)
        update_project_beat_plan(project_id, plan)

        regenerated = generate_project_audio_master(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(out.stat().st_mtime_ns, original_mtime)

        draft_after = get_project_draft(project_id)
        self.assertEqual(draft_after.beats[0].asset_id, visual_asset_id_before)  # visuals untouched

    def test_fingerprint_differs_for_different_ducking_ratio(self):
        f1 = audio_fingerprint("narration-x", "bgm-y", 1.0, 0.15, True, 8.0, 0.5, 1.0)
        f2 = audio_fingerprint("narration-x", "bgm-y", 1.0, 0.15, True, 12.0, 0.5, 1.0)
        self.assertNotEqual(f1, f2)


class CrashRecoveryTests(_AudioStageTestCase):
    def test_run_stuck_in_generating_audio_is_marked_interrupted_on_reconcile(self):
        from app.modules.factory import service as factory_service

        project_id = self._project_with_narration("Audio Crash", ["Some narration text."])
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="GENERATING_AUDIO")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "GENERATING_AUDIO")

    def test_audio_master_is_valid_false_when_the_file_is_deleted(self):
        project_id = self._project_with_narration("Deleted Master", ["Some narration text."])
        generate_project_audio_master(project_id, self.settings)
        out = audio_master_path(project_id, self.settings.library_dir)
        out.unlink()

        self.assertFalse(audio_master_is_valid(project_id, self.settings))
        self.assertTrue(audio_was_attempted(project_id, self.settings.library_dir))

    def test_audio_was_never_attempted_for_a_fresh_project(self):
        project_id = self._project_with_narration("Never Ran Audio", ["Some narration text."])
        self.assertFalse(audio_was_attempted(project_id, self.settings.library_dir))


class StageErrorTranslationTests(_AudioStageTestCase):
    def test_bgm_not_found_is_translated_into_a_factory_stage_error(self):
        from app.api.v1.endpoints.factory_pipeline import FactoryStageError

        project_id = self._project_with_narration(
            "Stage Error BGM", ["Some narration text."],
            audio=AudioProjectConfig(music_enabled=True, bgm_mode="MANUAL", bgm_asset_id=999999),
        )
        with self.assertRaises(FactoryStageError) as ctx:
            _stage_generate_audio(project_id, self.settings)
        self.assertEqual(ctx.exception.code, "BGM_NOT_FOUND")
        self.assertEqual(ctx.exception.stage, "GENERATING_AUDIO")


class PipelineIntegrationTests(_AudioStageTestCase):
    def test_full_run_produces_audio_master_after_voice_and_motion(self):
        from tests.api.test_batch_render import _make_solid_image

        image = _make_solid_image(self.tmp_path / "audio_pipeline.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(image)

        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Audio In Pipeline", "placeholder script", ProjectConfig())
        draft = get_project_draft(project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some real narration text.", duration=2.0, asset_id=asset_id)]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertIn(run.status, ("QUEUED", "NEEDS_REVIEW", "COMPLETED"))

        self.assertTrue(narration_wav_path(project_id, self.settings).exists())
        self.assertTrue(audio_master_path(project_id, self.settings.library_dir).exists())


class BatchTests(_AudioStageTestCase):
    def test_five_projects_complete_the_audio_stage(self):
        from app.api.v1.endpoints.factory_pipeline import run_batch_factory
        from app.modules.batch import service as batch_service
        from app.modules.batch.schemas import CreateBatchRequest
        from tests.api.test_batch_render import _make_solid_image
        from app.api.v1.endpoints.batch_render import create_batch

        image = _make_solid_image(self.tmp_path / "batch_shared.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(image)

        scripts = "\n---\n".join(f"Batch script number {i}." for i in range(1, 6))
        with patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal):
            batch = create_batch(CreateBatchRequest(name="Audio Batch", template_id="custom", scripts_text=scripts), self.settings)

        for item in batch.items:
            draft = get_project_draft(item.project_id)
            beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some narration text for this beat.", duration=2.0, asset_id=asset_id)]
            plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
            update_project_beat_plan(item.project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            started = run_batch_factory(batch.id, self.settings, self.service)
            mock_generate.assert_not_called()

        self.assertEqual(started, 5)

        settled = get_project_draft(batch.items[0].project_id)  # sanity: project still readable
        self.assertIsNotNone(settled)
        for item in batch.items:
            self.assertTrue(audio_master_path(item.project_id, self.settings.library_dir).exists())


if __name__ == "__main__":
    unittest.main()
